"""
Database engine and session factory.

DATABASE_URL selects the dialect. Postgres is the deployed target; SQLite is
the zero-infrastructure local-venv path. Both are supported, which is why
nothing in this module emits dialect-specific DDL any more — Alembic owns the
schema (`alembic upgrade head`), and `migrations/` is the only place a column
is defined.
"""

import logging

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from sqlalchemy import event

from config import settings

logger = logging.getLogger(__name__)

IS_SQLITE = settings.DATABASE_URL.startswith("sqlite")

# Postgres gets a real pool: the API runs N uvicorn workers and the workflow
# worker runs activities concurrently, so connections are the contended
# resource. pool_pre_ping costs one round-trip per checkout and buys immunity
# to connections severed by an idle timeout between the app and the database.
_engine_kwargs: dict = {"echo": settings.DEBUG}
if IS_SQLITE:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    _engine_kwargs.update(
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=1800,
    )

engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)


@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if IS_SQLITE:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        # Without this a concurrent writer fails instantly with "database is
        # locked" rather than waiting for the writer holding the lock.
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()


AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

Base = declarative_base()


async def init_db():
    """
    Bring the schema up on a local SQLite debug run only.

    Everywhere else `alembic upgrade head` runs first (entrypoint.sh in Docker,
    documented in the README for a venv) and this is a no-op. The previous
    implementation issued a block of raw ALTER TABLE statements wrapped in
    `except: pass` — SQLite-dialect DDL that could not run on Postgres, and
    that on Postgres would poison the surrounding transaction after the first
    failure, silently skipping every statement after it.
    """
    # Import every model module so create_all sees the full metadata.
    from db import models  # noqa: F401

    if not (settings.DEBUG and IS_SQLITE):
        logger.info(
            "[DB] Schema is managed by Alembic — run `alembic upgrade head` before starting."
        )
        return

    logger.warning(
        "[DB] DEBUG + SQLite: creating tables directly from model metadata. "
        "This is a convenience for local runs; Alembic remains the source of truth."
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def init_claim_tables():
    """
    Retained so existing callers keep working. Claim models live on the same
    Base as everything else, so init_db() already covers them.
    """
    return await init_db()


async def ping() -> bool:
    """True when the database answers. Backs GET /ready."""
    from sqlalchemy import text as _text
    try:
        async with engine.connect() as conn:
            await conn.execute(_text("SELECT 1"))
        return True
    except Exception as e:
        logger.warning(f"[DB] Ping failed: {e}")
        return False
