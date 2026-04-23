"""Tests for POST /v1/facts controller."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fact_inventory.application.services import FactInventoryService
from fact_inventory.config.settings import settings
from litestar.status_codes import (
    HTTP_201_CREATED,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
    HTTP_405_METHOD_NOT_ALLOWED,
    HTTP_409_CONFLICT,
    HTTP_413_REQUEST_ENTITY_TOO_LARGE,
    HTTP_500_INTERNAL_SERVER_ERROR,
    HTTP_504_GATEWAY_TIMEOUT,
)
from litestar.testing import AsyncTestClient
from sqlalchemy.exc import SQLAlchemyError


class TestSuccessfulSubmission:
    async def test_valid_payload_returns_201(
        self, valid_payload: dict[str, Any], client: AsyncTestClient
    ) -> None:
        response = await client.post("/v1/facts", json=valid_payload)
        assert response.status_code == HTTP_201_CREATED
        data = response.json()
        assert "Facts stored successfully" in data["detail"]
        assert "application/json" in response.headers["content-type"]

    async def test_minimal_payload_returns_201(
        self, minimal_payload: dict[str, Any], client: AsyncTestClient
    ) -> None:
        assert (
            await client.post("/v1/facts", json=minimal_payload)
        ).status_code == HTTP_201_CREATED

    async def test_valid_payload_with_request_id_returns_201(
        self, valid_payload: dict[str, Any], client: AsyncTestClient
    ) -> None:
        response = await client.post(
            "/v1/facts", json=valid_payload, headers={"X-Request-ID": "test-req-id"}
        )
        assert response.status_code == HTTP_201_CREATED


class TestDTOValidation:
    @pytest.mark.parametrize("field", ["system_facts", "package_facts", "local_facts"])
    async def test_missing_required_field_returns_400(
        self, field: str, client: AsyncTestClient
    ) -> None:
        payload = {
            "system_facts": {"os": "RHEL"},
            "package_facts": {},
            "local_facts": {},
        }
        del payload[field]
        assert (
            await client.post("/v1/facts", json=payload)
        ).status_code == HTTP_400_BAD_REQUEST

    @pytest.mark.parametrize(
        "field,value",
        [
            ("system_facts", "not a dict"),
            ("package_facts", []),
            ("local_facts", 123),
        ],
    )
    async def test_wrong_field_type_returns_400(
        self, field: str, value: Any, client: AsyncTestClient
    ) -> None:
        payload: dict[str, Any] = {
            "system_facts": {},
            "package_facts": {},
            "local_facts": {},
        }
        payload[field] = value
        assert (
            await client.post("/v1/facts", json=payload)
        ).status_code == HTTP_400_BAD_REQUEST

    async def test_unknown_fields_rejected(self, client: AsyncTestClient) -> None:
        payload = {
            "system_facts": {"os": "RHEL"},
            "package_facts": {},
            "local_facts": {},
            "extra": "bad",
        }
        assert (
            await client.post("/v1/facts", json=payload)
        ).status_code == HTTP_400_BAD_REQUEST

    async def test_invalid_json_returns_400(self, client: AsyncTestClient) -> None:
        assert (
            await client.post(
                "/v1/facts",
                content=b"not json",
                headers={"Content-Type": "application/json"},
            )
        ).status_code == HTTP_400_BAD_REQUEST

    async def test_empty_body_returns_400(self, client: AsyncTestClient) -> None:
        assert (
            await client.post(
                "/v1/facts", content=b"", headers={"Content-Type": "application/json"}
            )
        ).status_code == HTTP_400_BAD_REQUEST


class TestBusinessValidation:
    async def test_all_empty_facts_returns_400(self, client: AsyncTestClient) -> None:
        response = await client.post(
            "/v1/facts",
            json={"system_facts": {}, "package_facts": {}, "local_facts": {}},
        )
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == "Validation failed"

    async def test_all_empty_facts_with_request_id_returns_400(
        self, client: AsyncTestClient
    ) -> None:
        response = await client.post(
            "/v1/facts",
            json={"system_facts": {}, "package_facts": {}, "local_facts": {}},
            headers={"X-Request-ID": "test-req-val"},
        )
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == "Validation failed"

    @pytest.mark.parametrize(
        "field,value",
        [
            ("system_facts", {"os": "RHEL"}),
            ("package_facts", {"glibc": "2.36"}),
            ("local_facts", {"env": "prod"}),
        ],
    )
    async def test_single_non_empty_category_accepted(
        self, field: str, value: dict[str, Any], client: AsyncTestClient
    ) -> None:
        payload: dict[str, Any] = {
            "system_facts": {},
            "package_facts": {},
            "local_facts": {},
        }
        payload[field] = value
        assert (
            await client.post("/v1/facts", json=payload)
        ).status_code == HTTP_201_CREATED


class TestPayloadSizeLimits:
    async def test_field_over_json_limit_returns_413(
        self, client: AsyncTestClient
    ) -> None:
        oversized = "x" * (settings.max_json_field_mb * 1024 * 1024 + 1)
        response = await client.post(
            "/v1/facts",
            json={
                "system_facts": {"data": oversized},
                "package_facts": {},
                "local_facts": {},
            },
        )
        assert response.status_code == HTTP_413_REQUEST_ENTITY_TOO_LARGE

    @pytest.mark.parametrize("field", ["system_facts", "package_facts", "local_facts"])
    async def test_each_field_checked_independently(
        self, field: str, client: AsyncTestClient
    ) -> None:
        oversized = "x" * (settings.max_json_field_mb * 1024 * 1024 + 1)
        payload: dict[str, Any] = {
            "system_facts": {},
            "package_facts": {},
            "local_facts": {},
        }
        payload[field] = {"data": oversized}
        assert (
            await client.post("/v1/facts", json=payload)
        ).status_code == HTTP_413_REQUEST_ENTITY_TOO_LARGE

    async def test_field_at_limit_accepted(self, client: AsyncTestClient) -> None:
        at_limit = "x" * (settings.max_json_field_mb * 1024 * 1024 - 12)
        response = await client.post(
            "/v1/facts",
            json={
                "system_facts": {"data": at_limit},
                "package_facts": {},
                "local_facts": {},
            },
        )
        assert response.status_code == HTTP_201_CREATED

    async def test_body_over_http_limit_returns_413(
        self, client: AsyncTestClient
    ) -> None:
        oversized = "x" * (settings.max_request_body_mb * 1024 * 1024 * 2)
        response = await client.post(
            "/v1/facts",
            json={
                "system_facts": {"data": oversized},
                "package_facts": {},
                "local_facts": {},
            },
        )
        assert response.status_code == HTTP_413_REQUEST_ENTITY_TOO_LARGE


class TestEdgeCases:
    async def test_unicode_accepted(self, client: AsyncTestClient) -> None:
        assert (
            await client.post(
                "/v1/facts",
                json={
                    "system_facts": {"host": "服务器-01"},
                    "package_facts": {},
                    "local_facts": {},
                },
            )
        ).status_code == HTTP_201_CREATED

    async def test_null_values_accepted(self, client: AsyncTestClient) -> None:
        assert (
            await client.post(
                "/v1/facts",
                json={
                    "system_facts": {"key": None},
                    "package_facts": {},
                    "local_facts": {},
                },
            )
        ).status_code == HTTP_201_CREATED

    async def test_null_json_body_rejected(self, client: AsyncTestClient) -> None:
        assert (
            await client.post(
                "/v1/facts",
                content=b"null",
                headers={"Content-Type": "application/json"},
            )
        ).status_code == HTTP_400_BAD_REQUEST

    async def test_boolean_values_accepted(self, client: AsyncTestClient) -> None:
        assert (
            await client.post(
                "/v1/facts",
                json={
                    "system_facts": {"on": True},
                    "package_facts": {},
                    "local_facts": {},
                },
            )
        ).status_code == HTTP_201_CREATED

    async def test_numeric_values_accepted(self, client: AsyncTestClient) -> None:
        assert (
            await client.post(
                "/v1/facts",
                json={
                    "system_facts": {"n": 42},
                    "package_facts": {},
                    "local_facts": {},
                },
            )
        ).status_code == HTTP_201_CREATED

    async def test_list_values_accepted(self, client: AsyncTestClient) -> None:
        payload = {
            "system_facts": {"tags": ["a", "b"]},
            "package_facts": {"v": [1, 2]},
            "local_facts": {"k": [3]},
        }
        assert (
            await client.post("/v1/facts", json=payload)
        ).status_code == HTTP_201_CREATED

    async def test_special_characters_accepted(self, client: AsyncTestClient) -> None:
        payload = {
            "system_facts": {"notes": r"!@#$%^&*(){}[]|\\:;\"'<>,.?/"},
            "package_facts": {},
            "local_facts": {},
        }
        assert (
            await client.post("/v1/facts", json=payload)
        ).status_code == HTTP_201_CREATED


class TestErrorHandling:
    async def test_sqlalchemy_error_returns_409(self, client: AsyncTestClient) -> None:
        with patch.object(
            FactInventoryService,
            "upsert_client_record",
            new_callable=AsyncMock,
            side_effect=SQLAlchemyError("db error"),
        ):
            response = await client.post(
                "/v1/facts",
                json={
                    "system_facts": {"os": "RHEL"},
                    "package_facts": {},
                    "local_facts": {},
                },
            )
        assert response.status_code == HTTP_409_CONFLICT

    async def test_sqlalchemy_error_with_request_id_returns_409(
        self, client: AsyncTestClient
    ) -> None:
        with patch.object(
            FactInventoryService,
            "upsert_client_record",
            new_callable=AsyncMock,
            side_effect=SQLAlchemyError("db error"),
        ):
            response = await client.post(
                "/v1/facts",
                json={
                    "system_facts": {"os": "RHEL"},
                    "package_facts": {},
                    "local_facts": {},
                },
                headers={"X-Request-ID": "test-req-db"},
            )
        assert response.status_code == HTTP_409_CONFLICT

    async def test_unexpected_error_returns_500(self, client: AsyncTestClient) -> None:
        with patch.object(
            FactInventoryService,
            "upsert_client_record",
            new_callable=AsyncMock,
            side_effect=RuntimeError("boom"),
        ):
            response = await client.post(
                "/v1/facts",
                json={
                    "system_facts": {"os": "RHEL"},
                    "package_facts": {},
                    "local_facts": {},
                },
            )
        assert response.status_code == HTTP_500_INTERNAL_SERVER_ERROR

    async def test_unexpected_error_with_request_id_returns_500(
        self, client: AsyncTestClient
    ) -> None:
        with patch.object(
            FactInventoryService,
            "upsert_client_record",
            new_callable=AsyncMock,
            side_effect=RuntimeError("boom"),
        ):
            response = await client.post(
                "/v1/facts",
                json={
                    "system_facts": {"os": "RHEL"},
                    "package_facts": {},
                    "local_facts": {},
                },
                headers={"X-Request-ID": "test-req-123"},
            )
        assert response.status_code == HTTP_500_INTERNAL_SERVER_ERROR

    async def test_timeout_returns_504(self, client: AsyncTestClient) -> None:
        with patch.object(
            FactInventoryService,
            "upsert_client_record",
            new_callable=AsyncMock,
            side_effect=TimeoutError("timeout"),
        ):
            response = await client.post(
                "/v1/facts",
                json={
                    "system_facts": {"os": "RHEL"},
                    "package_facts": {},
                    "local_facts": {},
                },
            )
        assert response.status_code == HTTP_504_GATEWAY_TIMEOUT
        assert "timeout" in response.json()["detail"].lower()

    async def test_timeout_with_request_id_returns_504(
        self, client: AsyncTestClient
    ) -> None:
        with patch.object(
            FactInventoryService,
            "upsert_client_record",
            new_callable=AsyncMock,
            side_effect=TimeoutError("timeout"),
        ):
            response = await client.post(
                "/v1/facts",
                json={
                    "system_facts": {"os": "RHEL"},
                    "package_facts": {},
                    "local_facts": {},
                },
                headers={"X-Request-ID": "test-req-456"},
            )
        assert response.status_code == HTTP_504_GATEWAY_TIMEOUT
        assert "timeout" in response.json()["detail"].lower()


class TestPayloadUnderLimit:
    async def test_payload_under_http_limit_accepted(
        self, client: AsyncTestClient
    ) -> None:
        safe_size = (settings.max_request_body_mb * 1024 * 1024) // 10
        payload = {
            "system_facts": {"data": "x" * safe_size},
            "package_facts": {},
            "local_facts": {},
        }
        assert (
            await client.post("/v1/facts", json=payload)
        ).status_code == HTTP_201_CREATED


class TestHttpExceptionReRaise:
    async def test_http_exception_from_service_is_reraised(
        self, client: AsyncTestClient
    ) -> None:
        """HTTPException raised inside the try block must propagate unchanged (not wrapped)."""
        from litestar.exceptions import HTTPException as LitestarHTTPException

        with patch.object(
            FactInventoryService,
            "upsert_client_record",
            new_callable=AsyncMock,
            side_effect=LitestarHTTPException(
                status_code=HTTP_400_BAD_REQUEST, detail="direct http exc"
            ),
        ):
            response = await client.post(
                "/v1/facts",
                json={
                    "system_facts": {"os": "RHEL"},
                    "package_facts": {},
                    "local_facts": {},
                },
            )
        assert response.status_code == HTTP_400_BAD_REQUEST


class TestRouting:
    async def test_v1_prefix_required(self, client: AsyncTestClient) -> None:
        assert (
            await client.post(
                "/facts",
                json={"system_facts": {}, "package_facts": {}, "local_facts": {}},
            )
        ).status_code == HTTP_404_NOT_FOUND

    async def test_v1_prefix_accessible(self, client: AsyncTestClient) -> None:
        assert (
            await client.post(
                "/v1/facts",
                json={
                    "system_facts": {"os": "RHEL"},
                    "package_facts": {},
                    "local_facts": {},
                },
            )
        ).status_code == HTTP_201_CREATED

    async def test_unversioned_not_under_v1(self, client: AsyncTestClient) -> None:
        assert (await client.get("/v1/health")).status_code == HTTP_404_NOT_FOUND

    async def test_get_not_allowed(self, client: AsyncTestClient) -> None:
        assert (
            await client.get("/v1/facts")
        ).status_code == HTTP_405_METHOD_NOT_ALLOWED

    async def test_put_not_allowed(self, client: AsyncTestClient) -> None:
        assert (
            await client.put("/v1/facts", json={})
        ).status_code == HTTP_405_METHOD_NOT_ALLOWED

    async def test_patch_not_allowed(self, client: AsyncTestClient) -> None:
        assert (
            await client.patch("/v1/facts", json={})
        ).status_code == HTTP_405_METHOD_NOT_ALLOWED

    async def test_delete_not_allowed(self, client: AsyncTestClient) -> None:
        assert (
            await client.delete("/v1/facts")
        ).status_code == HTTP_405_METHOD_NOT_ALLOWED
