from datetime import datetime, timedelta
from typing import Dict, Any
from sqlalchemy.orm import Session
from models.entities import User, Post, Reel, Comment, Like, Report, Message


def compute_platform_analytics(db: Session) -> Dict[str, Any]:
    now = datetime.utcnow()
    day_ago = now - timedelta(hours=24)

    total_users = db.query(User).filter(User.role == "USER").count()
    all_accounts = db.query(User).count()
    active_users_24h = db.query(User).filter(User.created_at >= day_ago, User.is_banned == False).count()
    banned_users = db.query(User).filter(User.is_banned == True).count()
    verified_users = db.query(User).filter(User.is_verified == True).count()
    total_posts = db.query(Post).count()
    total_reels = db.query(Reel).count()
    total_comments = db.query(Comment).count()
    total_likes = db.query(Like).count()
    total_messages = db.query(Message).count()
    open_reports = db.query(Report).filter(Report.status == "OPEN").count()

    return {
        "total_users": total_users,
        "all_accounts": all_accounts,
        "active_users_24h": active_users_24h,
        "banned_users": banned_users,
        "verified_users": verified_users,
        "total_posts": total_posts,
        "total_reels": total_reels,
        "total_comments": total_comments,
        "total_likes": total_likes,
        "total_messages": total_messages,
        "open_reports": open_reports,
    }
