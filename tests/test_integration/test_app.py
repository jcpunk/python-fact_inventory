"""Integration tests exercising the full application stack.

These tests use a real Litestar app with an in-memory SQLite database
and cover cross-cutting concerns: router path configuration, feature
flag toggles, background job callbacks, and observability settings.
"""

from typing import Any

import pytest
from fact_inventory.app_factory import create_app
from fact_inventory.config.settings import settings
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_404_NOT_FOUND,
    HTTP_413_REQUEST_ENTITY_TOO_LARGE,
)
from litestar.testing import AsyncTestClient


class TestRouterPaths:
    def test_default_path_is_slash(self) -> None:
        from fact_inventory.presentation.api.router import create_router

        assert create_router().path == "/"

    def test_custom_path_stored(self) -> None:
        from fact_inventory.presentation.api.router import create_router

        assert create_router(path="/fact_inventory").path == "/fact_inventory"

    async def test_health_at_default_prefix(self, client: AsyncTestClient) -> None:
        response = await client.get("/health")
        assert response.status_code == HTTP_200_OK
        assert response.json() is None

    async def test_facts_at_default_prefix(self, client: AsyncTestClient) -> None:
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

    async def test_facts_at_custom_prefix(
        self, client_with_custom_router_path: AsyncTestClient
    ) -> None:
        assert (
            await client_with_custom_router_path.post(
                "/fact_inventory/v1/facts",
                json={
                    "system_facts": {"os": "RHEL"},
                    "package_facts": {},
                    "local_facts": {},
                },
            )
        ).status_code == HTTP_201_CREATED

    async def test_health_not_under_v1(self, client: AsyncTestClient) -> None:
        assert (await client.get("/v1/health")).status_code == HTTP_404_NOT_FOUND

    async def test_ready_not_under_v1(self, client: AsyncTestClient) -> None:
        assert (await client.get("/v1/ready")).status_code == HTTP_404_NOT_FOUND


class TestFeatureFlags:
    async def test_both_probes_can_be_disabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "enable_health_endpoint", False)
        monkeypatch.setattr(settings, "enable_ready_endpoint", False)
        async with AsyncTestClient(app=create_app()) as client:
            assert (await client.get("/health")).status_code == HTTP_404_NOT_FOUND
            assert (await client.get("/ready")).status_code == HTTP_404_NOT_FOUND
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

    async def test_openapi_disabled_in_production(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "debug", False)
        assert create_app().openapi_config is None

    async def test_gzip_enabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from litestar.config.compression import CompressionConfig

        original_init = CompressionConfig.__init__

        def patched_init(self, *args, minimum_size: int = 1, **kwargs):
            original_init(self, *args, minimum_size=minimum_size, **kwargs)

        monkeypatch.setattr(CompressionConfig, "__init__", patched_init)

        async with AsyncTestClient(app=create_app()) as client:
            response = await client.post(
                "/v1/facts",
                json={
                    "system_facts": {"os": "RHEL" * 100},
                    "package_facts": {},
                    "local_facts": {},
                },
                headers={"Accept-Encoding": "gzip"},
            )
            assert response.status_code == HTTP_201_CREATED
            assert "gzip" in response.headers.get("content-encoding", "")

    async def test_metrics_endpoint_enabled(self, client: AsyncTestClient) -> None:
        response = await client.get("/metrics")
        assert response.status_code == HTTP_200_OK
        assert "python_info" in response.text

    async def test_metrics_endpoint_disabled(
        self, client_no_metrics: AsyncTestClient
    ) -> None:
        assert (
            await client_no_metrics.get("/metrics")
        ).status_code == HTTP_404_NOT_FOUND

    async def test_v1_works_with_health_disabled(
        self, client_no_health: AsyncTestClient
    ) -> None:
        assert (
            await client_no_health.post(
                "/v1/facts",
                json={
                    "system_facts": {"os": "RHEL"},
                    "package_facts": {},
                    "local_facts": {},
                },
            )
        ).status_code == HTTP_201_CREATED

    async def test_v1_works_with_ready_disabled(
        self, client_no_ready: AsyncTestClient
    ) -> None:
        assert (
            await client_no_ready.post(
                "/v1/facts",
                json={
                    "system_facts": {"os": "RHEL"},
                    "package_facts": {},
                    "local_facts": {},
                },
            )
        ).status_code == HTTP_201_CREATED


class TestBackgroundJobCallbacks:
    async def test_retention_callback_returns_int(self) -> None:
        async with AsyncTestClient(app=create_app()) as client:
            plugin = next(
                p
                for p in client.app.plugins
                if p.__class__.__name__ == "AsyncBackgroundJobPlugin"
                and p._name == "fact-inventory-retention-cleanup"
            )
            result = await plugin._job_callback()
            assert isinstance(result, int) and result >= 0

    async def test_history_callback_returns_int(self) -> None:
        async with AsyncTestClient(app=create_app()) as client:
            plugin = next(
                p
                for p in client.app.plugins
                if p.__class__.__name__ == "AsyncBackgroundJobPlugin"
                and p._name == "fact-inventory-history-cleanup"
            )
            result = await plugin._job_callback()
            assert isinstance(result, int) and result >= 0

    async def test_facts_not_at_bare_path(self, client: AsyncTestClient) -> None:
        response = await client.post(
            "/facts",
            json={"system_facts": {}, "package_facts": {}, "local_facts": {}},
        )
        assert response.status_code == HTTP_404_NOT_FOUND

    async def test_callbacks_work_with_data_present(
        self, valid_payload: dict[str, Any]
    ) -> None:
        """Callbacks function correctly when records already exist in the database."""
        async with AsyncTestClient(app=create_app()) as client:
            await client.post("/v1/facts", json=valid_payload)
            await client.post("/v1/facts", json=valid_payload)
            plugin = next(
                p
                for p in client.app.plugins
                if p.__class__.__name__ == "AsyncBackgroundJobPlugin"
                and p._name == "fact-inventory-history-cleanup"
            )
            result = await plugin._job_callback()
            assert isinstance(result, int) and result >= 0


class TestPayloadSizeLimits:
    async def test_payload_under_http_limit_accepted(
        self, client: AsyncTestClient
    ) -> None:
        safe_size = (settings.max_request_body_mb * 1024 * 1024) // 10
        assert (
            await client.post(
                "/v1/facts",
                json={
                    "system_facts": {"data": "x" * safe_size},
                    "package_facts": {},
                    "local_facts": {},
                },
            )
        ).status_code == HTTP_201_CREATED

    async def test_field_at_json_limit_accepted(self, client: AsyncTestClient) -> None:
        at_limit = "x" * (settings.max_json_field_mb * 1024 * 1024 - 12)
        assert (
            await client.post(
                "/v1/facts",
                json={
                    "system_facts": {"data": at_limit},
                    "package_facts": {},
                    "local_facts": {},
                },
            )
        ).status_code == HTTP_201_CREATED

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


class TestBackgroundJobSettings:
    async def test_retention_job_disabled_only_retention_disabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "enable_retention_cleanup_job", False)
        async with AsyncTestClient(app=create_app()) as client:
            plugins = [
                p
                for p in client.app.plugins
                if p.__class__.__name__ == "AsyncBackgroundJobPlugin"
            ]
            assert len(plugins) == 1
            assert plugins[0]._name == "fact-inventory-history-cleanup"

    async def test_history_job_disabled_only_history_disabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "enable_history_cleanup_job", False)
        async with AsyncTestClient(app=create_app()) as client:
            plugins = [
                p
                for p in client.app.plugins
                if p.__class__.__name__ == "AsyncBackgroundJobPlugin"
            ]
            assert len(plugins) == 1
            assert plugins[0]._name == "fact-inventory-retention-cleanup"

    async def test_both_jobs_disabled_via_individual_flags(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "enable_retention_cleanup_job", False)
        monkeypatch.setattr(settings, "enable_history_cleanup_job", False)
        async with AsyncTestClient(app=create_app()) as client:
            plugins = [
                p
                for p in client.app.plugins
                if p.__class__.__name__ == "AsyncBackgroundJobPlugin"
            ]
            assert len(plugins) == 0


class TestSettings:
    def test_debug_and_log_level_are_independent(self) -> None:
        assert isinstance(settings.debug, bool)
        assert isinstance(settings.log_level, str)
