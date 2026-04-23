"""Tests for JSONFieldSizeConstraint domain object."""

import json

import pytest
from fact_inventory.application.exceptions import FactValidationError
from fact_inventory.domain.constraints import (
    JSONFieldSizeConstraint,
)


class TestJSONFieldSizeConstraint:
    def test_validation_bounds(self) -> None:
        JSONFieldSizeConstraint(max_size_mb=0.001)
        with pytest.raises(ValueError):
            JSONFieldSizeConstraint(max_size_mb=0)
        with pytest.raises(ValueError):
            JSONFieldSizeConstraint(max_size_mb=-1.0)

    def test_is_valid_empty_dict(self) -> None:
        c = JSONFieldSizeConstraint(max_size_mb=1.0)
        assert c.is_valid_size(json.dumps({}).encode()) is True

    def test_is_valid_small_dict(self) -> None:
        c = JSONFieldSizeConstraint(max_size_mb=1.0)
        assert c.is_valid_size(json.dumps({"k": "v"}).encode()) is True

    def test_is_invalid_over_limit(self) -> None:
        c = JSONFieldSizeConstraint(max_size_mb=0.001)
        assert c.is_valid_size(json.dumps({"k": "x" * 10000}).encode()) is False

    def test_validate_success(self) -> None:
        JSONFieldSizeConstraint(max_size_mb=5.0).validate_size("field", {"os": "RHEL"})

    def test_validate_empty_dict_ok(self) -> None:
        JSONFieldSizeConstraint(max_size_mb=1.0).validate_size("field", {})

    def test_validate_oversized_raises(self) -> None:
        c = JSONFieldSizeConstraint(max_size_mb=0.001)
        with pytest.raises(ValueError, match="exceeds maximum size"):
            c.validate_size("large_field", {"x": "y" * 2000})

    def test_validate_error_includes_field_name(self) -> None:
        c = JSONFieldSizeConstraint(max_size_mb=0.0001)
        with pytest.raises(ValueError, match="my_field"):
            c.validate_size("my_field", {"x": "y" * 1000})

    def test_validate_error_includes_mb_unit(self) -> None:
        c = JSONFieldSizeConstraint(max_size_mb=0.0001)
        with pytest.raises(ValueError, match="MB"):
            c.validate_size("f", {"x": "y" * 1000})

    def test_repr(self) -> None:
        assert "5.0" in repr(JSONFieldSizeConstraint(max_size_mb=5.0))

    def test_instances_are_independent(self) -> None:
        c1 = JSONFieldSizeConstraint(max_size_mb=1.0)
        c2 = JSONFieldSizeConstraint(max_size_mb=10.0)
        assert c1.is_valid_size(json.dumps({"x": "y" * 500}).encode()) is True
        assert c2.is_valid_size(json.dumps({"x": "y" * 500}).encode()) is True

    def test_has_required_facts_with_data(self) -> None:
        c = JSONFieldSizeConstraint(max_size_mb=5.0)
        c.has_required_facts({"system_facts": {"os": "RHEL"}})

    def test_has_required_facts_rejects_empty(self) -> None:
        c = JSONFieldSizeConstraint(max_size_mb=5.0)
        with pytest.raises(FactValidationError, match="fact"):
            c.has_required_facts(
                {"system_facts": {}, "package_facts": {}, "local_facts": {}}
            )

    def test_has_required_facts_accepts_any_non_empty(self) -> None:
        c = JSONFieldSizeConstraint(max_size_mb=5.0)
        c.has_required_facts(
            {"system_facts": {}, "package_facts": {"glibc": "2.36"}, "local_facts": {}}
        )

    def test_validate_json_fields_success(self) -> None:
        c = JSONFieldSizeConstraint(max_size_mb=5.0)
        c.validate_json_fields(
            {
                "system_facts": {"os": "RHEL"},
                "package_facts": {"glibc": "2.36"},
                "local_facts": {},
            }
        )

    def test_validate_json_fields_rejects_empty(self) -> None:
        c = JSONFieldSizeConstraint(max_size_mb=5.0)
        with pytest.raises(FactValidationError):
            c.validate_json_fields(
                {"system_facts": {}, "package_facts": {}, "local_facts": {}}
            )

    def test_validate_json_fields_rejects_oversized(self) -> None:
        c = JSONFieldSizeConstraint(max_size_mb=0.001)
        with pytest.raises(ValueError, match="exceeds maximum size"):
            c.validate_json_fields(
                {
                    "system_facts": {"os": "RHEL"},
                    "package_facts": {"x": "y" * 2000},
                    "local_facts": {},
                }
            )
