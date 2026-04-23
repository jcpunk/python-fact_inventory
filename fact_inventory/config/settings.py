"""Application configuration from environment variables and .env files.

Loads application configuration from environment variables and .env files.
Set the DEPLOYMENT environment variable to select .env.${DEPLOYMENT};
defaults to the testing environment when unset.

Notes
-----
All configuration is exposed through the module-level settings instance.
Consumers should import and use that object directly:

    from fact_inventory.config.settings import settings

    uri = settings.database_uri
    app_name = settings.app_name

Configuration is sourced from environment variables with optional override
from .env files. The following configuration parameters are supported:

**Application Identity**

APP_NAME
    Application name used in logs and OpenAPI documentation.
    Default: "fact_inventory".

VERSION
    Application version from package metadata, git commit, or fallback.
    Default: "unknown".

DEPLOYMENT
    Selects .env.{DEPLOYMENT} file and sets deployment.environment.
    Default: "testing". Valid: any string identifier.

**Database & Connection Pooling**

DATABASE_URI
    The database connection string (required). Default: None.

DB_POOL_SIZE
    The database connection pool size. Default: 10. Valid: >=1.

DB_POOL_MAX_OVERFLOW
    Maximum connections beyond pool size. Default: 20. Valid: >=0.

DB_POOL_TIMEOUT
    Seconds to wait for a connection from the pool. Default: 30. Valid: >=1.

CREATE_ALL
    Automatically create database tables on startup. Default: True.

**Rate Limiting**

RATE_LIMIT_UNIT
    Unit over which requests are rate limited. Default: "hour".
    Valid: "day", "hour", "minute", "second".

RATE_LIMIT_MAX_REQUESTS
    Maximum requests allowed within the rate limit window. Default: 2.
    Valid: >=1.

**Data Retention & Cleanup**

ENABLE_RETENTION_CLEANUP_JOB
    Enable the retention cleanup background job. Default: True.

RETENTION_DAYS
    Days before a record expires. Default: 400. Valid: >=1.

RETENTION_CHECK_INTERVAL_HOURS
    Hours between successive retention checks. Default: 20. Valid: >=1.

RETENTION_CHECK_JITTER_MINUTES
    Maximum random offset (minutes) added to each retention check sleep cycle.
    Default: 200. Valid: >=0.

ENABLE_HISTORY_CLEANUP_JOB
    Enable the history cleanup background job. Default: True.

HISTORY_CHECK_INTERVAL_HOURS
    Hours between successive history cleanup checks. Default: 20. Valid: >=1.

HISTORY_MAX_ENTRIES
    Maximum fact records to keep per client_address. Oldest records are
    deleted when exceeded. Default: 5. Valid: >=1.

HISTORY_CHECK_JITTER_MINUTES
    Maximum random offset (minutes) added to each history cleanup sleep cycle.
    Default: 200. Valid: >=0.

**Payload Constraints**

MAX_JSON_FIELD_MB
    Maximum size (MB) for a single JSON field. Default: 4. Valid: >=1.

MAX_REQUEST_BODY_MB
    Maximum total HTTP request body size (MB) enforced at the HTTP layer.
    Default: 13. Valid: > 3 x MAX_JSON_FIELD_MB.

**Logging & Observability**

DEBUG
    Enable debug mode (forces LOG_LEVEL to DEBUG and enables OpenAPI docs).
    Default: False.

LOG_LEVEL
    Minimum log level to emit. Default: "INFO".
    Valid: "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL".

ENABLE_METRICS
    Enable Prometheus /metrics endpoint and middleware. OpenTelemetry
    tracing is always active. Default: True.

**Health & Readiness Probes**

ENABLE_HEALTH_ENDPOINT
    Enable /health liveness probe endpoint. Default: True.

ENABLE_READY_ENDPOINT
    Enable /ready readiness probe endpoint. Default: True.

**Development Server (uvicorn)**

HOST
    Host to bind to. Default: "localhost".

PORT
    Port to bind to. Default: 8000.
"""

import contextlib
import os
import shutil
import subprocess
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _package_version
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from fact_inventory.domain.constraints import JSONFieldSizeConstraint

__all__ = ["settings"]

DEPLOYMENT = os.getenv("DEPLOYMENT", "testing")
_ENV_FILE = Path(f".env.{DEPLOYMENT}")

#: Valid values for Settings.rate_limit_unit field.
DurationUnit = Literal["second", "minute", "hour", "day"]


def _get_version(package_name: str) -> str:
    """Determine the application version from installed package metadata or git.

    Attempts to resolve version from three sources in priority order:

    1. Installed package metadata (importlib.metadata)
    2. Current git commit short-hash (git rev-parse --short HEAD)
    3. Fallback literal string "unknown"

    Parameters
    ----------
    package_name : str
        Name of the installed package to query for version metadata.

    Returns
    -------
    str
        Version string from metadata, git commit hash, or "unknown" fallback.
    """
    with contextlib.suppress(PackageNotFoundError):
        return _package_version(package_name)

    git = shutil.which("git")
    if git is None:
        return "unknown"

    try:
        result = subprocess.run(  # noqa: S603
            [git, "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return f"git-{result.stdout.strip()}"
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return "git-unknown"


# ----------------------------------------------------------------------
# Settings model - reads from environment and .env file
# ----------------------------------------------------------------------
class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file.

    See fact_inventory/config/settings.py module docstring for the complete
    list of configuration parameters and their defaults.
    """

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "fact_inventory"
    version: str = "unknown"
    deployment_environment: str = Field(default=DEPLOYMENT, alias="DEPLOYMENT")

    database_uri: str = Field(...)
    db_pool_size: int = Field(default=10, ge=1)
    db_pool_max_overflow: int = Field(default=20, ge=0)
    db_pool_timeout: int = Field(default=30, ge=1)
    create_all: bool = True

    rate_limit_unit: DurationUnit = "hour"
    rate_limit_max_requests: int = Field(default=2, ge=1)

    enable_retention_cleanup_job: bool = True
    retention_days: int = Field(default=400, ge=1)
    retention_check_interval_hours: int = Field(default=20, ge=1)
    retention_check_jitter_minutes: int = Field(default=200, ge=0)

    enable_history_cleanup_job: bool = True
    history_check_interval_hours: int = Field(default=20, ge=1)
    history_max_entries: int = Field(default=5, ge=1)
    history_check_jitter_minutes: int = Field(default=200, ge=0)

    max_json_field_mb: int = Field(default=4, ge=1)
    max_request_body_mb: int = Field(default=13, ge=1)

    debug: bool = False
    log_level: str = "INFO"

    enable_metrics: bool = True
    enable_health_endpoint: bool = True
    enable_ready_endpoint: bool = True

    @model_validator(mode="after")
    def _check_body_size(self) -> Self:
        """Verify the request body limit can hold the JSON fields and envelope.

        The request body must be strictly larger than the JSON fields combined
        so there is room for the surrounding JSON envelope and other request
        overhead. Requiring max_request_body_mb > N * max_json_field_mb preserves
        this invariant regardless of the chosen field size, where N is the number
        of JSON field names defined in JSONFieldSizeConstraint.

        Returns
        -------
        Self
            The validated Settings instance.

        Raises
        ------
        ValueError
            If max_request_body_mb is not greater than N x max_json_field_mb.
        """
        num_json_fields = len(JSONFieldSizeConstraint.JSON_FIELD_NAMES)
        if self.max_request_body_mb <= num_json_fields * self.max_json_field_mb:
            raise ValueError(  # noqa: TRY003
                f"max_request_body_mb ({self.max_request_body_mb}) must be greater"
                f" than {num_json_fields} x max_json_field_mb"
                f" ({num_json_fields * self.max_json_field_mb})"
            )
        return self

    @model_validator(mode="after")
    def _resolve_version(self) -> Self:
        """Resolve version from package metadata if not explicitly set.

        Attempts to determine the application version from importlib.metadata
        using the app_name configuration value. If the package is not installed,
        falls back to git commit hash detection.

        Returns
        -------
        Self
            The validated Settings instance with version field populated.
        """
        if self.version == "unknown":
            self.version = _get_version(self.app_name)
        return self


# ----------------------------------------------------------------------
# Application-wide settings singleton
# ----------------------------------------------------------------------
settings = Settings()
