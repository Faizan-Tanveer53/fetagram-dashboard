from typing import Dict, Any, Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from models.entities import Post, Like, Comment, User
from services.social_service import serialize_post, get_active_announcement


def list_feed_posts(db: Session, current_user_id: Optional[int] = None, page: int = 1, limit: int = 25) -> Dict[str, Any]:
    offset = max(0, (page - 1) * limit)
    posts = db.query(Post).order_by(desc(Post.created_at)).offset(offset).limit(limit).all()
    return {
        "posts": [serialize_post(p, current_user_id) for p in posts],
        "announcement": get_active_announcement(db),
        "page": page,
        "limit": limit,
    }


def create_new_post(db: Session, author: User, payload: Dict[str, Any]) -> Dict[str, Any]:
    if author.is_banned:
        raise HTTPException(status_code=403, detail="Banned accounts cannot publish posts")

    media_url = (payload.get("media_url") or payload.get("image") or "").strip()
    if not media_url:
        raise HTTPException(status_code=400, detail="media_url is required")

    post = Post(
        author_id=author.id,
        media_url=media_url,
        media_type=payload.get("media_type", "IMAGE"),
        caption=payload.get("caption", ""),
        location=payload.get("location", "Hunza Valley, Gilgit Baltistan"),
        filter_name=payload.get("filter_name", "Normal"),
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return serialize_post(post, author.id)


def toggle_like_on_post(db: Session, post_id: int, user: User) -> Dict[str, Any]:
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    existing = db.query(Like).filter(Like.post_id == post_id, Like.user_id == user.id).first()
    if existing:
        db.delete(existing)
        db.commit()
    else:
        new_like = Like(post_id=post_id, user_id=user.id)
        db.add(new_like)
        db.commit()

    db.refresh(post)
    return serialize_post(post, user.id)


def add_comment_to_post(db: Session, post_id: int, user: User, payload: Dict[str, Any]) -> Dict[str, Any]:
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Comment text is required")

    comment = Comment(post_id=post_id, user_id=user.id, text=text)
    db.add(comment)
    db.commit()
    db.refresh(post)
    return serialize_post(post, user.id)
