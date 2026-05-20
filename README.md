# mqtt_sql — v0.1 "hello world"

A tiny Python service that:

1. subscribes to an MQTT broker on `devices/#`,
2. drops every message verbatim (topic + raw payload) into a single MS SQL Server table,
3. exposes a `GET /health` endpoint that reports broker + DB status.

This is the smallest end-to-end slice. The full design (multi-customer, per-machine-type
tables, status cache, commands, metrics, auth) is in the project plan as a roadmap.

## Architecture

```
device ──wss://...──> Cloudflare Worker ──> Mosquitto WebSocket listener ─┐
                                                                          │
                                                                  broker bus
                                                                          │
mqtt_sql (this app) ──MQTT loopback subscribe──> insert into dbo.messages
                  ──GET /health──> reports broker + db status
```

## Prerequisites

- **Python 3.11+** (tested through 3.14)
- **Mosquitto broker** reachable on `MQTT_HOST:MQTT_PORT` (defaults to `localhost:1883`).
  On Windows, install via the Eclipse Mosquitto installer; on Linux/macOS, `apt install
  mosquitto` / `brew install mosquitto`.
- **MS SQL Server** reachable via the connection string in `.env`.
- **Microsoft ODBC Driver 18 for SQL Server** installed on the host running this
  app — required by `aioodbc`:
  <https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server>.
  On Linux dev boxes also `apt install unixodbc`.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate                  # or .venv\Scripts\Activate.ps1 on Windows
pip install -e .

cp .env.example .env                       # then edit MSSQL_CONN_STR etc.
```

Create the database and table:

```bash
sqlcmd -S <server> -E -C -Q "IF DB_ID('mqtt_sql') IS NULL CREATE DATABASE mqtt_sql"
sqlcmd -S <server> -d mqtt_sql -E -C -i scripts/sql_init.sql
```

The `-C` flag tells `sqlcmd` to trust the server's self-signed TLS cert
(ODBC Driver 18 verifies by default and fails on the local instance's
self-signed cert).

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
    ├── config.py            # env-driven settings (pydantic-settings)
    ├── db.py                # async SQLAlchemy engine + insert/health helpers
    ├── mqtt_subscriber.py   # subscribe loop with exponential-backoff reconnect
    └── main.py              # FastAPI app + /health + Windows-aware event loop
```

## Notes from running on Windows Server (gotchas)

- **Mosquitto password file ACLs.** `mosquitto_passwd.exe -c …\passwd device1`
  creates the file owned by Administrator with no read access for
  `NT AUTHORITY\SYSTEM`. The service runs as LocalSystem, so it silently
  fails to start (no Windows event, no log file written). Fix after every
  password change:
  ```powershell
  icacls "C:\ProgramData\mosquitto\passwd" /grant "NT AUTHORITY\SYSTEM:R"
  ```

- **SelectorEventLoop on Windows.** `paho-mqtt` (under `aiomqtt`) calls
  `loop.add_reader` / `add_writer`, which `ProactorEventLoop` (the Windows
  default) doesn't implement. `uvicorn.run()` forces a Proactor policy
  internally, so we drive `uvicorn.Server.serve()` ourselves via
  `asyncio.Runner(loop_factory=asyncio.SelectorEventLoop)` (see
  `main.py::main`).

- **ODBC Driver 18 cert validation.** Driver 18 defaults to encrypted
  connections with strict cert checking. SQL Server's self-signed cert
  fails this. Either add `Encrypt=no` to the connection string (simplest
  for local) or `Encrypt=yes;TrustServerCertificate=yes` to keep TLS on.

- **Cloudflare Worker `fetch()` to origins.** Workers reject WebSocket
  subrequests to raw IPs — the target must be a hostname. Any DNS name
  resolving to the server works (the hosting provider's
  `<uuid>.clouding.host` is enough); no domain registration needed for
  testing.

## What's intentionally missing in v0.1

No customers, no devices registry, no per-machine-type parsing, no status cache,
no commands, no metrics, no auth on the FastAPI side. Those land in v0.2+ —
see the roadmap in the project plan.
