"""Background MQTT subscriber that forwards messages to SQL Server.

The `run_subscriber` coroutine is launched from the FastAPI lifespan and runs
until the `stop_event` is set. On any broker error it reconnects with
exponential backoff + jitter, so a flapping broker can't pin the CPU and
many parallel deployments don't reconnect in lockstep.

`state.connected` is a process-wide flag the `/health` endpoint reads.
"""

import asyncio
import logging
import random
from dataclasses import dataclass

import aiomqtt

from .config import settings
from .db import insert_message

log = logging.getLogger(__name__)

# All real device traffic lands under devices/<id>/... — broker `$SYS` topics
# and any ad-hoc test topics are intentionally ignored.
SUBSCRIBE_TOPIC = "devices/#"

# MQTT-level keepalive in seconds. The broker disconnects clients that go
# silent for longer than 1.5× this value, so a smaller number detects dead
# TCP sessions faster at the cost of a few extra PINGREQ packets.
KEEPALIVE_SECONDS = 30

# Reconnect backoff bounds. The delay doubles on each consecutive failure
# (1s → 2s → 4s → ...), capped at MAX, then ±50% jitter is added so a fleet
# of processes restarting at once doesn't dogpile the broker.
BACKOFF_BASE_SECONDS = 1.0
BACKOFF_MAX_SECONDS = 60.0


@dataclass
class SubscriberState:
    """Liveness flag the /health endpoint reads. Updated by the subscriber loop."""

    connected: bool = False


state = SubscriberState()


def _decode_payload(payload: object) -> str:
    """Best-effort decode of an MQTT payload to a text string.

    Devices in this project send UTF-8 JSON, but the broker also accepts
    arbitrary bytes. We replace undecodable bytes rather than dropping the
    message so the raw payload still lands in the DB for inspection.
    """
    if isinstance(payload, (bytes, bytearray)):
        return payload.decode("utf-8", errors="replace")
    return str(payload)


def _backoff_delay(attempt: int) -> float:
    """Exponential backoff with 0-50% jitter, capped at BACKOFF_MAX_SECONDS."""
    base = min(BACKOFF_MAX_SECONDS, BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)))
    return base + random.uniform(0, base * 0.5)


async def _run_session() -> None:
    """One broker session: connect, subscribe, loop until disconnect or error.

    Returning normally means the broker closed the connection cleanly; any
    error is raised as `aiomqtt.MqttError` for the outer loop to handle.
    """
    async with aiomqtt.Client(
        hostname=settings.mqtt_host,
        port=settings.mqtt_port,
        keepalive=KEEPALIVE_SECONDS,
    ) as client:
        state.connected = True
        log.info("MQTT connected to %s:%s", settings.mqtt_host, settings.mqtt_port)
        await client.subscribe(SUBSCRIBE_TOPIC)
        log.info("Subscribed to %s", SUBSCRIBE_TOPIC)

        async for msg in client.messages:
            topic = str(msg.topic)
            payload = _decode_payload(msg.payload)
            try:
                await insert_message(topic, payload)
            except Exception:
                # A DB error on one message must not kill the subscriber —
                # log it and keep going so the next message gets a chance.
                # We catch broad Exception (not just SQLAlchemyError) on
                # purpose: a network blip, ODBC driver hiccup, or anything
                # else here should be survivable.
                log.exception("Failed to insert message for topic %s", topic)


async def run_subscriber(stop_event: asyncio.Event) -> None:
    """Subscribe loop that survives broker disconnects until told to stop.

    Each iteration either completes a full session and resets the backoff
    attempt counter, or fails with `MqttError` and waits an exponential
    backoff (or until `stop_event` fires, whichever comes first).
    """
    attempt = 0
    while not stop_event.is_set():
        try:
            await _run_session()
            attempt = 0  # session ended cleanly; restart counter
        except aiomqtt.MqttError as e:
            attempt += 1
            delay = _backoff_delay(attempt)
            log.warning(
                "MQTT session error: %s. Reconnecting in %.1fs (attempt %d).",
                e, delay, attempt,
            )
        finally:
            state.connected = False

        if stop_event.is_set():
            break

        # Sleep until either the backoff elapses or shutdown is signalled.
        # `wait_for` cancels cleanly when stop_event is set, so shutdown
        # doesn't have to wait the full delay.
        delay = _backoff_delay(attempt) if attempt else BACKOFF_BASE_SECONDS
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=delay)
        except asyncio.TimeoutError:
            pass
