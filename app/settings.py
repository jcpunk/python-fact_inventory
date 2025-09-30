"""
Load application configs from dotenv.

setenv RUNTIME to select .env.${RUNTIME}
or you will get the `testing` environment

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

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from litestar.logging import LoggingConfig

# ----------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------
__TRUE_SET = {"true", "yes", "y", "on", "1"}
NAME = "fact_inventory"

# ----------------------------------------------------------------------
# Runtime environment handling
# ----------------------------------------------------------------------
RUNTIME = os.getenv("RUNTIME", "testing")
ENV_FILE = Path(f".env.{RUNTIME}")

if ENV_FILE.is_file():
    load_dotenv(ENV_FILE, override=True)
    print(f"Loaded environment configuration from: {ENV_FILE}")
else:
    print(f"No .env file for {RUNTIME!s} ({ENV_FILE}) - trying defaults")

DEBUG = os.getenv("DEBUG", "false").strip().casefold() in __TRUE_SET

if DEBUG:  # debug mode always has debug logs
    os.environ["LOG_LEVEL"] = "DEBUG"

# ----------------------------------------------------------------------
# Core configuration values (can be overridden in the .env file)
# ----------------------------------------------------------------------

DATABASE_URI = os.getenv("DATABASE_URI")  # required at runtime
if not DATABASE_URI:
    raise RuntimeError("DATABASE_URI environment variable is required")  # noqa: TRY003

RATE_LIMIT_MINUTES = int(os.getenv("RATE_LIMIT_MINUTES", "27"))

CREATE_ALL = os.getenv("CREATE_ALL", "true").strip().casefold() in __TRUE_SET

DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))
DB_POOL_MAX_OVERFLOW = int(os.getenv("DB_POOL_MAX_OVERFLOW", "20"))
DB_POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))

ALLOWED_ORIGINS: list[str] = [
    o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()
]

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# ----------------------------------------------------------------------
# Logging configuration setup
# ----------------------------------------------------------------------
logging_config = LoggingConfig(
    root={"level": logging.getLevelName(LOG_LEVEL), "handlers": ["console"]},
    formatters={
        "standard": {"format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"}
    },
)

logger = logging.getLogger(__name__)
