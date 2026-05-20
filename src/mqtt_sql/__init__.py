"""mqtt_sql — minimal MQTT-to-SQL Server ingest service.

This package subscribes to an MQTT broker on `devices/#` and writes every
received message verbatim into `dbo.messages` in SQL Server. It also exposes
a tiny FastAPI app with a `GET /health` endpoint reporting broker + DB
connectivity.

Module layout:
- `config`           - environment-driven settings (pydantic-settings)
- `db`               - async SQLAlchemy engine + insert/health helpers
- `mqtt_subscriber`  - background loop that subscribes + forwards to db
- `main`             - FastAPI app, lifespan, and entry point

This is the v0.1 "hello world" slice; see the project plan for the roadmap
(customers/devices registry, per-machine-type tables, commands, etc.).
"""

__version__ = "0.1.0"
