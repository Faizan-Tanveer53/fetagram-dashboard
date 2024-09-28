from datetime import datetime, timedelta
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(120), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(120), default="")
    bio = Column(Text, default="")
    website = Column(String(255), default="")
    avatar_url = Column(String(512), default="")
    is_verified = Column(Boolean, default=False)
    is_banned = Column(Boolean, default=False)
    is_private = Column(Boolean, default=False)
    role = Column(String(24), default="USER")  # USER, MODERATOR, ADMIN, SUPER_ADMIN
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    last_active_at = Column(DateTime, default=datetime.utcnow)

    posts = relationship("Post", back_populates="author", cascade="all, delete-orphan")
    stories = relationship("Story", back_populates="user", cascade="all, delete-orphan")
    reels = relationship("Reel", back_populates="author", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="user", cascade="all, delete-orphan")
    likes = relationship("Like", back_populates="user", cascade="all, delete-orphan")


class Follow(Base):
    __tablename__ = "follows"
    __table_args__ = (UniqueConstraint("follower_id", "following_id", name="uq_follower_following"),)

    id = Column(Integer, primary_key=True, index=True)
    follower_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    following_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class FollowRequest(Base):
    __tablename__ = "follow_requests"
    __table_args__ = (UniqueConstraint("requester_id", "target_id", name="uq_follow_request"),)

    id = Column(Integer, primary_key=True, index=True)
    requester_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    target_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(16), default="PENDING")
    created_at = Column(DateTime, default=datetime.utcnow)


class Block(Base):
    __tablename__ = "blocks"
    __table_args__ = (UniqueConstraint("blocker_id", "blocked_id", name="uq_user_block"),)

    id = Column(Integer, primary_key=True, index=True)
    blocker_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    blocked_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Mute(Base):
    __tablename__ = "mutes"
    __table_args__ = (UniqueConstraint("muter_id", "muted_id", name="uq_user_mute"),)

    id = Column(Integer, primary_key=True, index=True)
    muter_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    muted_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    media_url = Column(Text, nullable=False)
    media_type = Column(String(16), default="IMAGE")
    caption = Column(Text, default="")
    location = Column(String(120), default="")
    filter_name = Column(String(40), default="Normal")
    aspect_ratio = Column(String(16), default="1:1")
    comments_disabled = Column(Boolean, default=False)
    likes_hidden = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow)

    author = relationship("User", back_populates="posts")
    media_items = relationship("PostMedia", back_populates="post", cascade="all, delete-orphan")
    likes = relationship("Like", back_populates="post", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")


class PostMedia(Base):
    __tablename__ = "post_media"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    media_url = Column(Text, nullable=False)
    media_type = Column(String(16), default="IMAGE")
    display_order = Column(Integer, default=0)
    position = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    post = relationship("Post", back_populates="media_items")


class Like(Base):
    __tablename__ = "likes"
    __table_args__ = (UniqueConstraint("post_id", "user_id", name="uq_post_user_like"),)

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    post = relationship("Post", back_populates="likes")
    user = relationship("User", back_populates="likes")


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_comment_id = Column(Integer, ForeignKey("comments.id", ondelete="CASCADE"), nullable=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    post = relationship("Post", back_populates="comments")
    user = relationship("User", back_populates="comments")


class SavedPost(Base):
    __tablename__ = "saved_posts"
    __table_args__ = (UniqueConstraint("post_id", "user_id", name="uq_saved_post_user"),)

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Story(Base):
    __tablename__ = "stories"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    media_url = Column(Text, nullable=False)
    media_type = Column(String(16), default="IMAGE")
    caption = Column(Text, default="")
    expires_at = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(hours=24), index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="stories")


class StoryView(Base):
    __tablename__ = "story_views"
    __table_args__ = (UniqueConstraint("story_id", "viewer_id", name="uq_story_viewer"),)

    id = Column(Integer, primary_key=True, index=True)
    story_id = Column(Integer, ForeignKey("stories.id", ondelete="CASCADE"), nullable=False, index=True)
    viewer_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    viewed_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


class StoryReaction(Base):
    __tablename__ = "story_reactions"

    id = Column(Integer, primary_key=True, index=True)
    story_id = Column(Integer, ForeignKey("stories.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    reaction = Column(String(32), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Reel(Base):
    __tablename__ = "reels"

    id = Column(Integer, primary_key=True, index=True)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    video_url = Column(Text, default="")
    media_url = Column(Text, nullable=False)
    thumbnail_url = Column(Text, default="")
    caption = Column(Text, default="")
    audio_name = Column(String(120), default="Original Audio")
    audio_track = Column(String(120), default="Original Audio")
    view_count = Column(Integer, default=0)
    views_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    author = relationship("User", back_populates="reels")


class ReelLike(Base):
    __tablename__ = "reel_likes"
    __table_args__ = (UniqueConstraint("reel_id", "user_id", name="uq_reel_user_like"),)

    id = Column(Integer, primary_key=True, index=True)
    reel_id = Column(Integer, ForeignKey("reels.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ReelComment(Base):
    __tablename__ = "reel_comments"

    id = Column(Integer, primary_key=True, index=True)
    reel_id = Column(Integer, ForeignKey("reels.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    is_group = Column(Boolean, default=False)
    title = Column(String(120), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class ConversationMember(Base):
    __tablename__ = "conversation_members"
    __table_args__ = (UniqueConstraint("conversation_id", "user_id", name="uq_conv_member"),)

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    receiver_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    media_url = Column(Text, default="")
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    recipient_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String(32), nullable=False)
    target_id = Column(Integer, nullable=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="SET NULL"), nullable=True)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    reporter_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    target_type = Column(String(32), nullable=False)
    target_id = Column(Integer, nullable=False)
    reason = Column(String(120), nullable=False)
    description = Column(Text, default="")
    status = Column(String(32), default="PENDING")  # PENDING, RESOLVED, DISMISSED
    moderation_notes = Column(Text, default="")
    resolution_notes = Column(Text, default="")
    reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SystemAnnouncement(Base):
    __tablename__ = "system_announcements"

    id = Column(Integer, primary_key=True, index=True)
    message = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(days=7))
    created_at = Column(DateTime, default=datetime.utcnow)


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    admin_username = Column(String(64), nullable=False)
    action = Column(String(64), nullable=False)
    target_type = Column(String(32), default="")
    target_id = Column(String(64), default="")
    metadata_json = Column(Text, default="")
    details = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
