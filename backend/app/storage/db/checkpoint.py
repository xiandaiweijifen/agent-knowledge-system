"""
Postgres-backed LangGraph checkpoint saver.

Initialised once at application startup via the FastAPI lifespan.
The saver instance is stored on `app.state.checkpointer` for use by
LangGraph graphs in later packages.

If DATABASE_URL is not configured the module is a no-op so that the
existing test suite (which runs without Postgres) is unaffected.
"""

import asyncio
import inspect
import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool, ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

# psycopg3 async requires SelectorEventLoop on Windows.
# uvicorn sets this automatically; this guard covers scripts and tests.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

logger = logging.getLogger(__name__)


def _normalize_url(database_url: str) -> str:
    """Convert SQLAlchemy-style URL to plain psycopg3 connstring."""
    return database_url.replace("postgresql+psycopg2", "postgresql")


async def _run_setup(conn_str: str) -> None:
    """
    Run AsyncPostgresSaver.setup() using a dedicated autocommit connection.
    CREATE INDEX CONCURRENTLY cannot run inside a transaction block, so this
    must NOT go through the shared pool.
    """
    async with await psycopg.AsyncConnection.connect(
        conn_str, autocommit=True
    ) as conn:
        await AsyncPostgresSaver(conn).setup()


def _build_sync_checkpointer(
    conn_str: str,
) -> tuple[PostgresSaver, ConnectionPool] | tuple[None, None]:
    """
    Windows-friendly sync fallback for psycopg/LangGraph checkpointing.
    This avoids psycopg async's ProactorEventLoop incompatibility.
    """
    with psycopg.Connection.connect(
        conn_str, autocommit=True, prepare_threshold=0, row_factory=dict_row
    ) as conn:
        PostgresSaver(conn).setup()
    logger.info("LangGraph checkpoint tables ready")

    pool = ConnectionPool(conninfo=conn_str, max_size=10, open=True)
    checkpointer = PostgresSaver(pool)
    logger.info("Postgres checkpointer ready (sync fallback)")
    return checkpointer, pool


async def build_checkpointer(
    database_url: str,
) -> tuple[object, object] | tuple[None, None]:
    """
    1. Run setup() via an autocommit connection (idempotent DDL).
    2. Open a connection pool for runtime use.
    3. Return (AsyncPostgresSaver, pool) so the caller can close the pool on shutdown.

    Returns (None, None) when database_url is empty or on any error.
    """
    if not database_url:
        logger.info("DATABASE_URL not set — Postgres checkpointer disabled")
        return None, None

    conn_str = _normalize_url(database_url)

    try:
        if sys.platform == "win32":
            return _build_sync_checkpointer(conn_str)

        await _run_setup(conn_str)
        logger.info("LangGraph checkpoint tables ready")

        pool = AsyncConnectionPool(conninfo=conn_str, max_size=10, open=False)
        await pool.open()

        checkpointer = AsyncPostgresSaver(pool)
        logger.info("Postgres checkpointer ready")
        return checkpointer, pool

    except Exception as exc:
        logger.warning("Postgres checkpointer init failed: %s", exc)
        return None, None


@asynccontextmanager
async def checkpointer_lifespan(
    database_url: str,
) -> AsyncGenerator[object | None, None]:
    """
    Async context manager for use inside FastAPI lifespan.
    Yields the checkpointer (or None if Postgres is unavailable).
    """
    checkpointer, pool = await build_checkpointer(database_url)
    try:
        yield checkpointer
    finally:
        if pool is not None:
            close_result = pool.close()
            if inspect.isawaitable(close_result):
                await close_result
            logger.info("Postgres connection pool closed")
