"""Key derivation functions (PBKDF2-HMAC-SHA256 / Argon2id) for the vault.

The vault never stores a raw master key: it derives a 256-bit AES key from the
master passphrase plus a random per-record salt, using the algorithm selected
in settings. Argon2 is used when available; otherwise the caller falls back to
PBKDF2 with a hardened iteration count.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from typing import Literal

try:  # pragma: no cover - exercised implicitly via ARGON2_AVAILABLE
    from argon2.low_level import Type, hash_secret_raw

    ARGON2_AVAILABLE = True
except ImportError:  # pragma: no cover
    ARGON2_AVAILABLE = False

KDFAlgorithm = Literal["pbkdf2", "argon2"]
KEY_LENGTH_BYTES = 32  # AES-256
SALT_LENGTH_BYTES = 16
_PBKDF2_FALLBACK_ITERATIONS = 600_000


class KDFError(Exception):
    """Raised when key derivation parameters are invalid or unsupported."""


@dataclass(frozen=True, slots=True)
class DerivedKey:
    """Result of a KDF operation."""

    key: bytes
    algorithm: KDFAlgorithm
    salt: bytes
    iterations: int


def generate_salt(length: int = SALT_LENGTH_BYTES) -> bytes:
    """Cryptographically secure random salt."""
    return secrets.token_bytes(length)


def derive_key(
    passphrase: str,
    salt: bytes,
    *,
    algorithm: KDFAlgorithm = "pbkdf2",
    iterations: int = 100_000,
    argon2_time_cost: int = 3,
    argon2_memory_cost: int = 65_536,
    argon2_parallelism: int = 4,
) -> DerivedKey:
    """Derive a 256-bit key from ``passphrase`` and ``salt``.

    Raises:
        KDFError: if argon2 is requested but the runtime lacks argon2-cffi,
            or if parameters are out of policy.
    """
    if not passphrase:
        raise KDFError("Passphrase must not be empty.")
    if len(salt) < 8:
        raise KDFError("Salt must be at least 8 bytes.")

    if algorithm == "argon2":
        if not ARGON2_AVAILABLE:
            raise KDFError(
                "argon2-cffi is not installed; configure NEXUS_VAULT_KDF_ALGORITHM=pbkdf2"
            )
        if argon2_time_cost < 1 or argon2_memory_cost < 8_192 or argon2_parallelism < 1:
            raise KDFError("Argon2 parameters are below the minimum policy.")
        key = hash_secret_raw(
            secret=passphrase.encode("utf-8"),
            salt=salt,
            time_cost=argon2_time_cost,
            memory_cost=argon2_memory_cost,
            parallelism=argon2_parallelism,
            hash_len=KEY_LENGTH_BYTES,
            type=Type.ID,
        )
        return DerivedKey(key=key, algorithm="argon2", salt=salt, iterations=argon2_time_cost)

    if algorithm == "pbkdf2":
        if iterations < 100_000:
            raise KDFError("PBKDF2 iterations must be >= 100000 (OWASP minimum).")
        key = hashlib.pbkdf2_hmac(
            "sha256",
            passphrase.encode("utf-8"),
            salt,
            iterations,
            dklen=KEY_LENGTH_BYTES,
        )
        return DerivedKey(key=key, algorithm="pbkdf2", salt=salt, iterations=iterations)

    raise KDFError(f"Unsupported KDF algorithm: {algorithm!r}")


def fallback_pbkdf2_iterations() -> int:
    """Iteration count used when auto-falling back from argon2 to pbkdf2."""
    return _PBKDF2_FALLBACK_ITERATIONS


def key_fingerprint(key_material: str | bytes) -> str:
    """Non-reversible, display-safe fingerprint of a secret (first 16 hex)."""
    raw = key_material.encode("utf-8") if isinstance(key_material, str) else key_material
    digest = hashlib.sha256(raw).hexdigest()
    return digest[:16]


def constant_time_equals(left: bytes, right: bytes) -> bool:
    """Constant-time comparison to compare verification tags safely."""
    return hmac.compare_digest(left, right)
