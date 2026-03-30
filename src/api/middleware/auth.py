"""
Authentication middleware for CodeProvenance API.
Handles API key validation and tenant context setting.
"""
import hashlib
from typing import Optional
from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session
from src.config.database import SessionLocal, set_tenant_context
from src.models.database import ApiKey
from src.utils.database import TenantService


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to authenticate requests using API keys.
    Validates API key and sets tenant context for RLS.
    """
    
    def __init__(self, app, exclude_paths: Optional[list] = None):
        super().__init__(app)
        self.exclude_paths = exclude_paths or [
            "/", "/docs", "/redoc", "/openapi.json", "/health"
        ]
        self.security = HTTPBearer(auto_error=False)
    
    async def dispatch(self, request: Request, call_next):
        # Skip authentication for excluded paths
        if request.url.path in self.exclude_paths:
            return await call_next(request)
        
        # Skip authentication for OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)
        
        # Get credentials from Authorization header
        credentials: Optional[HTTPAuthorizationCredentials] = await self.security(request)
        
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Extract API key from credentials
        api_key = credentials.credentials
        
        # Validate API key and get tenant
        db = SessionLocal()
        try:
            # Hash the provided API key for comparison
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()
            
            # Look up the API key in database
            db_api_key = db.query(ApiKey).filter(
                ApiKey.key_hash == key_hash,
                ApiKey.is_active == True
            ).first()
            
            if not db_api_key:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or inactive API key",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            # Check if API key has expired
            if db_api_key.expires_at and db_api_key.expires_at < datetime.utcnow():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="API key has expired",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            # Get tenant information
            tenant = db_api_key.tenant
            if not tenant or tenant.status != 'active':
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Tenant is inactive or suspended",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            # Set tenant context for RLS
            set_tenant_context(db, str(tenant.id))
            
            # Add tenant info to request state for use in endpoints
            request.state.tenant_id = tenant.id
            request.state.tenant = tenant
            request.state.api_key = db_api_key
            
            # Update last used timestamp
            db_api_key.last_used_at = datetime.utcnow()
            db.commit()
            
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication error",
            )
        finally:
            db.close()
        
        # Process request
        response = await call_next(request)
        return response


# Import datetime here to avoid circular imports
from datetime import datetime