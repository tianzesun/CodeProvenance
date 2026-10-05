"""User management API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from src.backend.api.middleware.auth import dashboard_user
from src.backend.config.database import get_db
from src.backend.models.database import User

router = APIRouter()


# Plain ``def``: the session is synchronous, so FastAPI runs this in a worker
# thread instead of blocking the event loop.
@router.get("/users")
def list_users(
    request: Request,
    limit: int = Query(500, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    """List the caller's organization's active users for reviewer assignment.

    This used to return EVERY user in the database (email, name, role) to any
    caller, with no authentication and no organization filter.
    """
    caller = dashboard_user(request)
    organization_id = (caller or {}).get("organization_id")
    if not organization_id:
        raise HTTPException(
            status_code=403, detail="User is not associated with an organization"
        )

    users = (
        db.query(User)
        .filter(User.organization_id == organization_id, User.is_active.is_(True))
        .order_by(User.full_name, User.email)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": str(u.id),
            "email": u.email,
            "name": u.full_name,
            "role": u.role,
        }
        for u in users
    ]
