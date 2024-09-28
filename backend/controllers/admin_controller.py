from typing import Dict, Any
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from models.entities import User, Post, SystemAnnouncement
from services.social_service import serialize_user, serialize_post, get_active_announcement
from services.admin_service import compute_platform_analytics


def get_admin_dashboard_state(db: Session) -> Dict[str, Any]:
    users = db.query(User).order_by(desc(User.created_at)).all()
    posts = db.query(Post).order_by(desc(Post.created_at)).all()
    return {
        "analytics": compute_platform_analytics(db),
        "users": [serialize_user(u, db) for u in users],
        "posts": [serialize_post(p) for p in posts],
        "announcement": get_active_announcement(db),
    }


def toggle_user_ban(db: Session, user_id: int) -> Dict[str, Any]:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_banned = not bool(user.is_banned)
    db.commit()
    db.refresh(user)
    return serialize_user(user, db)


def toggle_user_verify(db: Session, user_id: int) -> Dict[str, Any]:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_verified = not bool(user.is_verified)
    db.commit()
    db.refresh(user)
    return serialize_user(user, db)


def delete_user_account(db: Session, user_id: int) -> Dict[str, Any]:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"deleted_user_id": user_id, "status": "ok"}


def force_delete_post(db: Session, post_id: int) -> Dict[str, Any]:
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    db.delete(post)
    db.commit()
    return {"deleted_post_id": post_id, "status": "ok"}


def update_global_broadcast(db: Session, payload: Dict[str, Any]) -> Dict[str, Any]:
    message = (payload.get("message") or "").strip()
    db.query(SystemAnnouncement).update({SystemAnnouncement.is_active: False})
    if message:
        ann = SystemAnnouncement(message=message, is_active=True)
        db.add(ann)
    db.commit()
    return {"announcement": get_active_announcement(db)}
