from typing import Dict, Any
from fastapi import HTTPException
from sqlalchemy.orm import Session
from models.entities import User
from middlewares.auth_middleware import hash_password, verify_password, create_jwt_token
from services.social_service import serialize_user


def register_user(db: Session, payload: Dict[str, Any]) -> Dict[str, Any]:
    username = (payload.get("username") or "").strip().lower()
    email = (payload.get("email") or f"{username}@fetagram.io").strip().lower()
    password = payload.get("password") or "password123"
    full_name = payload.get("full_name") or username

    if not username:
        raise HTTPException(status_code=400, detail="Username is required")

    existing = db.query(User).filter((User.username == username) | (User.email == email)).first()
    if existing:
        raise HTTPException(status_code=409, detail="Username or email already registered")

    new_user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        bio=payload.get("bio") or "Exploring the world on Fetagram ✨",
        avatar_url=payload.get("avatar_url")
        or "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=300&q=80",
        is_verified=False,
        is_banned=False,
        role="USER",
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = create_jwt_token({"user_id": new_user.id, "username": new_user.username, "role": new_user.role})
    refresh_token = create_jwt_token({"user_id": new_user.id}, expires_seconds=604800, is_refresh=True)
    return {
        "access_token": token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": serialize_user(new_user, db),
    }


def login_user(db: Session, payload: Dict[str, Any]) -> Dict[str, Any]:
    identifier = (payload.get("username") or payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    user = db.query(User).filter((User.username == identifier) | (User.email == identifier)).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username/email or password")

    if user.is_banned:
        raise HTTPException(
            status_code=403,
            detail="ACCOUNT_BANNED: Your Fetagram account has been suspended by platform moderation.",
        )

    token = create_jwt_token({"user_id": user.id, "username": user.username, "role": user.role})
    refresh_token = create_jwt_token({"user_id": user.id}, expires_seconds=604800, is_refresh=True)
    return {
        "access_token": token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": serialize_user(user, db),
    }
