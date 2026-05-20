"""Async SQL Server access via SQLAlchemy + aioodbc.

Two public functions:
- `insert_message(topic, payload)` writes one row to `dbo.messages`.
- `check_db()` runs a cheap `SELECT 1` for the `/health` endpoint and never raises.

The engine is created at module import time so that a misconfigured connection
string fails fast rather than at first message.
"""

import logging
import urllib.parse

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from .config import settings

log = logging.getLogger(__name__)

# Pool tuning. pool_pre_ping issues a tiny SELECT 1 before handing out a
# pooled connection, transparently recovering from server restarts and
# idle-timeout disconnects. pool_recycle forces a fresh connection every
# 30 minutes to avoid stale TCP sockets that some network gear silently
# drops after long idle periods.
_POOL_PRE_PING = True
_POOL_RECYCLE_SECONDS = 1800


def _build_url(odbc_conn_str: str) -> str:
    """Wrap a raw ODBC connection string in the SQLAlchemy `mssql+aioodbc` URL form.

    The `mssql+aioodbc` dialect does not parse individual keyword arguments;
    it expects the full ODBC string passed through the `odbc_connect` URL
    parameter (URL-encoded). This helper hides that quirk.
    """
    return f"mssql+aioodbc:///?odbc_connect={urllib.parse.quote_plus(odbc_conn_str)}"


engine: AsyncEngine = create_async_engine(
    _build_url(settings.mssql_conn_str),
    pool_pre_ping=_POOL_PRE_PING,
    pool_recycle=_POOL_RECYCLE_SECONDS,
)


async def insert_message(topic: str, payload: str) -> None:
    """Insert a single message into `dbo.messages`.

    Raises `SQLAlchemyError` on database failures; the caller is expected to
    log and continue rather than tear down the subscriber.
    """
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO dbo.messages (topic, payload) VALUES (:topic, :payload)"),
            {"topic": topic, "payload": payload},
        )


async def check_db() -> bool:
    """Return True if a simple query succeeds, False otherwise.

    Catches only SQLAlchemy errors so that genuine bugs (e.g. import-time
    failures) still surface. Used by the `/health` endpoint, which must
    never raise.
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError as e:
        log.warning("DB health check failed: %s", e)
        return False
