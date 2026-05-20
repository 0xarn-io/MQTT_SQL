# mqtt_sql — v0.1 "hello world"

A tiny Python service that:

1. subscribes to an MQTT broker on `devices/#`,
2. drops every message verbatim (topic + raw payload) into a single MS SQL Server table,
3. exposes a `GET /health` endpoint that reports broker + DB status.

This is the smallest end-to-end slice. The full design (multi-customer, per-machine-type
tables, status cache, commands, metrics, auth) is in
`/root/.claude/plans/with-python-we-need-logical-pinwheel.md` as a roadmap.

## Prerequisites

- Python 3.11+
- Mosquitto broker reachable on `MQTT_HOST:MQTT_PORT` (defaults to `localhost:1883`).
  On Windows, install via the Eclipse Mosquitto installer; on Linux/macOS, `apt install
  mosquitto` / `brew install mosquitto`.
- MS SQL Server reachable via the connection string in `.env`.
- **Microsoft ODBC Driver 18 for SQL Server** installed on the host running this
  app — required by `aioodbc`. Install instructions:
  <https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server>.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate                  # or .venv\Scripts\activate on Windows
pip install -e .

cp .env.example .env                       # then edit MSSQL_CONN_STR etc.
```

Create the table:

```bash
sqlcmd -S <server> -d mqtt_sql -i scripts/sql_init.sql
```

## Run

```bash
python -m mqtt_sql.main
# or, after `pip install -e .`:
mqtt-sql
```

## Smoke test

1. `curl http://localhost:8000/health` → `{"status":"ok","broker":"connected","db":"ok"}`.
2. Publish a test message:

   ```bash
   python scripts/mqtt_pub_sample.py devices/hello '{"msg":"world"}'
   ```

3. Query the table — a new row should appear:

   ```sql
   SELECT TOP 5 * FROM dbo.messages ORDER BY id DESC;
   ```

4. Stop Mosquitto and hit `/health` again → `503` with `"broker":"down"`.

## Project layout

```
MQTT_SQL/
├── pyproject.toml
├── .env.example
├── deploy/mosquitto.conf
├── scripts/
│   ├── sql_init.sql
│   └── mqtt_pub_sample.py
└── src/mqtt_sql/
    ├── config.py            # pydantic-settings
    ├── db.py                # SQLAlchemy async engine + insert_message
    ├── mqtt_subscriber.py   # aiomqtt subscriber loop with auto-reconnect
    └── main.py              # FastAPI app + /health
```

## What's intentionally missing in v0.1

No customers, no devices registry, no per-machine-type parsing, no status cache,
no commands, no metrics, no auth. Those land in v0.2+ — see the roadmap in the
plan file.
