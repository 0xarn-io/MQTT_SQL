"""FastAPI application entry point and process lifecycle.

Boots the MQTT subscriber as a background task during the FastAPI lifespan,
serves a single `GET /health` endpoint, and on Windows forces a Selector-
based event loop because paho-mqtt (under aiomqtt) needs `add_reader` /
`add_writer` and the default ProactorEventLoop doesn't implement them.
"""

import asyncio
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response

from .config import settings
from .db import check_db, engine
from .mqtt_subscriber import run_subscriber, state as mqtt_state


def _configure_logging() -> None:
    """Set up the root logger once, before any module-level logs fire.

    We use basicConfig (rather than dictConfig) because we have one
    process, one format, one destination, and zero need for hot-reload.
    """
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


_configure_logging()
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Spin up the subscriber task on app boot, cancel it cleanly on shutdown.

    The `stop_event` lets the subscriber exit its retry loop immediately
    rather than waiting out the current backoff sleep. `task.cancel()` is
    still issued to handle the case where it's mid-MQTT-call.
    """
    stop_event = asyncio.Event()
    task = asyncio.create_task(run_subscriber(stop_event), name="mqtt-subscriber")
    log.info("Subscriber task started")
    try:
        yield
    finally:
        log.info("Shutting down subscriber")
        stop_event.set()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        await engine.dispose()
        log.info("Shutdown complete")


app = FastAPI(title="mqtt_sql", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health(response: Response) -> dict:
    """Report broker + DB connectivity. Returns 200 when both are up, 503 otherwise.

    Both checks are cheap (broker check reads an in-memory flag; DB check
    runs `SELECT 1`), so we don't bother caching for this endpoint at v0.1
    volume.
    """
    db_ok = await check_db()
    broker_ok = mqtt_state.connected
    body = {
        "status": "ok" if (db_ok and broker_ok) else "degraded",
        "broker": "connected" if broker_ok else "down",
        "db": "ok" if db_ok else "down",
    }
    if not (db_ok and broker_ok):
        response.status_code = 503
    return body


def main() -> None:
    """Run uvicorn under an asyncio.Runner with an explicit loop factory.

    Why not just `uvicorn.run(...)`? On Windows it calls
    `set_event_loop_policy(WindowsProactorEventLoopPolicy())` internally,
    which clobbers any policy we set earlier. ProactorEventLoop doesn't
    implement add_reader/add_writer, which paho-mqtt (inside aiomqtt)
    relies on — so the subscriber crashes immediately.

    Building the loop ourselves via `asyncio.Runner(loop_factory=...)`
    sidesteps the override entirely; we pass `Server.serve()` (the
    coroutine) to the Runner instead of letting uvicorn manage its own
    loop. SelectorEventLoop on Windows; default elsewhere.
    """
    import uvicorn

    config = uvicorn.Config(
        "mqtt_sql.main:app",
        host=settings.http_host,
        port=settings.http_port,
        log_level=settings.log_level.lower(),
    )
    server = uvicorn.Server(config)

    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    with asyncio.Runner(loop_factory=loop_factory) as runner:
        runner.run(server.serve())


if __name__ == "__main__":
    main()
