import os
import logging
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text

log = logging.getLogger("db")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///data/monitor.db")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://") and "+asyncpg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

connect_args = {}
if "sqlite" in DATABASE_URL:
    connect_args = {"check_same_thread": False}

engine = create_async_engine(DATABASE_URL, echo=False, connect_args=connect_args)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        yield session


_TABLE_COLUMN_DEFAULTS = {
    "users": {
        "notify_slack": "BOOLEAN DEFAULT FALSE",
        "slack_webhook_url": "VARCHAR(500)",
        "notify_discord": "BOOLEAN DEFAULT FALSE",
        "discord_webhook_url": "VARCHAR(500)",
        "custom_webhooks": "TEXT",
        "language": "VARCHAR(5) DEFAULT 'en'",
    }
}


async def _ensure_columns(conn, table: str, columns: dict):
    is_sqlite = "sqlite" in DATABASE_URL
    if is_sqlite:
        result = await conn.execute(text(f"PRAGMA table_info({table})"))
        existing = {row[1] for row in result.fetchall()}
    else:
        result = await conn.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name = :t"
        ), {"t": table})
        existing = {row[0] for row in result.fetchall()}

    for col_name, col_def in columns.items():
        if col_name not in existing:
            sql = f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}"
            log.info("Migration: %s", sql)
            await conn.execute(text(sql))


async def init_db():
    if "sqlite" in DATABASE_URL:
        os.makedirs("data", exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for table, columns in _TABLE_COLUMN_DEFAULTS.items():
            try:
                await _ensure_columns(conn, table, columns)
            except Exception as e:
                log.warning("Migration skip for %s: %s", table, e)
