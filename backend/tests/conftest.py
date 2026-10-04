"""Shared test fixtures.

Environment is pinned BEFORE importing ``app.main`` so the module-level
``create_app()`` picks up the test configuration (temp DB, temp clone root,
known vault passphrase, execution disabled).
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import httpx
import pytest

_TMP_DIR = Path(tempfile.mkdtemp(prefix="nexus-test-"))
os.environ["NEXUS_DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP_DIR / 'test.db'}"
os.environ["NEXUS_VAULT_MASTER_KEY"] = "unit-test-master-passphrase"
os.environ["NEXUS_VAULT_AUTO_UNLOCK"] = "true"
os.environ["NEXUS_CLONE_ROOT"] = str(_TMP_DIR / "repos")
os.environ["NEXUS_EXECUTION_ENABLED"] = "false"
os.environ["NEXUS_TOKEN_BUDGET_PER_JOB"] = "400000"

from app.core.config import Settings  # noqa: E402
from app.services.llm_client import OpenAICompatibleClient  # noqa: E402
from app.services.provider_router import ProviderRouter  # noqa: E402
from app.services.vault import KeyVault  # noqa: E402


@pytest.fixture(scope="session")
def tmp_root() -> Path:
    return _TMP_DIR


@pytest.fixture()
def settings(tmp_root: Path) -> Settings:
    """Isolated settings instance for unit tests."""
    return Settings(
        _env_file=None,
        vault_master_key="unit-test-master-passphrase",
        database_url=f"sqlite+aiosqlite:///{tmp_root / 'unit.db'}",
        clone_root=str(tmp_root / "repos"),
    )


@pytest.fixture()
def vault(settings: Settings) -> KeyVault:
    unlocked = KeyVault(settings)
    unlocked.unlock("unit-test-master-passphrase")
    return unlocked


@pytest.fixture()
def mock_catalog_path(tmp_path: Path) -> Path:
    """Two-provider catalog used by router tests."""
    catalog = {
        "vault_config": {"encryption_algorithm": "AES-256-GCM", "pbkdf2_iterations": 100000},
        "providers": [
            {
                "provider_id": "alpha",
                "display_name": "Alpha (primary)",
                "base_url": "https://alpha.test/v1",
                "default_model": "alpha-large",
                "supported_models": ["alpha-large", "alpha-small"],
                "auth_scheme": "bearer",
                "max_tokens_limit": 4096,
                "priority": 10,
            },
            {
                "provider_id": "beta",
                "display_name": "Beta (fallback)",
                "base_url": "https://beta.test/v1",
                "default_model": "beta-large",
                "supported_models": ["beta-large"],
                "auth_scheme": "bearer",
                "max_tokens_limit": 8192,
                "priority": 20,
            },
        ],
    }
    path = tmp_path / "providers.json"
    path.write_text(json.dumps(catalog), encoding="utf-8")
    return path


def make_router_sync(
    *,
    settings: Settings,
    vault: KeyVault,
    catalog_path: Path,
    transport: httpx.AsyncBaseTransport,
) -> ProviderRouter:
    """Build a ProviderRouter (no keys attached) wired to a mock transport."""
    client = OpenAICompatibleClient(transport=transport)
    router = ProviderRouter(settings=settings, vault=vault, client=client)
    router.load_catalog(str(catalog_path))
    return router


async def attach_key(router: ProviderRouter, vault: KeyVault, provider_id: str, api_key: str) -> None:
    """Seal + attach one provider key to a router (for async tests)."""
    record_id = f"rec-{provider_id}"
    sealed = vault.seal(api_key, aad=f"{provider_id}:{record_id}")
    await router.attach_key(
        provider_id=provider_id,
        record_id=record_id,
        sealed=sealed,
        fingerprint=KeyVault.fingerprint(api_key),
    )


def ok_completion(content: str = "hello", model: str = "alpha-large") -> bytes:
    return json.dumps(
        {
            "choices": [
                {"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}
            ],
            "usage": {"prompt_tokens": 12, "completion_tokens": 3},
            "model": model,
        }
    ).encode("utf-8")
