"""Application configuration via pydantic-settings v2.

All settings are overridable through environment variables prefixed with
``NEXUS_`` (e.g. ``NEXUS_VAULT_MASTER_KEY``) or through a ``.env`` file.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]  # …/backend


class Settings(BaseSettings):
    """Strongly-typed, validated runtime configuration for the platform."""

    model_config = SettingsConfigDict(
        env_prefix="NEXUS_",
        env_file=str(BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── Application ────────────────────────────────────────────────────────
    app_name: str = "Nexus AI Swarm Platform"
    version: str = "1.0.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = True
    api_prefix: str = "/api"
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    # ── Persistence ────────────────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./data/nexus.db"

    # ── Key Vault (AES-256-GCM) ────────────────────────────────────────────
    vault_master_key: str | None = None
    vault_kdf_algorithm: Literal["pbkdf2", "argon2"] = "pbkdf2"
    vault_pbkdf2_iterations: int = 100_000
    vault_argon2_time_cost: int = 3
    vault_argon2_memory_cost: int = 65_536
    vault_argon2_parallelism: int = 4
    vault_auto_unlock: bool = True

    # ── Provider Router ────────────────────────────────────────────────────
    providers_config_path: str = str(BACKEND_ROOT / "app" / "config" / "providers.json")
    provider_timeout_seconds: float = 120.0
    provider_stream_timeout_seconds: float = 300.0
    rate_limit_window_seconds: int = 60
    rate_limit_max_requests: int = 20
    circuit_failure_threshold: int = 3
    circuit_reset_seconds: int = 60
    token_budget_per_job: int = 400_000

    # ── GitHub Ingestion ───────────────────────────────────────────────────
    clone_root: str = "./workspace/repos"
    clone_depth: int = 1
    max_repo_size_mb: int = 500

    # ── Swarm & Self-Healing Loop ──────────────────────────────────────────
    max_repair_iterations: int = 3
    execution_enabled: bool = True
    execution_timeout_seconds: int = 180
    lint_command: str = "ruff check --quiet ."
    test_command: str = "python -m pytest -x -q"

    # ── Event Bus ──────────────────────────────────────────────────────────
    event_bus_max_queue: int = 2_000


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached singleton settings object."""
    return Settings()
