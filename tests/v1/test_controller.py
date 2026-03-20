"""
Tests for the FactController HTTP endpoints.
"""

from unittest.mock import AsyncMock, patch

from app.fact_inventory.v1.services import HostFactsService
from litestar.status_codes import (
    HTTP_201_CREATED,
    HTTP_400_BAD_REQUEST,
    HTTP_405_METHOD_NOT_ALLOWED,
    HTTP_409_CONFLICT,
    HTTP_413_REQUEST_ENTITY_TOO_LARGE,
    HTTP_429_TOO_MANY_REQUESTS,
    HTTP_500_INTERNAL_SERVER_ERROR,
)
from litestar.testing import AsyncTestClient
from sqlalchemy.exc import SQLAlchemyError


class TestFactControllerSubmit:
    """Tests for the POST /fact_inventory/v1/facts endpoint."""

    async def test_submit_valid_params(
        self,
        client: AsyncTestClient,
    ) -> None:
        """Test submitting valid fact data returns 200."""
        response = await client.post(
            "/fact_inventory/v1/facts",
            json={  # these are just example nonsense values
                "system_facts": {
                    "os": "RHEL",
                    "version": "9.2",
                    "hostname": "test-server-01",
                    "architecture": "x86_64",
                    "kernel": "5.14.0-284.11.1.el9_2.x86_64",
                },
                "package_facts": {
                    "installed": ["vim", "git", "htop", "nginx"],
                    "total_packages": 1523,
                },
            },
        )

        assert response.status_code == HTTP_201_CREATED
        assert "Facts stored successfully" in response.text
        assert "testclient" in response.text

    async def test_submit_minimal(
        self,
        client: AsyncTestClient,
    ) -> None:
        """Test submitting minimal valid data."""
        response = await client.post(
            "/fact_inventory/v1/facts",
            json={
                "system_facts": {},
                "package_facts": {},
            },
        )

        assert response.status_code == HTTP_201_CREATED
        assert "Facts stored successfully" in response.text
        assert "testclient" in response.text

    async def test_empty_json_objects(
        self,
        client: AsyncTestClient,
    ) -> None:
        """Test submitting empty but valid JSON objects."""
        response = await client.post(
            "/fact_inventory/v1/facts",
            json={"system_facts": {}, "package_facts": {}},
        )

        assert response.status_code == HTTP_201_CREATED
        assert "Facts stored successfully" in response.text
        assert "testclient" in response.text

    async def test_nested_json_structures(
        self,
        client: AsyncTestClient,
    ) -> None:
        """Test that deeply nested JSON is accepted."""
        nested_facts = {
            "system_facts": {
                "network": {
                    "interfaces": {
                        "eth0": {
                            "ipv4": "192.168.1.100",
                            "ipv6": "fe80::1",
                        }
                    }
                }
            },
            "package_facts": {},
        }

        response = await client.post("/fact_inventory/v1/facts", json=nested_facts)

        assert response.status_code == HTTP_201_CREATED
        assert "Facts stored successfully" in response.text
        assert "testclient" in response.text

    async def test_unicode_in_data(
        self,
        client: AsyncTestClient,
    ) -> None:
        """Test that Unicode characters are handled correctly."""
        unicode_facts = {
            "system_facts": {
                "hostname": "服务器-01",
                "location": "北京",
            },
            "package_facts": {},
        }

        response = await client.post("/fact_inventory/v1/facts", json=unicode_facts)

        assert response.status_code == HTTP_201_CREATED
        assert "Facts stored successfully" in response.text
        assert "testclient" in response.text

    async def test_special_characters_in_data(
        self,
        client: AsyncTestClient,
    ) -> None:
        """Test that special characters don't break the API."""
        special_facts = {
            "system_facts": {
                "notes": "Test with special chars: !@#$%^&*(){}[]|\\:;\"'<>,.?/",
            },
            "package_facts": {},
        }

        response = await client.post("/fact_inventory/v1/facts", json=special_facts)

        assert response.status_code == HTTP_201_CREATED
        assert "Facts stored successfully" in response.text
        assert "testclient" in response.text

    async def test_submit_missing_system_facts(
        self,
        client: AsyncTestClient,
    ) -> None:
        """Test that missing system_facts field is rejected."""
        response = await client.post(
            "/fact_inventory/v1/facts",
            json={"package_facts": {}},
        )

        assert response.status_code == HTTP_400_BAD_REQUEST

    async def test_submit_missing_package_facts(
        self,
        client: AsyncTestClient,
    ) -> None:
        """Test that missing package_facts field is rejected."""
        response = await client.post(
            "/fact_inventory/v1/facts",
            json={"system_facts": {}},
        )

        assert response.status_code == HTTP_400_BAD_REQUEST

    async def test_submit_unknown_fields(
        self,
        client: AsyncTestClient,
    ) -> None:
        """Test that unknown fields are rejected."""
        invalid_data = {
            "package_facts": {},
            "system_facts": {},
            "unknown_field": "should_fail",
        }
        response = await client.post("/fact_inventory/v1/facts", json=invalid_data)

        assert response.status_code == HTTP_400_BAD_REQUEST

    async def test_submit_invalid_json(
        self,
        client: AsyncTestClient,
    ) -> None:
        """Test that malformed JSON is rejected."""
        response = await client.post(
            "/fact_inventory/v1/facts",
            content="not valid json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == HTTP_400_BAD_REQUEST

    async def test_submit_non_dict_system_facts(
        self,
        client: AsyncTestClient,
    ) -> None:
        """Test that non-dict system_facts are rejected."""
        response = await client.post(
            "/fact_inventory/v1/facts",
            json={
                "system_facts": "not a dict",
                "package_facts": {},
            },
        )

        assert response.status_code == HTTP_400_BAD_REQUEST

    async def test_submit_non_dict_package_facts(
        self,
        client: AsyncTestClient,
    ) -> None:
        """Test that non-dict package_facts are rejected."""
        response = await client.post(
            "/fact_inventory/v1/facts",
            json={
                "system_facts": {},
                "package_facts": ["not", "a", "dict"],
            },
        )

        assert response.status_code == HTTP_400_BAD_REQUEST

    async def test_submit_single_oversized_json_field(
        self,
        client: AsyncTestClient,
    ) -> None:
        """Test that JSON fields exceeding the limit are rejected."""
        oversized_data = {
            "system_facts": {
                "large_field_x": "x" * (15 * 1024 * 1024),
                "large_field_y": "y" * (15 * 1024 * 1024),
                "large_field_z": "z" * (15 * 1024 * 1024),
            },
            "package_facts": {},
        }

        response = await client.post("/fact_inventory/v1/facts", json=oversized_data)

        assert response.status_code == HTTP_413_REQUEST_ENTITY_TOO_LARGE

    async def test_rate_limit_enforcement(
        self,
        client: AsyncTestClient,
    ) -> None:
        """Test that rate limiting works for repeated submissions.

        Rate limiting is handled by Litestar's ``RateLimitMiddleware``
        (configured in the application factory).  The test environment
        uses ``RATE_LIMIT_UNIT=second`` / ``RATE_LIMIT_MAX_REQUESTS=1``
        so the second request within the same second is rejected.
        """
        # First submission should succeed
        response1 = await client.post(
            "/fact_inventory/v1/facts",
            json={
                "system_facts": {},
                "package_facts": {},
            },
        )
        assert response1.status_code == HTTP_201_CREATED

        # Second immediate submission should be rate limited
        response2 = await client.post(
            "/fact_inventory/v1/facts",
            json={
                "system_facts": {},
                "package_facts": {},
            },
        )

        assert response2.status_code == HTTP_429_TOO_MANY_REQUESTS
        assert "application/json" in response2.headers["content-type"]
        assert "detail" in response2.json()

    # ------------------------------------------------------------------
    # HTTP method restrictions
    # ------------------------------------------------------------------

    async def test_submit_get_not_allowed(self, client: AsyncTestClient) -> None:
        """GET is not allowed on the facts endpoint."""
        response = await client.get("/fact_inventory/v1/facts")
        assert response.status_code == HTTP_405_METHOD_NOT_ALLOWED

    async def test_submit_put_not_allowed(self, client: AsyncTestClient) -> None:
        """PUT is not allowed on the facts endpoint."""
        response = await client.put("/fact_inventory/v1/facts", json={})
        assert response.status_code == HTTP_405_METHOD_NOT_ALLOWED

    async def test_submit_delete_not_allowed(self, client: AsyncTestClient) -> None:
        """DELETE is not allowed on the facts endpoint."""
        response = await client.delete("/fact_inventory/v1/facts")
        assert response.status_code == HTTP_405_METHOD_NOT_ALLOWED

    async def test_submit_patch_not_allowed(self, client: AsyncTestClient) -> None:
        """PATCH is not allowed on the facts endpoint."""
        response = await client.patch("/fact_inventory/v1/facts", json={})
        assert response.status_code == HTTP_405_METHOD_NOT_ALLOWED

    # ------------------------------------------------------------------
    # 201 success response shape
    # ------------------------------------------------------------------

    async def test_submit_response_is_json(self, client: AsyncTestClient) -> None:
        """Successful submission must return application/json."""
        response = await client.post(
            "/fact_inventory/v1/facts",
            json={"system_facts": {}, "package_facts": {}},
        )
        assert response.status_code == HTTP_201_CREATED
        assert "application/json" in response.headers["content-type"]

    async def test_submit_response_has_detail_key(
        self, client: AsyncTestClient
    ) -> None:
        """201 response body must contain a 'detail' key."""
        response = await client.post(
            "/fact_inventory/v1/facts",
            json={"system_facts": {}, "package_facts": {}},
        )
        assert response.status_code == HTTP_201_CREATED
        assert "detail" in response.json()

    async def test_submit_response_body_has_only_detail_key(
        self, client: AsyncTestClient
    ) -> None:
        """201 response body must contain exactly one key."""
        response = await client.post(
            "/fact_inventory/v1/facts",
            json={"system_facts": {}, "package_facts": {}},
        )
        assert response.status_code == HTTP_201_CREATED
        assert set(response.json().keys()) == {"detail"}

    # ------------------------------------------------------------------
    # 409 path -- storage layer failure
    # ------------------------------------------------------------------

    async def test_submit_storage_failure_returns_409(
        self, client: AsyncTestClient
    ) -> None:
        """A storage error must return HTTP 409."""
        with patch.object(
            HostFactsService,
            "upsert_host_facts",
            new_callable=AsyncMock,
            side_effect=SQLAlchemyError("simulated write failure"),
        ):
            response = await client.post(
                "/fact_inventory/v1/facts",
                json={"system_facts": {}, "package_facts": {}},
            )
        assert response.status_code == HTTP_409_CONFLICT

    async def test_submit_storage_failure_response_is_json(
        self, client: AsyncTestClient
    ) -> None:
        """409 response must be JSON."""
        with patch.object(
            HostFactsService,
            "upsert_host_facts",
            new_callable=AsyncMock,
            side_effect=SQLAlchemyError("simulated write failure"),
        ):
            response = await client.post(
                "/fact_inventory/v1/facts",
                json={"system_facts": {}, "package_facts": {}},
            )
        assert "application/json" in response.headers["content-type"]

    async def test_submit_storage_failure_has_detail_key(
        self, client: AsyncTestClient
    ) -> None:
        """409 response body must contain a 'detail' key."""
        with patch.object(
            HostFactsService,
            "upsert_host_facts",
            new_callable=AsyncMock,
            side_effect=SQLAlchemyError("simulated write failure"),
        ):
            response = await client.post(
                "/fact_inventory/v1/facts",
                json={"system_facts": {}, "package_facts": {}},
            )
        assert "detail" in response.json()

    async def test_submit_storage_failure_detail_is_safe(
        self, client: AsyncTestClient
    ) -> None:
        """409 detail must not reveal internal storage implementation details."""
        with patch.object(
            HostFactsService,
            "upsert_host_facts",
            new_callable=AsyncMock,
            side_effect=SQLAlchemyError("simulated write failure"),
        ):
            response = await client.post(
                "/fact_inventory/v1/facts",
                json={"system_facts": {}, "package_facts": {}},
            )
        detail = response.json()["detail"].lower()
        assert "sqlalchemy" not in detail
        assert "traceback" not in detail
        assert "simulated write failure" not in detail

    # ------------------------------------------------------------------
    # 500 path -- unexpected exception
    # ------------------------------------------------------------------

    async def test_submit_unexpected_error_returns_500(
        self, client: AsyncTestClient
    ) -> None:
        """An unexpected exception during storage must return HTTP 500."""
        with patch.object(
            HostFactsService,
            "upsert_host_facts",
            new_callable=AsyncMock,
            side_effect=RuntimeError("something went very wrong"),
        ):
            response = await client.post(
                "/fact_inventory/v1/facts",
                json={"system_facts": {}, "package_facts": {}},
            )
        assert response.status_code == HTTP_500_INTERNAL_SERVER_ERROR

    # ------------------------------------------------------------------
    # Valid payload content -- accepted value types inside facts dicts
    # ------------------------------------------------------------------

    async def test_submit_null_values_in_system_facts(
        self, client: AsyncTestClient
    ) -> None:
        """null values inside system_facts must be accepted."""
        response = await client.post(
            "/fact_inventory/v1/facts",
            json={"system_facts": {"key": None}, "package_facts": {}},
        )
        assert response.status_code == HTTP_201_CREATED

    async def test_submit_boolean_values_in_facts(
        self, client: AsyncTestClient
    ) -> None:
        """Boolean values inside facts dicts must be accepted."""
        response = await client.post(
            "/fact_inventory/v1/facts",
            json={
                "system_facts": {"enabled": True, "disabled": False},
                "package_facts": {},
            },
        )
        assert response.status_code == HTTP_201_CREATED

    async def test_submit_numeric_values_in_facts(
        self, client: AsyncTestClient
    ) -> None:
        """Numeric values inside facts dicts must be accepted."""
        response = await client.post(
            "/fact_inventory/v1/facts",
            json={
                "system_facts": {"count": 42, "ratio": 3.14},
                "package_facts": {},
            },
        )
        assert response.status_code == HTTP_201_CREATED

    async def test_submit_list_values_in_facts(self, client: AsyncTestClient) -> None:
        """List values inside facts dicts must be accepted."""
        response = await client.post(
            "/fact_inventory/v1/facts",
            json={
                "system_facts": {"tags": ["a", "b", "c"]},
                "package_facts": {"versions": [1, 2, 3]},
            },
        )
        assert response.status_code == HTTP_201_CREATED

    async def test_submit_empty_string_value_in_facts(
        self, client: AsyncTestClient
    ) -> None:
        """Empty string values inside facts dicts must be accepted."""
        response = await client.post(
            "/fact_inventory/v1/facts",
            json={"system_facts": {"key": ""}, "package_facts": {}},
        )
        assert response.status_code == HTTP_201_CREATED

    # ------------------------------------------------------------------
    # Malformed / empty body
    # ------------------------------------------------------------------

    async def test_submit_empty_body(self, client: AsyncTestClient) -> None:
        """An empty request body must be rejected."""
        response = await client.post(
            "/fact_inventory/v1/facts",
            content=b"",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == HTTP_400_BAD_REQUEST

    async def test_submit_null_json_body(self, client: AsyncTestClient) -> None:
        """A JSON null body must be rejected."""
        response = await client.post(
            "/fact_inventory/v1/facts",
            content=b"null",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == HTTP_400_BAD_REQUEST
