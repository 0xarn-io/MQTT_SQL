import asyncio
import logging
from dataclasses import dataclass

import aiomqtt

from .config import settings
from .db import insert_message

log = logging.getLogger(__name__)

RECONNECT_DELAY_SECONDS = 5.0
SUBSCRIBE_TOPIC = "devices/#"


@dataclass
class SubscriberState:
    connected: bool = False


state = SubscriberState()


def _decode_payload(payload: object) -> str:
    if isinstance(payload, (bytes, bytearray)):
        return payload.decode("utf-8", errors="replace")
    return str(payload)


async def _run_session() -> None:
    async with aiomqtt.Client(hostname=settings.mqtt_host, port=settings.mqtt_port) as client:
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
                log.exception("Failed to insert message for topic %s", topic)


async def run_subscriber(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            await _run_session()
        except aiomqtt.MqttError as e:
            log.warning("MQTT session error: %s. Reconnecting in %ss.", e, RECONNECT_DELAY_SECONDS)
        finally:
            state.connected = False

        if stop_event.is_set():
            break
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=RECONNECT_DELAY_SECONDS)
        except asyncio.TimeoutError:
            pass
