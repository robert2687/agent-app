"""AES-256-GCM encrypted Key Vault.

Design
------
* The master passphrase (env var or operator-supplied) is stretched through
  PBKDF2/Argon2 into a 256-bit key. The key lives only in process memory while
  the vault is unlocked.
* Every stored API key is sealed with a **random per-record salt + nonce** and
  authenticated associated data (provider_id + label) so ciphertexts cannot be
  transplanted between records.
* A sealed verifier (known plaintext) lets us confirm a passphrase derives the
  same key without persisting any key material.
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import Settings
from app.core.errors import VaultLockedError, VaultUnlockError
from app.services.kdf import (
    ARGON2_AVAILABLE,
    DerivedKey,
    derive_key,
    fallback_pbkdf2_iterations,
    generate_salt,
    key_fingerprint,
)

_VAULT_CHECK_PLAINTEXT = b"nexus-vault-integrity-check-v1"
_VAULT_CHECK_AAD = b"nexus-vault-verifier"


@dataclass(frozen=True, slots=True)
class SealedSecret:
    """All material needed to persist an encrypted secret at rest."""

    ciphertext: bytes
    nonce: bytes
    salt: bytes
    kdf_algorithm: str
    kdf_iterations: int


class KeyVault:
    """In-memory-unlocked, AES-256-GCM at-rest key vault."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._derived: DerivedKey | None = None
        self._passphrase: str | None = None
        self._verifier_tag: bytes | None = None
        self._verifier_nonce: bytes | None = None
        # First unlock establishes the verifier; later unlocks must match it.
        self._verifier_salt: bytes | None = None

    # ── State ──────────────────────────────────────────────────────────────
    @property
    def is_unlocked(self) -> bool:
        return self._derived is not None

    @property
    def kdf_algorithm(self) -> str:
        return self._settings.vault_kdf_algorithm

    # ── Unlock / Lock ──────────────────────────────────────────────────────
    def unlock(self, passphrase: str) -> None:
        """Derive the master key from ``passphrase`` and unlock the vault."""
        if self.is_unlocked:
            return
        algorithm = self._settings.vault_kdf_algorithm
        iterations = self._settings.vault_pbkdf2_iterations
        if algorithm == "argon2" and not ARGON2_AVAILABLE:
            # Hard-fallback (documented) rather than bricking startup.
            algorithm = "pbkdf2"
            iterations = fallback_pbkdf2_iterations()

        salt = self._verifier_salt or generate_salt()
        try:
            derived = derive_key(
                passphrase,
                salt,
                algorithm=algorithm,
                iterations=iterations,
                argon2_time_cost=self._settings.vault_argon2_time_cost,
                argon2_memory_cost=self._settings.vault_argon2_memory_cost,
                argon2_parallelism=self._settings.vault_argon2_parallelism,
            )
        except Exception as exc:  # noqa: BLE001 - surfaced as domain error
            raise VaultUnlockError(f"Key derivation failed: {exc}") from exc

        aes = AESGCM(derived.key)
        if self._verifier_tag is None:
            # First unlock in this process: establish the verifier.
            self._derived = derived
            self._passphrase = passphrase
            self._verifier_salt = salt
            self._verifier_nonce = os.urandom(12)
            self._verifier_tag = aes.encrypt(
                self._verifier_nonce, _VAULT_CHECK_PLAINTEXT, _VAULT_CHECK_AAD
            )
            return

        try:
            plaintext = AESGCM(derived.key).decrypt(
                self._verifier_nonce, self._verifier_tag, _VAULT_CHECK_AAD
            )
        except InvalidTag as exc:
            raise VaultUnlockError("Incorrect master passphrase.") from exc
        if plaintext != _VAULT_CHECK_PLAINTEXT:
            raise VaultUnlockError("Incorrect master passphrase.")
        self._derived = derived
        self._passphrase = passphrase

    def lock(self) -> None:
        """Drop key material and re-lock the vault.

        The in-memory passphrase reference is released; the verifier persists
        so the next unlock must derive the same key again.
        """
        self._derived = None
        self._passphrase = None

    @property
    def passphrase(self) -> str:
        """The unlocked master passphrase (raises when locked)."""
        if self._passphrase is None:
            raise VaultLockedError(
                "The key vault is locked. Unlock it via POST /api/vault/unlock."
            )
        return self._passphrase

    # ── Seal / Open ────────────────────────────────────────────────────────
    def seal(self, plaintext: str, *, aad: str) -> SealedSecret:
        """Encrypt ``plaintext`` under a key derived from (passphrase, fresh salt).

        Each record carries its own random salt, so records are independently
        decryptable across process restarts: nothing about the sealing key is
        process-specific.
        """
        self.passphrase  # raises when locked
        salt = generate_salt()
        nonce = os.urandom(12)
        derived = derive_key(
            self._passphrase,
            salt,
            algorithm=self._settings.vault_kdf_algorithm,
            iterations=self._settings.vault_pbkdf2_iterations,
            argon2_time_cost=self._settings.vault_argon2_time_cost,
            argon2_memory_cost=self._settings.vault_argon2_memory_cost,
            argon2_parallelism=self._settings.vault_argon2_parallelism,
        )
        record_key = derived.key
        ciphertext = AESGCM(record_key).encrypt(
            nonce, plaintext.encode("utf-8"), aad.encode("utf-8")
        )
        return SealedSecret(
            ciphertext=ciphertext,
            nonce=nonce,
            salt=salt,
            kdf_algorithm=derived.algorithm,
            kdf_iterations=derived.iterations,
        )

    def open(self, sealed: SealedSecret, *, aad: str) -> str:
        """Decrypt a sealed secret using its own per-record KDF parameters."""
        self.passphrase  # raises when locked
        derived = derive_key(
            self._passphrase,
            sealed.salt,
            algorithm=sealed.kdf_algorithm,  # type: ignore[arg-type]
            iterations=sealed.kdf_iterations,
            argon2_time_cost=sealed.kdf_iterations if sealed.kdf_algorithm == "argon2" else 3,
            argon2_memory_cost=self._settings.vault_argon2_memory_cost,
            argon2_parallelism=self._settings.vault_argon2_parallelism,
        )
        try:
            plaintext = AESGCM(derived.key).decrypt(
                sealed.nonce, sealed.ciphertext, aad.encode("utf-8")
            )
        except InvalidTag as exc:
            raise VaultUnlockError(
                "Ciphertext authentication failed (wrong passphrase or tampered record)."
            ) from exc
        return plaintext.decode("utf-8")

    # ── Helpers ────────────────────────────────────────────────────────────
    @staticmethod
    def fingerprint(plaintext: str) -> str:
        """Stable display fingerprint (never the key itself)."""
        return key_fingerprint(plaintext)

    @staticmethod
    def mask(plaintext: str) -> str:
        """Redacted preview such as ``nvapi-••••••3f9a``."""
        if len(plaintext) <= 8:
            return "••••••••"
        head, tail = plaintext[:6], plaintext[-4:]
        return f"{head}••••••{tail}"


def utc_now() -> datetime:
    """UTC timestamp helper shared by vault-adjacent services."""
    return datetime.now(timezone.utc)


def b64(data: bytes) -> str:
    """Base64 (urlsafe) encoder for byte columns when needed."""
    return base64.urlsafe_b64encode(data).decode("ascii")


VaultStatusLiteral = Literal["locked", "unlocked"]
