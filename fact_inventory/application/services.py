"""Service layer for fact inventory operations.

The service layer implements application rules and business logic for fact
inventory operations. Services express application-level behavior while
delegating database operations to the repository layer.

Service Layer Rationale
-----------------------
Services embody application rules: validation, state transitions, retention
policies, and orchestration. They use domain objects to express business rules
and call repositories for database work. This separation lets rules evolve
independently - retention policy changes affect only services, not controllers
or database schemas.

This layer has no HTTP or framework imports. All exceptions raised here are
plain Python exceptions; the presentation layer converts them to HTTP responses.
"""

import logging
from typing import Any

from advanced_alchemy.service import SQLAlchemyAsyncRepositoryService

from fact_inventory.config.settings import settings
from fact_inventory.domain.constraints import JSONFieldSizeConstraint
from fact_inventory.domain.retention import (
    HistoryRetentionPolicy,
    TimeRetentionPolicy,
)
from fact_inventory.infrastructure.db.models import FactInventory
from fact_inventory.infrastructure.db.repositories import FactInventoryRepository

__all__ = ["FactInventoryService"]


class FactInventoryService(SQLAlchemyAsyncRepositoryService[FactInventory]):
    """Business-logic layer for fact inventory records.

    Methods in this class express application rules (retention, upsert strategy,
    etc.) while delegating database-specific work to FactInventoryRepository.

    Notes
    -----
    The service layer is framework-agnostic. It uses domain objects for business
    rules and repositories for database access.
    """

    model_type = FactInventory
    repository_type = FactInventoryRepository
    repository: FactInventoryRepository

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the service with domain constraints.

        Parameters
        ----------
        *args : Any
            Positional arguments passed to the parent SQLAlchemyAsyncRepositoryService.
        **kwargs : Any
            Keyword arguments passed to the parent SQLAlchemyAsyncRepositoryService.
        """
        super().__init__(*args, **kwargs)
        self._json_field_constraint = JSONFieldSizeConstraint(
            settings.max_json_field_mb
        )

    def _validate_json_field_constraints(self, data: dict[str, Any]) -> None:
        """Validate JSON data against configured constraints.

        Parameters
        ----------
        data : dict[str, Any]
            Dictionary containing system_facts, package_facts, and local_facts.

        Raises
        ------
        FactValidationError
            If all fact categories are empty.
        ValueError
            If any JSON field exceeds the configured size limit.
        """
        self._json_field_constraint.validate_json_fields(data)

    async def purge_facts_older_than(self, retention_days: int) -> int:
        """Delete fact records not updated within the specified retention window.

        Parameters
        ----------
        retention_days : int
            Records with updated_at older than this many days in the
            past are deleted.
            See ``fact_inventory.domain.retention.TimeRetentionPolicy``
            for the authoritative constraint values.

        Returns
        -------
        int
            Number of records deleted. All timestamp comparisons use UTC.

        Raises
        ------
        RepositoryError
            If the record could not be deleted (e.g., database connection error).
        SQLAlchemyError
            If database persistence fails for any reason.
        ValueError
            If retention_days is outside the valid range defined by
            ``TimeRetentionPolicy.MIN_DAYS`` and ``TimeRetentionPolicy.MAX_DAYS``.
        """
        policy = TimeRetentionPolicy(retention_days)

        deleted_count = await self.repository.delete_facts_older_than(policy)
        if deleted_count > 0:
            logging.getLogger(__name__).info(
                "Stale fact records removed by retention policy"
            )
        return deleted_count

    async def purge_fact_history_more_than(self, max_entries: int) -> int:
        """Delete excess fact records per client_address from history.

        Keeps the newest max_entries per client_address, deletes older ones.

        Parameters
        ----------
        max_entries : int
            Maximum records to keep per client_address.
            See ``fact_inventory.domain.retention.HistoryRetentionPolicy``
            for the authoritative constraint values.

        Returns
        -------
        int
            Number of records deleted.

        Raises
        ------
        RepositoryError
            If the record could not be deleted (e.g., database connection error).
        SQLAlchemyError
            If database persistence fails for any reason.
        ValueError
            If max_entries is outside the valid range defined by
            ``HistoryRetentionPolicy.MIN_ENTRIES`` and
            ``HistoryRetentionPolicy.MAX_ENTRIES``.
        """
        policy = HistoryRetentionPolicy(max_entries)

        deleted_count = await self.repository.delete_old_client_facts_over_limit(policy)
        if deleted_count > 0:
            logging.getLogger(__name__).info("Excess fact history removed per client")
        return deleted_count

    async def insert_record(self, data: dict[str, Any]) -> None:
        """Insert a new fact inventory record.

        Creates a new record with the provided fact data. Multiple rows may
        exist for the same client_address - each call creates a new row with
        a unique UUID generated by the database.

        Parameters
        ----------
        data : dict[str, Any]
            Dictionary containing client_address, system_facts,
            package_facts, and local_facts.

        Raises
        ------
        FactValidationError
            If all fact categories are empty.
        RepositoryError
            If the record could not be created (e.g., database connection error).
        SQLAlchemyError
            If database persistence fails for any reason.
        ValueError
            If any JSON field exceeds the configured size limit.
        """
        self._validate_json_field_constraints(data)
        await self.repository.insert_record(data)
        logging.getLogger(__name__).info("Fact inventory record inserted successfully")

    async def upsert_client_record(self, data: dict[str, Any]) -> None:
        """Create or update a fact inventory record for a client_address.

        Matching is based on client_address - if a record exists for
        the same IP it is updated in place and updated_at is refreshed;
        otherwise a new record is created.

        Parameters
        ----------
        data : dict[str, Any]
            Dictionary containing client_address, system_facts,
            package_facts, and local_facts.

        Raises
        ------
        FactValidationError
            If all fact categories are empty.
        ValueError
            If any JSON field exceeds the configured size limit.
        """
        self._validate_json_field_constraints(data)
        await self.repository.upsert_client_record(data)
        logging.getLogger(__name__).info(
            "Fact inventory client record upserted successfully"
        )
