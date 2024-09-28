from typing import Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models.entities import User
from middlewares.auth_middleware import require_admin
from controllers.admin_controller import (
    get_admin_dashboard_state,
    toggle_user_ban,
    toggle_user_verify,
    delete_user_account,
    force_delete_post,
    update_global_broadcast,
)

router = APIRouter(prefix="/api/admin", tags=["Admin Portal Governance"])


@router.get("/analytics")
@router.get("/metrics")
def admin_analytics_endpoint(admin_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return get_admin_dashboard_state(db)


@router.get("/users")
def admin_users_endpoint(admin_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return get_admin_dashboard_state(db)["users"]


@router.patch("/users/{user_id}/status")
@router.patch("/users/{user_id}/ban")
def admin_toggle_ban_endpoint(user_id: int, admin_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return toggle_user_ban(db, user_id)


@router.patch("/users/{user_id}/verify")
def admin_toggle_verify_endpoint(user_id: int, admin_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return toggle_user_verify(db, user_id)


@router.delete("/users/{user_id}")
def admin_delete_user_endpoint(user_id: int, admin_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return delete_user_account(db, user_id)


@router.delete("/posts/{post_id}")
def admin_delete_post_endpoint(post_id: int, admin_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return force_delete_post(db, post_id)


@router.post("/broadcast")
def admin_broadcast_endpoint(payload: Dict[str, Any], admin_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return update_global_broadcast(db, payload)
