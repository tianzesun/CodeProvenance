"""Shared security utilities for authentication and password management.

Centralizes password hashing, verification, and validation to ensure
consistent security policies across all authentication paths.
"""

import logging

from fastapi import HTTPException
from passlib.context import CryptContext

logger = logging.getLogger(__name__)

#: Argon2id for every new hash (the U of T Secure Development Baseline's approved
#: password algorithm). PBKDF2-SHA256 hashes stored before stay verifiable and are
#: replaced on the user's next successful sign-in (``verify_and_update``).
pwd_context = CryptContext(
    schemes=["argon2", "pbkdf2_sha256"],
    deprecated=["pbkdf2_sha256"],
    argon2__type="ID",
)

WEAK_PASSWORDS: list[str] = [
    "password",
    "12345678",
    "qwerty",
    "admin",
    "letmein",
    "welcome",
    "monkey",
    "dragon",
    "master",
    "login",
]


def hash_password(password: str) -> str:
    """Hash a password with Argon2id."""
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash (Argon2id, or a legacy PBKDF2 hash)."""
    return pwd_context.verify(password, password_hash)


def verify_and_upgrade_password(
    password: str, password_hash: str
) -> tuple[bool, str | None]:
    """Verify, and return a replacement Argon2id hash when the stored one is legacy.

    Returns:
        ``(verified, new_hash)``; ``new_hash`` is None unless the password was
        right and the stored hash should be replaced.
    """
    return pwd_context.verify_and_update(password, password_hash)


def validate_password_strength(password: str) -> None:
    """Validate password meets security requirements.

    Raises HTTPException (400) if the password is too weak.
    Skips validation when DEBUG_MODE is enabled for easier testing.
    """
    from src.backend.config.settings import settings

    if settings.DEBUG_MODE:
        return

    if len(password) < 12:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 12 characters long",
        )
    if not any(c.isupper() for c in password):
        raise HTTPException(
            status_code=400,
            detail="Password must contain at least one uppercase letter",
        )
    if not any(c.islower() for c in password):
        raise HTTPException(
            status_code=400,
            detail="Password must contain at least one lowercase letter",
        )
    if not any(c.isdigit() for c in password):
        raise HTTPException(
            status_code=400,
            detail="Password must contain at least one number",
        )
    if password.lower() in WEAK_PASSWORDS:
        raise HTTPException(
            status_code=400,
            detail="Password is too common. Please choose a stronger password",
        )
