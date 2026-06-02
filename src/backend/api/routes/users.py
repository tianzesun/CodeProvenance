"""User management API endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.backend.config.database import get_db

router = APIRouter()


@router.get("/users")
async def list_users(db: Session = Depends(get_db)):
    """List all users for reviewer assignment."""
    from src.backend.models.database import User
    
    users = db.query(User).all()
    return [
        {
            "id": str(u.id),
            "email": u.email,
            "name": u.full_name,
            "role": u.role,
        }
        for u in users
    ]