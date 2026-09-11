"""Encrypt integration credentials at rest (Fernet).

Used for Google/QuickBooks OAuth token blobs and any future integration secrets
(e.g. SAP Business One username/password). Call seal_credentials / unseal_credentials
for JSON-able secret dicts, or encrypt_credential / decrypt_credential for single strings.

INTEGRATION_ENCRYPTION_KEY must be set on Render (and never committed):
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

A long passphrase is also accepted — it is hashed into a Fernet key. Prefer a
Fernet.generate_key() value in production.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from typing import Any, Mapping, MutableMapping, Optional, Union

from cryptography.fernet import Fernet, InvalidToken

# Marker stored alongside ciphertext so we can tell sealed blobs from legacy plaintext.
ENC_VERSION = "v1"
ENC_MARKER = "_helm_enc"
ENC_PAYLOAD = "payload"

SecretMapping = Mapping[str, Any]
SecretDict = dict[str, Any]


class CredentialCryptoError(RuntimeError):
    """Raised when encryption is misconfigured or ciphertext cannot be opened."""


def _is_production() -> bool:
    return (os.environ.get("ENVIRONMENT") or "").strip().lower() == "production"


def _fernet_key_bytes() -> bytes:
    """
    Load Fernet key material from INTEGRATION_ENCRYPTION_KEY.

    Never hardcode a key. Set INTEGRATION_ENCRYPTION_KEY on Render (Dashboard →
    helm-company-cockpit → Environment). Generate with:
      python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    """
    raw = (os.environ.get("INTEGRATION_ENCRYPTION_KEY") or "").strip()
    if not raw:
        if _is_production():
            raise CredentialCryptoError(
                "INTEGRATION_ENCRYPTION_KEY must be set in production — "
                "generate with Fernet.generate_key() and set it on Render"
            )
        # Dev/test only: stable derived key so local restarts can still decrypt.
        seed = (os.environ.get("SESSION_SECRET") or "helm-dev-session").encode("utf-8")
        return base64.urlsafe_b64encode(hashlib.sha256(b"helm-integ-dev:" + seed).digest())

    try:
        key = raw.encode("utf-8")
        Fernet(key)  # validate shape
        return key
    except Exception as exc:
        if _is_production():
            raise CredentialCryptoError(
                "INTEGRATION_ENCRYPTION_KEY must be a valid Fernet key in production"
            ) from exc
        return base64.urlsafe_b64encode(hashlib.sha256(raw.encode("utf-8")).digest())


def _fernet() -> Fernet:
    return Fernet(_fernet_key_bytes())


def encrypt_credential(value: str) -> str:
    """Encrypt a single secret string. Returns a Fernet token (url-safe text)."""
    if value is None:
        raise CredentialCryptoError("Cannot encrypt None")
    if not isinstance(value, str):
        value = str(value)
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_credential(value: str) -> str:
    """Decrypt a Fernet token produced by encrypt_credential."""
    if not value or not isinstance(value, str):
        raise CredentialCryptoError("Cannot decrypt empty credential")
    try:
        return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise CredentialCryptoError("Invalid or wrong-key credential ciphertext") from exc


def is_sealed_credentials(value: Any) -> bool:
    """True when value is an encrypted credential blob produced by seal_credentials."""
    return (
        isinstance(value, dict)
        and value.get(ENC_MARKER) == ENC_VERSION
        and isinstance(value.get(ENC_PAYLOAD), str)
        and bool(value.get(ENC_PAYLOAD))
    )


def seal_credentials(data: Optional[SecretMapping]) -> Optional[SecretDict]:
    """
    Encrypt a secret mapping (OAuth tokens, SAP login, etc.) for Mongo storage.

    Returns None for empty input. Idempotent: already-sealed blobs are returned as-is.
    """
    if data is None:
        return None
    if not isinstance(data, Mapping):
        raise CredentialCryptoError("Credentials must be a mapping")
    if is_sealed_credentials(data):
        return dict(data)
    if not data:
        return None
    plaintext = json.dumps(dict(data), separators=(",", ":"), sort_keys=True)
    return {ENC_MARKER: ENC_VERSION, ENC_PAYLOAD: encrypt_credential(plaintext)}


def unseal_credentials(data: Any) -> Optional[SecretDict]:
    """
    Decrypt a sealed credential blob, or pass through legacy plaintext dicts.

    Accepts:
      - None / empty → None
      - sealed {_helm_enc, payload} → decrypted dict
      - legacy plaintext dict (pre-migration Google/QuickBooks tokens) → same dict
    """
    if data is None or data == "" or data == {}:
        return None
    if is_sealed_credentials(data):
        raw = decrypt_credential(data[ENC_PAYLOAD])
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise CredentialCryptoError("Decrypted credentials are not a mapping")
        return parsed
    if isinstance(data, dict):
        # Legacy plaintext — sealed on API startup / migrate_encrypt_integration_tokens.py
        return dict(data)
    raise CredentialCryptoError(f"Unexpected credential storage type: {type(data).__name__}")


def needs_reencryption(data: Any) -> bool:
    """True when stored value is legacy plaintext and should be sealed."""
    return isinstance(data, dict) and bool(data) and not is_sealed_credentials(data)


def credentials_present(data: Any) -> bool:
    """Connection check that works for sealed and plaintext storage."""
    if not data:
        return False
    if is_sealed_credentials(data):
        return True
    return isinstance(data, dict) and bool(data)
