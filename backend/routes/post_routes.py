from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models.entities import User
from middlewares.auth_middleware import get_current_user
from controllers.post_controller import (
    list_feed_posts,
    create_new_post,
    toggle_like_on_post,
    add_comment_to_post,
)

router = APIRouter(prefix="/api/posts", tags=["Posts & Feed"])


@router.get("")
@router.get("/feed")
def get_feed_endpoint(
    page: int = 1,
    limit: int = 25,
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    return list_feed_posts(db, current_user_id=user_id, page=page, limit=limit)


@router.post("")
@router.post("/create")
def create_post_endpoint(
    payload: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return create_new_post(db, current_user, payload)


@router.post("/{post_id}/like")
def like_post_endpoint(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return toggle_like_on_post(db, post_id, current_user)


@router.post("/{post_id}/comment")
def comment_post_endpoint(
    post_id: int,
    payload: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return add_comment_to_post(db, post_id, current_user, payload)
