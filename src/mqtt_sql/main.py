import asyncio
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response

from .config import settings
from .db import check_db, engine
from .mqtt_subscriber import run_subscriber, state as mqtt_state

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
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
    import uvicorn

    config = uvicorn.Config(
        "mqtt_sql.main:app",
        host=settings.http_host,
        port=settings.http_port,
        log_level=settings.log_level.lower(),
    )
    server = uvicorn.Server(config)

    # Windows: paho-mqtt (under aiomqtt) needs add_reader/add_writer, which
    # ProactorEventLoop doesn't implement. uvicorn.run() forces a Proactor policy
    # on Windows, so drive the server ourselves via asyncio.Runner with an explicit
    # SelectorEventLoop factory.
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    with asyncio.Runner(loop_factory=loop_factory) as runner:
        runner.run(server.serve())


if __name__ == "__main__":
    main()
