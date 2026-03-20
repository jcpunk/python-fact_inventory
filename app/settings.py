"""
Load application configuration from environment variables and .env files.

Set the RUNTIME environment variable to select `.env.${RUNTIME}`;
defaults to the ``testing`` environment when unset.

All configuration is exposed through the module-level ``settings`` instance.
Consumers should import and use that object directly::

    from .settings import settings
    uri = settings.database_uri

Configurable elements (production):
  - DATABASE_URI: str          (required)
  - APP_NAME: str              (default "fact_inventory")
  - RATE_LIMIT_MINUTES: int    (default 27)
  - CREATE_ALL: bool           (default True)
  - DB_POOL_SIZE: int          (default 10)
  - DB_POOL_MAX_OVERFLOW: int  (default 20)
  - DB_POOL_TIMEOUT: int       (default 30)
  - LOG_LEVEL: str             (default "INFO"; overridden to "DEBUG" when DEBUG=true)
  - DEBUG: bool                (default False)
  - VERSION: str               (default: package metadata for APP_NAME → git commit →
                                "unknown")

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
from typing import Self

from litestar.logging import LoggingConfig
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

RUNTIME = os.getenv("RUNTIME", "testing")
_ENV_FILE = Path(f".env.{RUNTIME}")


def _get_version() -> str:
    """Determine the application version via three fallback sources.

    1. Installed package metadata (``importlib.metadata``).
    2. Current git commit short-hash (``git rev-parse --short HEAD``).
    3. The literal string ``"unknown"``.
    """
    with contextlib.suppress(PackageNotFoundError):
        return _package_version("fact-inventory")

    git = shutil.which("git")
    if git is not None:
        with contextlib.suppress(subprocess.CalledProcessError):
            # All arguments are controlled: `git` is a fully-resolved path from
            # shutil.which() and the remaining args are literals, so there is no
            # untrusted input here.  S603 is suppressed accordingly.
            result = subprocess.run(  # noqa: S603
                [git, "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            )
            return f"git-{result.stdout.strip()}"

    return "unknown"


# ----------------------------------------------------------------------
# Settings model — reads from environment and .env file
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
    rate_limit_minutes: int = 27
    create_all: bool = True
    db_pool_size: int = 10
    db_pool_max_overflow: int = 20
    db_pool_timeout: int = 30
    log_level: str = "INFO"
    debug: bool = False
    version: str = Field(default_factory=_get_version)

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
# Logging infrastructure — built from the resolved settings and applied
# immediately so every module-level logger created at import time
# (including this one) uses the correct level, handler, and formatter.
# ----------------------------------------------------------------------
logging_config = LoggingConfig(
    root={"level": logging.getLevelName(settings.log_level), "handlers": ["console"]},
    formatters={
        "standard": {"format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"}
    },
)
logging_config.configure()

logger = logging.getLogger(__name__)
