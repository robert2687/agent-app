"""Tests for the KDF layer and the AES-256-GCM key vault."""

from __future__ import annotations

import pytest

from app.services.kdf import (
    KDFError,
    derive_key,
    fallback_pbkdf2_iterations,
    generate_salt,
    key_fingerprint,
)
from app.services.vault import KeyVault, SealedSecret, VaultUnlockError


class TestKDF:
    def test_pbkdf2_derivation_is_deterministic(self) -> None:
        salt = generate_salt()
        first = derive_key("passphrase", salt, algorithm="pbkdf2", iterations=100_000)
        second = derive_key("passphrase", salt, algorithm="pbkdf2", iterations=100_000)
        assert first.key == second.key
        assert len(first.key) == 32

    def test_different_salts_produce_different_keys(self) -> None:
        first = derive_key("passphrase", generate_salt(), algorithm="pbkdf2", iterations=100_000)
        second = derive_key("passphrase", generate_salt(), algorithm="pbkdf2", iterations=100_000)
        assert first.key != second.key

    def test_low_iteration_count_rejected(self) -> None:
        with pytest.raises(KDFError):
            derive_key("passphrase", generate_salt(), algorithm="pbkdf2", iterations=1000)

    def test_short_salt_rejected(self) -> None:
        with pytest.raises(KDFError):
            derive_key("passphrase", b"short", algorithm="pbkdf2", iterations=100_000)

    def test_empty_passphrase_rejected(self) -> None:
        with pytest.raises(KDFError):
            derive_key("", generate_salt(), algorithm="pbkdf2", iterations=100_000)

    def test_fingerprint_is_stable_and_short(self) -> None:
        assert key_fingerprint("nvapi-abcdef123456") == key_fingerprint("nvapi-abcdef123456")
        assert len(key_fingerprint("nvapi-abcdef123456")) == 16
        assert key_fingerprint("a") != key_fingerprint("b")

    def test_fallback_iterations_hardened(self) -> None:
        assert fallback_pbkdf2_iterations() >= 100_000


class TestKeyVault:
    def test_seal_open_roundtrip(self, vault: KeyVault) -> None:
        sealed = vault.seal("nvapi-super-secret-key", aad="nvidia_nemotron:rec1")
        assert isinstance(sealed, SealedSecret)
        assert sealed.ciphertext != b"nvapi-super-secret-key"
        assert vault.open(sealed, aad="nvidia_nemotron:rec1") == "nvapi-super-secret-key"

    def test_seal_is_non_deterministic(self, vault: KeyVault) -> None:
        first = vault.seal("same-plaintext", aad="ctx")
        second = vault.seal("same-plaintext", aad="ctx")
        assert first.ciphertext != second.ciphertext
        assert first.nonce != second.nonce
        assert first.salt != second.salt

    def test_aad_tamper_detected(self, vault: KeyVault) -> None:
        sealed = vault.seal("nvapi-key", aad="provider:rec1")
        with pytest.raises(VaultUnlockError):
            vault.open(sealed, aad="provider:rec2")

    def test_ciphertext_tamper_detected(self, vault: KeyVault) -> None:
        sealed = vault.seal("nvapi-key", aad="provider:rec1")
        corrupted = SealedSecret(
            ciphertext=b"x" + sealed.ciphertext[1:],
            nonce=sealed.nonce,
            salt=sealed.salt,
            kdf_algorithm=sealed.kdf_algorithm,
            kdf_iterations=sealed.kdf_iterations,
        )
        with pytest.raises(VaultUnlockError):
            vault.open(corrupted, aad="provider:rec1")

    def test_locked_vault_refuses_seal(self, settings) -> None:
        locked = KeyVault(settings)
        from app.core.errors import VaultLockedError

        with pytest.raises(VaultLockedError):
            locked.seal("nvapi-key", aad="ctx")

    def test_relock_requires_same_passphrase(self, settings) -> None:
        first = KeyVault(settings)
        first.unlock("unit-test-master-passphrase")
        first.lock()
        with pytest.raises(VaultUnlockError):
            first.unlock("a-completely-wrong-passphrase")
        first.unlock("unit-test-master-passphrase")  # correct one still works

    def test_sealed_records_survive_process_restart(self, settings) -> None:
        """Records sealed in one vault instance open in a fresh instance."""
        first = KeyVault(settings)
        first.unlock("unit-test-master-passphrase")
        sealed = first.seal("nvapi-restart-safe-key", aad="nvidia_nemotron:rec1")

        # Simulate a restart: brand-new vault object, same passphrase.
        second = KeyVault(settings)
        second.unlock("unit-test-master-passphrase")
        assert second.open(sealed, aad="nvidia_nemotron:rec1") == "nvapi-restart-safe-key"

    def test_mask_hides_material(self) -> None:
        masked = KeyVault.mask("nvapi-0123456789abcdef")
        assert "0123456789abcdef" not in masked
        assert masked.startswith("nvapi-")
        assert "•" in masked

    def test_argon2_derivation_when_available(self, vault: KeyVault) -> None:
        from app.services.kdf import ARGON2_AVAILABLE

        if not ARGON2_AVAILABLE:
            import pytest

            pytest.skip("argon2-cffi not installed")
        from app.services.kdf import derive_key, generate_salt

        derived = derive_key(
            "passphrase",
            generate_salt(),
            algorithm="argon2",
            argon2_time_cost=1,
            argon2_memory_cost=19_456,  # minimum policy is 8192 KiB
            argon2_parallelism=1,
        )
        assert len(derived.key) == 32
