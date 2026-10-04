"""Schemas for the AES-256-GCM Key Vault & Provider Router management."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

VaultState = Literal["locked", "unlocked"]


class VaultStatus(BaseModel):
    """Current vault state — never exposes key material."""

    state: VaultState
    kdf_algorithm: str
    pbkdf2_iterations: int
    argon2_configured: bool
    key_count: int
    active_key_count: int


class VaultUnlockRequest(BaseModel):
    """Master passphrase submission to unlock the vault."""

    passphrase: str = Field(min_length=8, max_length=512)


class ProviderKeyCreate(BaseModel):
    """Register (seal) a new provider API key."""

    provider_id: str = Field(min_length=2, max_length=64)
    label: str = Field(min_length=1, max_length=128)
    api_key: str = Field(min_length=8, max_length=4096)

    @field_validator("api_key")
    @classmethod
    def _no_whitespace(cls, value: str) -> str:
        if value.strip() != value:
            raise ValueError("API key must not begin or end with whitespace.")
        return value


class ProviderKeyOut(BaseModel):
    """A sealed key record — only a redacted fingerprint is ever exposed."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    provider_id: str
    label: str
    fingerprint: str
    status: Literal["active", "invalid", "revoked"]
    masked_hint: str
    last_verified_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ProviderKeyRotate(BaseModel):
    """Replace the plaintext of an existing sealed key."""

    api_key: str = Field(min_length=8, max_length=4096)


class ProviderVerifyResult(BaseModel):
    """Outcome of a live provider credential verification call."""

    ok: bool
    provider_id: str
    model: str
    latency_ms: float
    message: str
