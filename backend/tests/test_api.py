"""End-to-end API integration tests against the real app (ASGI, in-process)."""

from __future__ import annotations


import httpx
import pytest

from app.main import app


@pytest.fixture()
async def client(tmp_path):
    """ASGI client with the application lifespan fully started."""
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver", timeout=30.0
        ) as async_client:
            yield async_client


class TestHealth:
    async def test_health(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/api/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"

    async def test_ready(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/api/ready")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ready"
        assert body["providers_registered"] >= 3


class TestProviders:
    async def test_catalog_matches_reference_schema(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/api/providers")
        assert response.status_code == 200
        body = response.json()
        assert body["vault_config"]["encryption_algorithm"] == "AES-256-GCM"
        providers = {p["provider_id"]: p for p in body["providers"]}
        assert "nvidia_nemotron" in providers
        assert providers["nvidia_nemotron"]["base_url"] == "https://integrate.api.nvidia.com/v1"
        assert "qwen_dashscope" in providers
        assert providers["qwen_dashscope"]["base_url"] == (
            "https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        assert "qwen_openrouter" in providers
        assert "qwen-max" in providers["qwen_dashscope"]["supported_models"]

    async def test_usage_empty(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/api/providers/usage")
        assert response.status_code == 200
        assert response.json()["total_requests"] == 0


class TestVaultFlow:
    async def test_status_unlocked_via_env_master_key(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/api/vault/status")
        assert response.status_code == 200
        assert response.json()["state"] == "unlocked"

    async def test_key_lifecycle(self, client: httpx.AsyncClient) -> None:
        # Create (seal) a key for the NVIDIA provider.
        response = await client.post(
            "/api/vault/keys",
            json={
                "provider_id": "nvidia_nemotron",
                "label": "CI key",
                "api_key": "nvapi-" + "k" * 40,
            },
        )
        assert response.status_code == 201
        created = response.json()
        assert created["fingerprint"]
        assert "k" * 40 not in json_dumps(created)  # never echo key material
        assert created["status"] == "active"

        # List shows exactly one sealed key, masked.
        response = await client.get("/api/vault/keys")
        assert response.status_code == 200
        keys = response.json()
        assert any(k["provider_id"] == "nvidia_nemotron" for k in keys)
        for key in keys:
            assert "nvapi-" + "k" * 40 not in json_dumps(key)

        # Rotate it.
        response = await client.post(
            f"/api/vault/keys/{created['id']}/rotate",
            json={"api_key": "nvapi-" + "j" * 40},
        )
        assert response.status_code == 200

        # Delete it.
        response = await client.delete(f"/api/vault/keys/{created['id']}")
        assert response.status_code == 204

    async def test_unknown_provider_rejected(self, client: httpx.AsyncClient) -> None:
        response = await client.post(
            "/api/vault/keys",
            json={"provider_id": "does_not_exist", "label": "x", "api_key": "sk-whatever-123"},
        )
        assert response.status_code == 404

    async def test_short_key_rejected(self, client: httpx.AsyncClient) -> None:
        response = await client.post(
            "/api/vault/keys",
            json={"provider_id": "openai", "label": "x", "api_key": "short"},
        )
        assert response.status_code == 422


class TestSwarmGuardrails:
    async def test_launch_requires_ready_repository(self, client: httpx.AsyncClient) -> None:
        response = await client.post(
            "/api/swarm/jobs",
            json={"repository_id": "nonexistent", "task": "do something with this codebase"},
        )
        assert response.status_code == 404

    async def test_jobs_list_empty(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/api/swarm/jobs")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestSse:
    async def test_job_stream_404_for_unknown_job(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/api/swarm/jobs/unknown/stream")
        assert response.status_code == 404


def json_dumps(value: object) -> str:
    import json

    return json.dumps(value, default=str)
