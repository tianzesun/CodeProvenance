"""Encryption at rest for the credentials workspaces save in ``Tenant.settings``.

Workspace API keys and the SMTP password used to be stored in plain text in
the settings JSON. They are now sealed with AES-256-GCM under
``SETTINGS_ENCRYPTION_KEY``, a key that lives outside the database (injected
from the managed secret store). Each value is bound to its workspace and field
as associated data, so a sealed value copied into another workspace or field
does not decrypt.

Stored form: ``enc:v1:<base64(nonce || ciphertext || tag)>``. A value without
that prefix is a legacy plain-text value: it is still read, and is sealed on
the workspace's next save or by running this module::

    python -m src.backend.infrastructure.secret_box

which re-seals every workspace's credentials under the current key (also the
last step of a key rotation, with the old key in
``SETTINGS_ENCRYPTION_KEY_PREVIOUS``).
"""

from __future__ import annotations

import base64
import logging
import os
from collections.abc import Mapping
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)

PREFIX = "enc:v1:"
_NONCE_BYTES = 12

#: Credentials a workspace can save, as top-level ``Tenant.settings`` keys.
WORKSPACE_SECRET_FIELDS = frozenset(
    {
        "openai_api_key",
        "anthropic_api_key",
        "moss_user_id",
        "email_password",
        "sendgrid_api_key",
    }
)
#: Settings whose values are a ``{provider: key}`` map of credentials.
WORKSPACE_SECRET_MAPS = frozenset({"llm_api_keys"})


class SecretStorageUnavailable(RuntimeError):
    """No ``SETTINGS_ENCRYPTION_KEY`` is configured, so credentials cannot be stored."""


def _keys() -> list[bytes]:
    from src.backend.config.settings import settings

    keys = []
    for secret in (
        settings.SETTINGS_ENCRYPTION_KEY,
        settings.SETTINGS_ENCRYPTION_KEY_PREVIOUS,
    ):
        if secret:
            keys.append(base64.b64decode(secret.get_secret_value().strip()))
    return keys


def is_available() -> bool:
    """Whether credentials can be stored (an encryption key is configured)."""
    return bool(_keys())


def is_sealed(value: object) -> bool:
    return isinstance(value, str) and value.startswith(PREFIX)


def _aad(workspace_id: str, field: str) -> bytes:
    return f"{workspace_id}|{field}".encode()


def seal(plaintext: str, *, workspace_id: str, field: str) -> str:
    """Encrypt one credential for one workspace field.

    Raises:
        SecretStorageUnavailable: no encryption key is configured.
    """
    keys = _keys()
    if not keys:
        raise SecretStorageUnavailable("SETTINGS_ENCRYPTION_KEY is not configured")
    nonce = os.urandom(_NONCE_BYTES)
    sealed = AESGCM(keys[0]).encrypt(
        nonce, plaintext.encode(), _aad(workspace_id, field)
    )
    return PREFIX + base64.b64encode(nonce + sealed).decode()


def unseal(stored: object, *, workspace_id: str, field: str) -> str | None:
    """The plain credential, or None when it cannot be decrypted.

    A legacy plain-text value is returned unchanged.
    """
    if not isinstance(stored, str) or not stored:
        return None
    if not is_sealed(stored):
        return stored
    try:
        raw = base64.b64decode(stored[len(PREFIX) :], validate=True)
    except ValueError:
        logger.warning("Workspace %s: stored %s is malformed", workspace_id, field)
        return None
    nonce, sealed = raw[:_NONCE_BYTES], raw[_NONCE_BYTES:]
    for key in _keys():
        try:
            return (
                AESGCM(key).decrypt(nonce, sealed, _aad(workspace_id, field)).decode()
            )
        except InvalidTag:
            continue
    logger.warning(
        "Workspace %s: stored %s does not decrypt with the configured keys",
        workspace_id,
        field,
    )
    return None


def _map_field(name: str, provider: str) -> str:
    return f"{name}.{provider}"


def _reseal(value: object, workspace_id: str, field: str) -> str | None:
    """``value`` sealed under the current key (unchanged if it already is), or None if empty."""
    if is_sealed(value):
        keys = _keys()
        raw = base64.b64decode(str(value)[len(PREFIX) :])
        try:
            AESGCM(keys[0]).decrypt(
                raw[:_NONCE_BYTES], raw[_NONCE_BYTES:], _aad(workspace_id, field)
            )
            return str(value)
        except (InvalidTag, IndexError):
            pass
    plain = unseal(value, workspace_id=workspace_id, field=field)
    return seal(plain, workspace_id=workspace_id, field=field) if plain else None


def seal_record(record: Mapping[str, Any], workspace_id: str) -> dict[str, Any]:
    """A copy of a settings record with every plain-text credential sealed.

    Values sealed under a previous key are re-sealed under the current one, so
    this also completes a key rotation. Values it cannot decrypt are kept.

    Raises:
        SecretStorageUnavailable: the record holds a credential and no key is configured.
    """
    out = dict(record)
    for field in WORKSPACE_SECRET_FIELDS:
        if out.get(field):
            sealed = _reseal(out[field], workspace_id, field)
            if sealed:
                out[field] = sealed
    for name in WORKSPACE_SECRET_MAPS:
        values = out.get(name)
        if isinstance(values, Mapping):
            sealed_map = {}
            for provider, value in values.items():
                sealed = (
                    _reseal(value, workspace_id, _map_field(name, str(provider)))
                    if value
                    else None
                )
                if sealed or value:
                    sealed_map[str(provider)] = sealed or value
            out[name] = sealed_map
    return out


def open_record(record: Mapping[str, Any], workspace_id: str | None) -> dict[str, Any]:
    """A copy of a settings record with credentials decrypted (undecryptable ones dropped)."""
    out = dict(record)
    if not workspace_id:
        return out
    for field in WORKSPACE_SECRET_FIELDS:
        if field in out:
            plain = unseal(out[field], workspace_id=workspace_id, field=field)
            if plain:
                out[field] = plain
            else:
                out.pop(field)
    for name in WORKSPACE_SECRET_MAPS:
        values = out.get(name)
        if isinstance(values, Mapping):
            opened = {}
            for provider, value in values.items():
                plain = unseal(
                    value,
                    workspace_id=workspace_id,
                    field=_map_field(name, str(provider)),
                )
                if plain:
                    opened[str(provider)] = plain
            out[name] = opened
    return out


def reseal_all_workspaces() -> int:
    """Seal every workspace's stored credentials under the current key; returns workspaces changed."""
    from src.backend.config.database import SessionLocal
    from src.backend.models.database import Tenant

    changed = 0
    with SessionLocal() as db:
        for tenant in db.query(Tenant).all():
            record = tenant.settings if isinstance(tenant.settings, dict) else None
            if not record:
                continue
            sealed = seal_record(record, str(tenant.id))
            if sealed != record:
                tenant.settings = sealed
                changed += 1
        db.commit()
    return changed


if __name__ == "__main__":  # pragma: no cover - operator command
    logging.basicConfig(level=logging.INFO)
    count = reseal_all_workspaces()
    print(f"Sealed credentials in {count} workspace(s).")
