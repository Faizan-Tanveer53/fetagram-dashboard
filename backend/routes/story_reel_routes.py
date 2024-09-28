from typing import Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models.entities import Story, Post

router = APIRouter(prefix="/api", tags=["Stories & Reels"])


@router.get("/stories")
def get_stories(db: Session = Depends(get_db)):
    stories = db.query(Story).all()
    return [
        {
            "id": s.id,
            "user_id": s.user_id,
            "username": s.user.username if s.user else "ali_travels",
            "avatar_url": s.user.avatar_url if s.user else "",
            "is_verified": bool(s.user.is_verified) if s.user else False,
            "media_url": s.media_url,
            "expires_at": s.expires_at.isoformat() if s.expires_at else None,
        }
        for s in stories
    ]


@router.get("/reels")
def get_reels(db: Session = Depends(get_db)):
    posts = db.query(Post).limit(8).all()
    return [
        {
            "id": p.id,
            "username": p.author.username if p.author else "ali_travels",
            "avatar_url": p.author.avatar_url if p.author else "",
            "is_verified": bool(p.author.is_verified) if p.author else False,
            "media_url": p.media_url,
            "caption": p.caption,
            "audio_track": f"♫ Original Audio • {p.author.username if p.author else 'fetagram'}",
            "likes_count": len(p.likes or []) + 4200,
            "comments_count": len(p.comments or []) + 118,
        }
        for p in posts
    ]
