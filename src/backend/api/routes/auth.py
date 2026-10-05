"""
Authentication routes for IntegrityDesk.
"""

import base64
import hashlib
import logging
import secrets
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from src.backend.config.database import get_db
from src.backend.config.settings import settings
from src.backend.infrastructure.email_service import EmailService
from src.backend.infrastructure.security import (
    hash_password,
    validate_password_strength,
)
from src.backend.models.database import User

router = APIRouter()
security = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)

# Rate limiting for forgot-password: email -> last request timestamp.
# Per-process only; with several workers each keeps its own window.
_forgot_password_rate_limit: dict[str, float] = {}
FORGOT_PASSWORD_COOLDOWN_SECONDS = 300  # 5 minutes
ForgotPassword_COOLDOWN_SECONDS = FORGOT_PASSWORD_COOLDOWN_SECONDS  # legacy name
_RATE_LIMIT_PRUNE_THRESHOLD = 1000

#: How long an emailed reset link stays valid.
RESET_TOKEN_TTL = timedelta(hours=1)

_FORGOT_PASSWORD_MESSAGE = (
    "If an account with this email exists, a password reset link has been sent."
)


class LoginRequest(BaseModel):
    email: str
    password: str


class BootstrapAdminRequest(BaseModel):
    email: str
    full_name: str
    password: str
    tenant_name: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class UpdateMeRequest(BaseModel):
    """Fields a user may change on their own profile."""

    full_name: str | None = Field(None, max_length=255)

    @field_validator("full_name")
    @classmethod
    def _full_name_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Full name must not be blank")
        return value


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


def create_access_token(
    data: dict, expires_delta: timedelta | None = None
) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.AUTH_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": now})
    encoded_jwt = jwt.encode(to_encode, settings.auth_jwt_secret, algorithm="HS256")
    return encoded_jwt


def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict | None:
    if not credentials:
        return None

    try:
        # Require ``exp``: python-jose only checks it when present, so a token
        # minted without one would otherwise never expire.
        payload = jwt.decode(
            credentials.credentials,
            settings.auth_jwt_secret,
            algorithms=["HS256"],
            options={"require_exp": True},
        )
        email = payload.get("sub")
        if not isinstance(email, str) or not email:
            return None
        return {"email": email, "role": payload.get("role", "professor")}
    except JWTError:
        return None


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    user = get_current_user_optional(credentials)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def _hash_reset_token(token: str) -> str:
    """Return the value stored for a reset token (SHA-256, URL-safe base64).

    Only this digest is persisted, so a database read cannot be replayed as a
    working reset link. It is 43 characters, the same length as the raw token,
    so it fits the existing column.
    """
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _prune_rate_limit(now: float) -> None:
    """Drop expired cooldown entries so the dict cannot grow without bound."""
    if len(_forgot_password_rate_limit) < _RATE_LIMIT_PRUNE_THRESHOLD:
        return
    expired = [
        key
        for key, seen in _forgot_password_rate_limit.items()
        if now - seen >= FORGOT_PASSWORD_COOLDOWN_SECONDS
    ]
    for key in expired:
        del _forgot_password_rate_limit[key]


async def _send_reset_email(to_email: str, reset_url: str) -> None:
    """Send the reset email after the response has gone out.

    Sending inline made the "account exists" path slower than the "no such
    account" path (a timing oracle), and a mail failure turned into a 500 that
    revealed the account exists. Failures are logged without the address.
    """
    try:
        await EmailService.send_password_reset_email(to_email, reset_url)
    except Exception:
        logger.exception("Failed to send password reset email")


@router.get("/me-api-key")
async def get_me_by_api_key(request: Request, db: Session = Depends(get_db)):
    """Get current user information by API key (for dev mode)."""
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=401, detail="API key authentication required")

    debug_mode = bool(getattr(settings, "DEBUG_MODE", False))

    def _dev_user(tid) -> dict:
        return {
            "user": {
                "id": "dev-user-1",
                "email": "admin@dev.local",
                "full_name": "Development Admin",
                "role": "admin",
                "tenant_id": str(tid),
                "last_login_at": None,
            }
        }

    # The synthetic admin is for local development only. Without this guard an
    # API key resolving to the "dev" tenant would be shown as an admin anywhere.
    if tenant_id == "dev":
        if not debug_mode:
            raise HTTPException(status_code=403, detail="Not available")
        return _dev_user("dev")

    # Get user by tenant_id (first user in the tenant for dev mode)
    user = db.query(User).filter(User.tenant_id == tenant_id).first()

    if not user:
        # Never invent an admin for a real tenant outside development.
        if not debug_mode:
            raise HTTPException(status_code=404, detail="User not found")
        return _dev_user(tenant_id)

    return {
        "user": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "tenant_id": str(user.tenant_id) if user.tenant_id is not None else None,
            "last_login_at": (
                user.last_login_at.isoformat() if user.last_login_at else None
            ),
        }
    }


@router.post("/forgot-password")
async def forgot_password(
    request: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Request password reset."""
    # Mirror how every other path stores addresses (register, create-user and
    # login all normalize), otherwise `Prof@Uni.EDU` fails the lookup and the
    # user is told an email is coming that was never sent.
    email = request.email.strip().lower()

    # Rate limit: max 1 request per email per cooldown period
    now = time.time()
    _prune_rate_limit(now)
    last_request = _forgot_password_rate_limit.get(email)
    if last_request and (now - last_request) < FORGOT_PASSWORD_COOLDOWN_SECONDS:
        # Always return success to avoid email enumeration
        return {"message": _FORGOT_PASSWORD_MESSAGE}

    _forgot_password_rate_limit[email] = now

    user = db.query(User).filter(User.email == email).first()

    # Always return success for security (don't reveal if email exists or is
    # deactivated).
    if not user or not getattr(user, "is_active", True):
        return {"message": _FORGOT_PASSWORD_MESSAGE}

    # Generate reset token; only its hash is stored.
    reset_token = secrets.token_urlsafe(32)
    to_email = user.email
    user.reset_token = _hash_reset_token(reset_token)
    user.reset_token_expires = datetime.now(timezone.utc) + RESET_TOKEN_TTL
    db.commit()

    reset_url = (
        f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?token={reset_token}"
    )
    background_tasks.add_task(_send_reset_email, to_email, reset_url)

    return {"message": _FORGOT_PASSWORD_MESSAGE}


@router.post("/reset-password")
async def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Reset password using token."""
    user = (
        db.query(User)
        .filter(
            User.reset_token == _hash_reset_token(request.token),
            User.reset_token_expires > datetime.now(timezone.utc),
        )
        .first()
    )

    if not user or not getattr(user, "is_active", True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    # Validate new password strength (same rules as all other paths)
    validate_password_strength(request.new_password)

    # Update password
    user.password_hash = hash_password(request.new_password)
    user.reset_token = None
    user.reset_token_expires = None
    db.commit()

    return {"message": "Password reset successfully"}


@router.put("/me")
async def update_me(
    payload: UpdateMeRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update current user information."""
    user = (
        db.query(User)
        .filter(User.email == current_user["email"].strip().lower())
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not getattr(user, "is_active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Update allowed fields
    if payload.full_name is not None:
        user.full_name = payload.full_name

    db.commit()
    db.refresh(user)

    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "tenant_id": str(user.tenant_id) if user.tenant_id is not None else None,
    }
