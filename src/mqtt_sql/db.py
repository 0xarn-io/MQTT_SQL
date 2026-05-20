import urllib.parse

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from .config import settings


def _build_url(odbc_conn_str: str) -> str:
    return f"mssql+aioodbc:///?odbc_connect={urllib.parse.quote_plus(odbc_conn_str)}"


engine: AsyncEngine = create_async_engine(
    _build_url(settings.mssql_conn_str),
    pool_pre_ping=True,
    pool_recycle=1800,
)


async def insert_message(topic: str, payload: str) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO dbo.messages (topic, payload) VALUES (:topic, :payload)"),
            {"topic": topic, "payload": payload},
        )


async def check_db() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
