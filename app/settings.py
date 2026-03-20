"""
Load application configuration from environment variables and .env files.

Set the RUNTIME environment variable to select `.env.${RUNTIME}`;
defaults to the ``testing`` environment when unset.

Configurable elements (production):
  - DATABASE_URI: str
  - RATE_LIMIT_MINUTES: int
  - CREATE_ALL: bool
  - DB_POOL_SIZE: int
  - DB_POOL_MAX_OVERFLOW: int
  - DB_POOL_TIMEOUT: int
  - ALLOWED_ORIGINS: str (comma-separated)
  - LOG_LEVEL: str
  - DEBUG: bool

Additional Configurable elements (for development with uvicorn):
  - HOST: str = see main.py
  - PORT: int = see main.py
"""

from __future__ import annotations

import logging
import os
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from litestar.logging import LoggingConfig
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# ----------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------
NAME = "fact_inventory"

try:
    VERSION: str = version("fact-inventory")
except PackageNotFoundError:
    VERSION = "0.0.0+unknown"

RUNTIME = os.getenv("RUNTIME", "testing")
_ENV_FILE = Path(f".env.{RUNTIME}")


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

    database_uri: str = Field(...)  # required — no default
    rate_limit_minutes: int = 27
    create_all: bool = True
    db_pool_size: int = 10
    db_pool_max_overflow: int = 20
    db_pool_timeout: int = 30
    allowed_origins: list[str] = []
    log_level: str = "INFO"
    debug: bool = False

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> list[str]:
        """Accept a comma-separated string or a list of strings."""
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        if isinstance(v, list):
            return [str(item) for item in v]
        msg = f"allowed_origins must be a string or list, got {type(v).__name__}"
        raise TypeError(msg)


_settings = Settings()

# ----------------------------------------------------------------------
# Module-level exports used throughout the application
# ----------------------------------------------------------------------
DATABASE_URI: str = _settings.database_uri
RATE_LIMIT_MINUTES: int = _settings.rate_limit_minutes
CREATE_ALL: bool = _settings.create_all
DB_POOL_SIZE: int = _settings.db_pool_size
DB_POOL_MAX_OVERFLOW: int = _settings.db_pool_max_overflow
DB_POOL_TIMEOUT: int = _settings.db_pool_timeout
ALLOWED_ORIGINS: list[str] = _settings.allowed_origins
DEBUG: bool = _settings.debug

# DEBUG mode always uses DEBUG-level logging.
LOG_LEVEL: str = "DEBUG" if DEBUG else _settings.log_level

# ----------------------------------------------------------------------
# Logging configuration
# ----------------------------------------------------------------------
logging_config = LoggingConfig(
    root={"level": logging.getLevelName(LOG_LEVEL), "handlers": ["console"]},
    formatters={
        "standard": {"format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"}
    },
)

logger = logging.getLogger(__name__)
