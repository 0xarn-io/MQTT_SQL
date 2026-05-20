"""Application configuration, loaded from environment variables or a `.env` file.

Pydantic-settings reads the env vars (case-insensitively) and falls back to
the named defaults below. `mssql_conn_str` is the only required value; without
it the process refuses to start, which is what we want — silently writing to
the wrong database is worse than a loud startup failure.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # MQTT broker on the same host (loopback). The Python service talks plain
    # MQTT here; the broker's WebSocket listener on a separate port handles
    # external device traffic and is not used by this app.
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883

    # Full ODBC connection string for SQL Server. Required — no sensible
    # default. Example:
    #   Driver={ODBC Driver 18 for SQL Server};Server=localhost;
    #   Database=mqtt_sql;Trusted_Connection=yes;Encrypt=no
    mssql_conn_str: str

    # Where the FastAPI app listens. 0.0.0.0 is fine on a dedicated server;
    # if the box is multi-tenant, lock to 127.0.0.1 and put a reverse proxy
    # in front.
    http_host: str = "0.0.0.0"
    http_port: int = 8000

    # Python logging level for the app's own loggers (uvicorn's access log
    # uses the lowercased form of this).
    log_level: str = "INFO"


settings = Settings()
