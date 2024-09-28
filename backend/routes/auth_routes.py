from typing import Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models.entities import User
from middlewares.auth_middleware import get_current_user
from services.social_service import serialize_user
from controllers.auth_controller import register_user, login_user

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/register")
def register_endpoint(payload: Dict[str, Any], db: Session = Depends(get_db)):
    return register_user(db, payload)


@router.post("/login")
def login_endpoint(payload: Dict[str, Any], db: Session = Depends(get_db)):
    return login_user(db, payload)


@router.get("/me")
def me_endpoint(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return serialize_user(current_user, db)
