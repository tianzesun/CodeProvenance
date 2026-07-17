"""Shared security utilities for authentication and password management.

Centralizes password hashing, verification, and validation to ensure
consistent security policies across all authentication paths.
"""
import logging
from typing import List

from fastapi import HTTPException
from passlib.context import CryptContext

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

WEAK_PASSWORDS: List[str] = [
    "password", "12345678", "qwerty", "admin", "letmein",
    "welcome", "monkey", "dragon", "master", "login",
]


def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-SHA256."""
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(password, password_hash)


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
