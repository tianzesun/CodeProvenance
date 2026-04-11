"""
Authentication routes for IntegrityDesk.
"""

import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.config.settings import settings
from src.models.database import User
from src.application.services.auth_service import verify_password, get_password_hash

from src.infrastructure.email_service import EmailService

router = APIRouter()
security = HTTPBearer(auto_error=False)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class BootstrapAdminRequest(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    tenant_name: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

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

@router.get("/status")
async def auth_status(user: Optional[dict] = Depends(get_current_user_optional)):
    """Check authentication status."""
    if user:
        return {"authenticated": True, "user": user}
    return {"authenticated": False}

@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate user and return access token."""
    user = db.query(User).filter(User.email == request.email).first()
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    # Update last login
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    access_token = create_access_token(
        data={"sub": user.email, "role": user.role}
    )

    return AuthResponse(
        access_token=access_token,
        user={
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "tenant_id": user.tenant_id
        }
    )

@router.post("/bootstrap-admin", response_model=AuthResponse)
async def bootstrap_admin(request: BootstrapAdminRequest, db: Session = Depends(get_db)):
    """Create the first admin user if none exists."""
    # Check if any users exist
    existing_user = db.query(User).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="System already initialized"
        )

    # Create tenant first (simplified - in real implementation you'd create a proper tenant)
    from src.models.database import Tenant
    tenant = Tenant(name=request.tenant_name)
    db.add(tenant)
    db.flush()  # Get tenant ID

    # Create admin user
    hashed_password = get_password_hash(request.password)
    admin_user = User(
        email=request.email,
        full_name=request.full_name,
        password_hash=hashed_password,
        role="admin",
        tenant_id=tenant.id
    )

    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)

    access_token = create_access_token(
        data={"sub": admin_user.email, "role": admin_user.role}
    )

    return AuthResponse(
        access_token=access_token,
        user={
            "id": admin_user.id,
            "email": admin_user.email,
            "full_name": admin_user.full_name,
            "role": admin_user.role,
            "tenant_id": admin_user.tenant_id
        }
    )

@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """Logout endpoint - client handles token removal."""
    # In a stateless JWT system, logout is primarily handled client-side
    # We could optionally implement token blacklisting here if needed
    return {"message": "Logged out successfully", "user": current_user["email"]}

@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get current user information."""
    user = db.query(User).filter(User.email == current_user["email"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "tenant_id": user.tenant_id,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None
    }

@router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Request password reset."""
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

    # Validate new password
    if len(request.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long"
        )

    # Update password
    user.password_hash = get_password_hash(request.new_password)
    user.reset_token = None
    user.reset_token_expires = None
    db.commit()

    return {"message": "Password reset successfully"}

@router.post("/me")
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
