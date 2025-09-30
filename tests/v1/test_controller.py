"""
Tests for the FactController HTTP endpoints.
"""

import asyncio

from litestar.status_codes import (
    HTTP_201_CREATED,
    HTTP_400_BAD_REQUEST,
    HTTP_413_REQUEST_ENTITY_TOO_LARGE,
    HTTP_429_TOO_MANY_REQUESTS,
)
from litestar.testing import AsyncTestClient


class TestFactControllerSubmit:
    """Tests for the POST /v1/facts endpoint."""

    async def test_submit_valid_params(
        self,
        client: AsyncTestClient,
    ) -> None:
        """Test submitting valid fact data returns 200."""
        response = await client.post(
            "/v1/facts",
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
            "/v1/facts",
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
            "/v1/facts",
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

        response = await client.post("/v1/facts", json=nested_facts)

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

        response = await client.post("/v1/facts", json=unicode_facts)

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

        response = await client.post("/v1/facts", json=special_facts)

        assert response.status_code == HTTP_201_CREATED
        assert "Facts stored successfully" in response.text
        assert "testclient" in response.text

    async def test_submit_missing_system_facts(
        self,
        client: AsyncTestClient,
    ) -> None:
        """Test that missing system_facts field is rejected."""
        response = await client.post(
            "/v1/facts",
            json={"package_facts": {}},
        )

        assert response.status_code == HTTP_400_BAD_REQUEST

    async def test_submit_missing_package_facts(
        self,
        client: AsyncTestClient,
    ) -> None:
        """Test that missing package_facts field is rejected."""
        response = await client.post(
            "/v1/facts",
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
        response = await client.post("/v1/facts", json=invalid_data)

        assert response.status_code == HTTP_400_BAD_REQUEST

    async def test_submit_invalid_json(
        self,
        client: AsyncTestClient,
    ) -> None:
        """Test that malformed JSON is rejected."""
        response = await client.post(
            "/v1/facts",
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
            "/v1/facts",
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
            "/v1/facts",
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

        response = await client.post("/v1/facts", json=oversized_data)

        assert response.status_code == HTTP_413_REQUEST_ENTITY_TOO_LARGE

    async def test_rate_limit_enforcement(
        self,
        client: AsyncTestClient,
    ) -> None:
        """Test that rate limiting works for repeated submissions."""
        # First submission should succeed
        response1 = await client.post(
            "/v1/facts",
            json={
                "system_facts": {},
                "package_facts": {},
            },
        )
        assert response1.status_code == HTTP_201_CREATED
        assert response1.headers.get("Retry-After") is None

        await asyncio.sleep(6)

        # Second immediate submission should be rate limited
        response2 = await client.post(
            "/v1/facts",
            json={
                "system_facts": {},
                "package_facts": {},
            },
        )

        assert response2.status_code == HTTP_429_TOO_MANY_REQUESTS
        assert "Rate limit exceeded" in response2.text
        assert "Retry-After" in response2.headers
        assert int(response2.headers.get("Retry-After")) > 0
