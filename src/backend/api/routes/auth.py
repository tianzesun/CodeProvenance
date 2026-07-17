"""
Authentication routes for IntegrityDesk.
"""

import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.backend.config.database import get_db
from src.backend.config.settings import settings
from src.backend.models.database import User
from src.backend.infrastructure.security import (
    hash_password,
    verify_password,
    validate_password_strength,
)
from src.backend.infrastructure.email_service import EmailService

router = APIRouter()
security = HTTPBearer(auto_error=False)

# Rate limiting for forgot-password: email -> last request timestamp
_forgot_password_rate_limit: dict[str, float] = {}
ForgotPassword_COOLDOWN_SECONDS = 300  # 5 minutes

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

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.AUTH_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.AUTH_JWT_SECRET, algorithm="HS256")
    return encoded_jwt

def get_current_user_optional(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[dict]:
    if not credentials:
        return None

    try:
        payload = jwt.decode(credentials.credentials, settings.AUTH_JWT_SECRET, algorithms=["HS256"])
        email: str = payload.get("sub")
        if email is None:
            return None
        return {"email": email, "role": payload.get("role", "professor")}
    except JWTError:
        return None

def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> dict:
    user = get_current_user_optional(credentials)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

@router.get("/me-api-key")
async def get_me_by_api_key(request: Request, db: Session = Depends(get_db)):
    """Get current user information by API key (for dev mode)."""
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=401, detail="API key authentication required")
    
    # For dev tenant (string), return a default dev user
    if tenant_id == "dev":
        return {
            "user": {
                "id": "dev-user-1",
                "email": "admin@dev.local",
                "full_name": "Development Admin",
                "role": "admin",
                "tenant_id": "dev",
                "last_login_at": None
            }
        }
    
    # Get user by tenant_id (first user in the tenant for dev mode)
    user = db.query(User).filter(User.tenant_id == tenant_id).first()
    
    if not user:
        # Return a default dev user if none exists
        return {
            "user": {
                "id": "dev-user-1",
                "email": "admin@dev.local",
                "full_name": "Development Admin",
                "role": "admin",
                "tenant_id": tenant_id,
                "last_login_at": None
            }
        }
    
    return {
        "user": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "tenant_id": str(user.tenant_id),
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None
        }
    }

@router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Request password reset."""
    # Rate limit: max 1 request per email per cooldown period
    now = time.time()
    last_request = _forgot_password_rate_limit.get(request.email)
    if last_request and (now - last_request) < ForgotPassword_COOLDOWN_SECONDS:
        # Always return success to avoid email enumeration
        return {"message": "If an account with this email exists, a password reset link has been sent."}

    _forgot_password_rate_limit[request.email] = now

    user = db.query(User).filter(User.email == request.email).first()

    # Always return success for security (don't reveal if email exists)
    if not user:
        return {"message": "If an account with this email exists, a password reset link has been sent."}

    # Generate reset token
    reset_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

    # Store reset token in user model (you might want to add a separate table for this)
    # For now, we'll store it in a temporary way
    user.reset_token = reset_token
    user.reset_token_expires = expires_at
    db.commit()

    # Send email with reset link
    reset_url = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?token={reset_token}"
    await EmailService.send_password_reset_email(user.email, reset_url)

    return {"message": "If an account with this email exists, a password reset link has been sent."}

@router.post("/reset-password")
async def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Reset password using token."""
    user = db.query(User).filter(
        User.reset_token == request.token,
        User.reset_token_expires > datetime.now(timezone.utc)
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
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
    request: dict,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current user information."""
    user = db.query(User).filter(User.email == current_user["email"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update allowed fields
    if "full_name" in request:
        user.full_name = request["full_name"]

    db.commit()
    db.refresh(user)

    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "tenant_id": user.tenant_id
    }
