"""At-rest encryption helpers for integration credentials."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("SESSION_SECRET", "test-session-secret-for-crypto-unit-tests")
os.environ["INTEGRATION_ENCRYPTION_KEY"] = Fernet.generate_key().decode()

import credential_crypto as cc  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_key(monkeypatch):
    monkeypatch.setenv("INTEGRATION_ENCRYPTION_KEY", Fernet.generate_key().decode())


def test_encrypt_decrypt_string_roundtrip():
    cipher = cc.encrypt_credential("sap-password-plaintext")
    assert cipher != "sap-password-plaintext"
    assert cc.decrypt_credential(cipher) == "sap-password-plaintext"


def test_seal_unseal_dict_roundtrip():
    tokens = {"access_token": "ya29.abc", "refresh_token": "1//xyz", "expires_at": 1700000000}
    sealed = cc.seal_credentials(tokens)
    assert isinstance(sealed, dict)
    assert sealed.get("_helm_enc") == "v1"
    assert "access_token" not in sealed
    assert "ya29" not in str(sealed)
    assert cc.unseal_credentials(sealed) == tokens


def test_unseal_legacy_plaintext_passthrough():
    legacy = {"access_token": "plain", "refresh_token": "plain-r"}
    assert cc.unseal_credentials(legacy) == legacy
    assert cc.needs_reencryption(legacy) is True
    assert cc.credentials_present(legacy) is True


def test_credentials_present_sealed():
    sealed = cc.seal_credentials({"access_token": "x"})
    assert cc.credentials_present(sealed) is True
    assert cc.needs_reencryption(sealed) is False
    assert cc.credentials_present(None) is False
    assert cc.credentials_present({}) is False


def test_seal_none_and_empty():
    assert cc.seal_credentials(None) is None
    assert cc.seal_credentials({}) is None
    assert cc.unseal_credentials(None) is None


def test_already_sealed_is_idempotent():
    sealed = cc.seal_credentials({"access_token": "once"})
    again = cc.seal_credentials(sealed)
    assert again == sealed
    assert cc.unseal_credentials(again)["access_token"] == "once"


def test_production_rejects_non_fernet_key(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("INTEGRATION_ENCRYPTION_KEY", "weak-passphrase")
    with pytest.raises(cc.CredentialCryptoError):
        cc.encrypt_credential("secret")


def test_encryption_key_is_fernet_and_assert_ready(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("INTEGRATION_ENCRYPTION_KEY", key)
    assert cc.encryption_key_is_fernet() is True
    assert cc.assert_encryption_ready() == key.encode("utf-8")
    monkeypatch.delenv("INTEGRATION_ENCRYPTION_KEY", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")
    assert cc.encryption_key_is_fernet() is False
