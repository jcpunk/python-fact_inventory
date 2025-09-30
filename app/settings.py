"""
Load application configuration from environment variables and .env files.

Set the RUNTIME environment variable to select ``.env.${RUNTIME}``;
defaults to the ``testing`` environment when unset.

All configuration is exposed through the module-level ``settings`` instance.
Consumers should import and use that object directly::

    from .settings import settings
    uri = settings.database_uri

Configurable elements (production):
  - DATABASE_URI: str              (required)
  - APP_NAME: str                  (default "fact_inventory")
  - RATE_LIMIT_UNIT: str           (default "hour"; second/minute/hour/day)
  - RATE_LIMIT_MAX_REQUESTS: int   (default 2)
  - RETENTION_DAYS: int            (default 365)
  - CLEANUP_INTERVAL_HOURS: int    (default 24)
  - CLEANUP_JITTER_MINUTES: int    (default 20; max random offset per cycle)
  - CREATE_ALL: bool               (default True)
  - DB_POOL_SIZE: int              (default 10)
  - DB_POOL_MAX_OVERFLOW: int      (default 20)
  - DB_POOL_TIMEOUT: int           (default 30)
  - LOG_LEVEL: str                 (default "INFO"; overridden to "DEBUG"
                                    when DEBUG=true)
  - DEBUG: bool                    (default False)
  - VERSION: str                   (default: package metadata,
                                    then git commit, then "unknown")

Additional configurable elements (for development with uvicorn):
  - HOST: str = see main.py
  - PORT: int = see main.py
"""

import contextlib
import logging
import os
import shutil
import subprocess
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _package_version
from pathlib import Path
from typing import Literal, Self

from litestar.logging import LoggingConfig
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

RUNTIME = os.getenv("RUNTIME", "testing")
_ENV_FILE = Path(f".env.{RUNTIME}")

#: Valid values for :attr:`Settings.rate_limit_unit`.
DurationUnit = Literal["second", "minute", "hour", "day"]


def _get_version(package_name: str) -> str:
    """Determine the application version via three fallback sources.

    1. Installed package metadata (``importlib.metadata``) for *package_name*.
    2. Current git commit short-hash (``git rev-parse --short HEAD``).
    3. The literal string ``"unknown"``.
    """
    _log = logging.getLogger(__name__)

    with contextlib.suppress(PackageNotFoundError):
        return _package_version(package_name)

    _log.debug(
        "Package metadata not found for %r; falling back to git commit hash",
        package_name,
    )

    git = shutil.which("git")
    if git is None:
        _log.debug("git not found on PATH; version will be reported as 'unknown'")
        return "unknown"

    try:
        # All arguments are controlled: `git` is a fully-resolved path from
        # shutil.which() and the remaining args are literals, so there is no
        # untrusted input here.  S603 is suppressed accordingly.
        result = subprocess.run(  # noqa: S603
            [git, "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return f"git-{result.stdout.strip()}"
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        _log.debug("git rev-parse failed; cannot fall back to commit hash")

    return "unknown"


# ----------------------------------------------------------------------
# Settings model - reads from environment and .env file
# ----------------------------------------------------------------------
class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    database_uri: str = Field(...)
    app_name: str = "fact_inventory"
    rate_limit_unit: DurationUnit = "hour"
    rate_limit_max_requests: int = Field(default=2, ge=1)
    retention_days: int = Field(default=365, ge=1)
    cleanup_interval_hours: int = Field(default=24, ge=1)
    cleanup_jitter_minutes: int = Field(default=20, ge=0)
    create_all: bool = True
    db_pool_size: int = Field(default=10, ge=1)
    db_pool_max_overflow: int = Field(default=20, ge=0)
    db_pool_timeout: int = Field(default=30, ge=1)
    log_level: str = "INFO"
    debug: bool = False
    version: str = "unknown"

    @model_validator(mode="after")
    def _resolve_version(self) -> Self:
        """Try to resolve version from package metadata using app_name."""
        if self.version == "unknown":
            self.version = _get_version(self.app_name)
        return self

    @model_validator(mode="after")
    def _apply_debug_log_level(self) -> Self:
        """Force log_level to DEBUG whenever debug mode is enabled."""
        if self.debug:
            self.log_level = "DEBUG"
        return self


# ----------------------------------------------------------------------
# Application-wide settings singleton
# ----------------------------------------------------------------------
settings = Settings()

# ----------------------------------------------------------------------
# Logging infrastructure
#
# The LoggingConfig object is passed to Litestar via the "logging_config"
# kwarg; Litestar calls .configure() during app startup.  We deliberately
# do NOT call .configure() here at import time: doing so would install a
# StreamHandler on the root logger as a side-effect of importing this
# module, which poisons pytest's stream-capture context and causes
# "ValueError: I/O operation on closed file" on Python 3.14 when
# aiosqlite's background worker thread outlives the event loop.
#
# aiosqlite is pinned to WARNING even when the root level is DEBUG because
# its messages ("executing ...", "operation ... completed") describe
# internal connection-worker plumbing that is not useful to application
# developers.  All other loggers inherit the root level.
# ----------------------------------------------------------------------
logging_config = LoggingConfig(
    root={"level": logging.getLevelName(settings.log_level), "handlers": ["console"]},
    formatters={
        "standard": {"format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"}
    },
    loggers={
        "aiosqlite": {"level": "WARNING", "handlers": ["console"], "propagate": False},
    },
)
