"""Key Vault endpoints: unlock/lock, key CRUD, live credential verification."""

from __future__ import annotations

import time

from fastapi import APIRouter, Response, status

from app.api.deps import ContainerDep
from app.core.errors import NotFoundError, VaultLockedError
from app.db import dao
from app.db.models import ProviderKeyRecord
from app.schemas.vault import (
    ProviderKeyCreate,
    ProviderKeyOut,
    ProviderKeyRotate,
    ProviderVerifyResult,
    VaultStatus,
    VaultUnlockRequest,
)
from app.services.llm_client import ProviderAPIError
from app.services.vault import KeyVault

router = APIRouter(prefix="/vault", tags=["vault"])


@router.get("/status", response_model=VaultStatus)
async def vault_status(container: ContainerDep) -> VaultStatus:
    """Vault lock state + sealed key counts."""
    keys = await dao.list_provider_keys(container.session_factory)
    return VaultStatus(
        state="unlocked" if container.vault.is_unlocked else "locked",
        kdf_algorithm=container.vault.kdf_algorithm,
        pbkdf2_iterations=container.settings.vault_pbkdf2_iterations,
        argon2_configured=True,
        key_count=len(keys),
        active_key_count=sum(1 for k in keys if k.status == "active"),
    )


@router.post("/unlock", response_model=VaultStatus)
async def unlock_vault(
    payload: VaultUnlockRequest, container: ContainerDep
) -> VaultStatus:
    """Derive the master key from the passphrase and unlock the vault."""
    container.vault.unlock(payload.passphrase)
    return await vault_status(container)


@router.post("/lock", response_model=VaultStatus)
async def lock_vault(container: ContainerDep) -> VaultStatus:
    """Zeroize in-memory key material."""
    container.vault.lock()
    return await vault_status(container)


@router.get("/keys", response_model=list[ProviderKeyOut])
async def list_keys(container: ContainerDep) -> list[ProviderKeyOut]:
    """List sealed keys (fingerprints only — never key material)."""
    keys = await dao.list_provider_keys(container.session_factory)
    return [_to_out(record) for record in keys]


@router.post("/keys", response_model=ProviderKeyOut, status_code=status.HTTP_201_CREATED)
async def create_key(
    payload: ProviderKeyCreate, container: ContainerDep
) -> ProviderKeyOut:
    """Seal and register a provider API key (replaces an existing active key)."""
    if not container.vault.is_unlocked:
        raise VaultLockedError("Unlock the vault before registering keys.")
    definition = container.router.get_definition(payload.provider_id)  # validates provider

    sealed = container.vault.seal(
        payload.api_key, aad=f"{definition.provider_id}:pending"
    )
    fingerprint = KeyVault.fingerprint(payload.api_key)
    record = await dao.create_provider_key(
        container.session_factory,
        provider_id=payload.provider_id,
        label=payload.label,
        sealed=sealed,
        fingerprint=fingerprint,
    )
    # Re-seal with the final record id in the AAD, then bind to the router.
    final_sealed = container.vault.seal(
        payload.api_key, aad=f"{definition.provider_id}:{record.id}"
    )
    await dao.replace_sealed_material(
        container.session_factory, record.id, final_sealed
    )
    await container.router.attach_key(
        provider_id=payload.provider_id,
        record_id=record.id,
        sealed=final_sealed,
        fingerprint=fingerprint,
        status="active",
        label=payload.label,
    )
    fresh = await dao.get_provider_key(container.session_factory, record.id)
    assert fresh is not None
    return _to_out(fresh)


@router.post("/keys/{record_id}/rotate", response_model=ProviderKeyOut)
async def rotate_key(
    record_id: str, payload: ProviderKeyRotate, container: ContainerDep
) -> ProviderKeyOut:
    """Replace the plaintext stored in an existing sealed key record."""
    if not container.vault.is_unlocked:
        raise VaultLockedError("Unlock the vault before rotating keys.")
    record = await dao.get_provider_key(container.session_factory, record_id)
    if record is None:
        raise NotFoundError(f"Key record {record_id} not found.")
    definition = container.router.get_definition(record.provider_id)

    sealed = container.vault.seal(payload.api_key, aad=f"{definition.provider_id}:{record.id}")
    fingerprint = KeyVault.fingerprint(payload.api_key)
    await dao.replace_sealed_material(
        container.session_factory,
        record.id,
        sealed,
        fingerprint=fingerprint,
    )
    await container.router.attach_key(
        provider_id=record.provider_id,
        record_id=record.id,
        sealed=sealed,
        fingerprint=fingerprint,
        status="active",
        label=record.label,
    )
    fresh = await dao.get_provider_key(container.session_factory, record.id)
    assert fresh is not None
    return _to_out(fresh)


@router.delete("/keys/{record_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_key(record_id: str, container: ContainerDep) -> Response:
    """Revoke and delete a sealed key record."""
    record = await dao.get_provider_key(container.session_factory, record_id)
    if record is None:
        raise NotFoundError(f"Key record {record_id} not found.")
    await dao.delete_provider_key(container.session_factory, record_id)
    await container.router.detach_key(record.provider_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/keys/{record_id}/verify", response_model=ProviderVerifyResult)
async def verify_key(record_id: str, container: ContainerDep) -> ProviderVerifyResult:
    """Live minimal completion against the provider to verify credentials."""
    record = await dao.get_provider_key(container.session_factory, record_id)
    if record is None:
        raise NotFoundError(f"Key record {record_id} not found.")
    definition = container.router.get_definition(record.provider_id)
    try:
        api_key = await container.router.resolve_key(record.provider_id)
    except Exception as exc:  # noqa: BLE001 - surfaced as verification failure
        return ProviderVerifyResult(
            ok=False,
            provider_id=record.provider_id,
            model=definition.default_model,
            latency_ms=0.0,
            message=f"Key resolution failed: {exc}",
        )

    try:
        started = time.perf_counter()
        result = await container.llm_client.chat(
            provider_id=definition.provider_id,
            base_url=definition.base_url,
            api_key=api_key,
            model=definition.default_model,
            messages=[{"role": "user", "content": "Reply with the single word: ok"}],
            auth_scheme=definition.auth_scheme,
            extra_headers=definition.extra_headers,
            max_tokens=8,
            temperature=0.0,
        )
        latency_ms = (time.perf_counter() - started) * 1000.0
    except ProviderAPIError as exc:
        await dao.update_provider_key_status(
            container.session_factory, record.id, "invalid" if exc.status_code in (401, 403) else record.status
        )
        return ProviderVerifyResult(
            ok=False,
            provider_id=record.provider_id,
            model=definition.default_model,
            latency_ms=0.0,
            message=exc.message,
        )

    await dao.update_provider_key_status(container.session_factory, record.id, "active")
    return ProviderVerifyResult(
        ok=True,
        provider_id=record.provider_id,
        model=definition.default_model,
        latency_ms=round(latency_ms, 1),
        message=f"Credential verified live (reply: {result.content.strip()[:32] or '(empty)'}).",
    )


def _to_out(record: ProviderKeyRecord) -> ProviderKeyOut:
    """ORM record → response model with a masked fingerprint hint."""
    return ProviderKeyOut(
        id=record.id,
        provider_id=record.provider_id,
        label=record.label,
        fingerprint=record.fingerprint,
        status=record.status,  # type: ignore[arg-type]
        masked_hint=f"{record.fingerprint[:4]}…{record.fingerprint[-4:]}",
        last_verified_at=record.last_verified_at,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )
