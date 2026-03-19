"""
Internal background task for data retention.

Periodically calls the ``purge_stale_host_facts`` stored procedure that
the application creates on PostgreSQL (see models.py).  The task runs
entirely inside the process — no HTTP endpoint is exposed and no
external scheduler (cron, pg_cron) is required.

The task is a no-op when:
  - RETENTION_DAYS is 0 (disabled)
  - The database is not PostgreSQL (the stored procedure only exists there)
"""

import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from ..settings import DATABASE_URI, RETENTION_DAYS

logger = logging.getLogger(__name__)

#: How often the purge runs (in seconds).  24 hours.
_PURGE_INTERVAL_SECONDS = 60 * 60 * 24


def _is_postgresql() -> bool:
    """Return True when the configured database is PostgreSQL."""
    return DATABASE_URI is not None and DATABASE_URI.startswith(
        ("postgresql", "postgres")
    )


async def _retention_loop() -> None:
    """Run the purge stored procedure on a fixed interval."""
    engine = create_async_engine(DATABASE_URI)  # type: ignore[arg-type]
    try:
        while True:
            try:
                async with engine.connect() as conn:
                    await conn.execute(
                        text("SELECT purge_stale_host_facts(:days)"),
                        {"days": RETENTION_DAYS},
                    )
                    await conn.commit()
                logger.info(
                    "Retention purge completed (retention_days=%d)", RETENTION_DAYS
                )
            except Exception:
                logger.exception("Retention purge failed")

            await asyncio.sleep(_PURGE_INTERVAL_SECONDS)
    except asyncio.CancelledError:
        logger.info("Retention task cancelled")
    finally:
        await engine.dispose()


def start_retention_task() -> asyncio.Task[None] | None:
    """Start the background retention task if configured.

    Returns the :class:`asyncio.Task` so the caller can cancel it on
    shutdown, or ``None`` when retention is disabled.
    """
    if RETENTION_DAYS <= 0:
        logger.info("Retention policy disabled (RETENTION_DAYS=0)")
        return None

    if not _is_postgresql():
        logger.warning(
            "Retention task requires PostgreSQL; skipping for current database"
        )
        return None

    logger.info(
        "Starting retention task (purge records older than %d days, interval %ds)",
        RETENTION_DAYS,
        _PURGE_INTERVAL_SECONDS,
    )
    return asyncio.create_task(_retention_loop())
