from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from models.entities import User, Post, Like, Comment, Follow, SavedPost, SystemAnnouncement


def serialize_user(user: User, db: Optional[Session] = None, viewer_id: Optional[int] = None) -> Dict[str, Any]:
    followers_count = 0
    following_count = 0
    post_count = 0
    is_following = False
    if db is not None:
        post_count = db.query(Post).filter(Post.author_id == user.id).count()
        followers_count = db.query(Follow).filter(Follow.following_id == user.id).count()
        following_count = db.query(Follow).filter(Follow.follower_id == user.id).count()
        if viewer_id:
            is_following = (
                db.query(Follow)
                .filter(Follow.follower_id == viewer_id, Follow.following_id == user.id)
                .first()
                is not None
            )

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name or "",
        "bio": user.bio or "",
        "website": user.website or "",
        "avatar_url": user.avatar_url or "",
        "is_verified": bool(user.is_verified),
        "is_banned": bool(user.is_banned),
        "role": user.role,
        "post_count": post_count,
        "posts_count": post_count,
        "follower_count": followers_count,
        "followers_count": followers_count,
        "following_count": following_count,
        "is_following": is_following,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def serialize_post(post: Post, current_user_id: Optional[int] = None, db: Optional[Session] = None) -> Dict[str, Any]:
    likes_list = post.likes or []
    comments_list = post.comments or []
    liked_by_me = any(l.user_id == current_user_id for l in likes_list) if current_user_id else False
    saved_by_me = False
    if db is not None and current_user_id:
        saved_by_me = (
            db.query(SavedPost)
            .filter(SavedPost.post_id == post.id, SavedPost.user_id == current_user_id)
            .first()
            is not None
        )

    return {
        "id": post.id,
        "author_id": post.author_id,
        "username": post.author.username if post.author else "",
        "author_avatar": post.author.avatar_url if post.author else "",
        "author_verified": bool(post.author.is_verified) if post.author else False,
        "media_url": post.media_url,
        "media_type": post.media_type,
        "media_items": [
            {"id": m.id, "media_url": m.media_url, "media_type": m.media_type, "position": m.position}
            for m in (post.media_items or [])
        ],
        "caption": post.caption or "",
        "location": post.location or "",
        "filter_name": post.filter_name or "Normal",
        "aspect_ratio": post.aspect_ratio or "1:1",
        "likes_count": len(likes_list),
        "liked_by_me": liked_by_me,
        "saved_by_me": saved_by_me,
        "comments_count": len(comments_list),
        "comments": [
            {
                "id": c.id,
                "user_id": c.user_id,
                "username": c.user.username if c.user else "",
                "user_verified": bool(c.user.is_verified) if c.user else False,
                "text": c.text,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in comments_list
        ],
        "created_at": post.created_at.isoformat() if post.created_at else None,
    }


def get_active_announcement(db: Session) -> Optional[Dict[str, Any]]:
    now = datetime.utcnow()
    ann = (
        db.query(SystemAnnouncement)
        .filter(SystemAnnouncement.is_active == True, SystemAnnouncement.expires_at > now)
        .order_by(desc(SystemAnnouncement.created_at))
        .first()
    )
    if not ann or not ann.message.strip():
        return None
    return {
        "id": ann.id,
        "message": ann.message,
        "is_active": ann.is_active,
        "expires_at": ann.expires_at.isoformat() if ann.expires_at else None,
        "created_at": ann.created_at.isoformat() if ann.created_at else None,
    }
