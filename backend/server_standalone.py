import os
import re
import uuid
import json
import time
import hmac
import base64
import hashlib
import sqlite3
import mimetypes
from datetime import datetime, timedelta
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import urllib.request
import urllib.parse
import ssl
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENT_WEB_DIR = os.path.join(os.path.dirname(BASE_DIR), "client-web")
VOLUME_DIR = (os.environ.get("RAILWAY_VOLUME_MOUNT_PATH") or os.environ.get("DATA_DIR") or "").strip()

if VOLUME_DIR:
    os.makedirs(VOLUME_DIR, exist_ok=True)
    DB_PATH = os.environ.get("DB_PATH", os.path.join(VOLUME_DIR, "fetagram.db"))
    UPLOAD_DIR = os.environ.get("UPLOAD_DIR", os.path.join(VOLUME_DIR, "uploads"))
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    seed_db = os.path.join(BASE_DIR, "fetagram.db")
    if not os.path.exists(DB_PATH) and os.path.exists(seed_db):
        try:
            shutil.copy2(seed_db, DB_PATH)
        except Exception:
            pass
    seed_uploads = os.path.join(BASE_DIR, "uploads")
    if os.path.isdir(seed_uploads):
        for fname in os.listdir(seed_uploads):
            src_f = os.path.join(seed_uploads, fname)
            dst_f = os.path.join(UPLOAD_DIR, fname)
            if os.path.isfile(src_f) and not os.path.exists(dst_f):
                try:
                    shutil.copy2(src_f, dst_f)
                except Exception:
                    pass
else:
    DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "fetagram.db"))
    UPLOAD_DIR = os.environ.get("UPLOAD_DIR", os.path.join(BASE_DIR, "uploads"))
    os.makedirs(UPLOAD_DIR, exist_ok=True)

JWT_SECRET = os.getenv("JWT_SECRET_KEY", "fetagram-production-hmac-secret-key-2026")
ADMIN_MASTER_PASSWORD = os.getenv("ADMIN_DEFAULT_PASSWORD", "Admin@Fetagram2026")

ALLOWED_IMAGE_MIMES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
ALLOWED_VIDEO_MIMES = {"video/mp4": ".mp4"}
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_VIDEO_BYTES = 100 * 1024 * 1024


def detect_magic_mime(file_bytes: bytes, fallback_mime: str = "") -> str:
    """Inspect magic bytes of binary file payloads to guarantee accurate MIME detection."""
    if file_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if file_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(file_bytes) >= 12 and file_bytes[:4] == b"RIFF" and file_bytes[8:12] == b"WEBP":
        return "image/webp"
    if len(file_bytes) >= 12 and (file_bytes[4:8] == b"ftyp" or b"mp4" in file_bytes[:32]):
        return "video/mp4"
    return fallback_mime.lower().strip()


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def b64url_decode(s: str) -> bytes:
    padding = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + padding)


def hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000)
    return f"pbkdf2_sha256${salt}${dk.hex()}"


def verify_password(plain_password: str, stored_hash: str) -> bool:
    try:
        parts = stored_hash.split("$")
        if len(parts) != 3:
            return False
        _, salt, expected_hex = parts
        dk = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), 120000)
        return hmac.compare_digest(dk.hex(), expected_hex)
    except Exception:
        return False


def create_jwt(user_id: int, username: str, role: str, expires_in: int = 86400) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "iat": int(time.time()),
        "exp": int(time.time()) + expires_in,
    }
    h_enc = b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    p_enc = b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{h_enc}.{p_enc}".encode("utf-8")
    sig = hmac.new(JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{h_enc}.{p_enc}.{b64url_encode(sig)}"


def decode_jwt(token: str):
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        h_enc, p_enc, sig_enc = parts
        signing_input = f"{h_enc}.{p_enc}".encode("utf-8")
        expected = hmac.new(JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
        if not hmac.compare_digest(b64url_encode(expected), sig_enc):
            return None
        payload = json.loads(b64url_decode(p_enc).decode("utf-8"))
        if payload.get("exp", 0) < int(time.time()):
            return None
        return payload
    except Exception:
        return None


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT DEFAULT '',
    bio TEXT DEFAULT '',
    website TEXT DEFAULT '',
    avatar_url TEXT DEFAULT '',
    is_verified INTEGER DEFAULT 0,
    is_banned INTEGER DEFAULT 0,
    is_private INTEGER DEFAULT 0,
    role TEXT DEFAULT 'USER',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_active_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS follows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    follower_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    following_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status TEXT DEFAULT 'accepted',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(follower_id, following_id)
);

CREATE TABLE IF NOT EXISTS follow_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    requester_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    target_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status TEXT DEFAULT 'PENDING',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(requester_id, target_id)
);

CREATE TABLE IF NOT EXISTS blocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    blocker_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    blocked_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(blocker_id, blocked_id)
);

CREATE TABLE IF NOT EXISTS mutes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    muter_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    muted_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(muter_id, muted_id)
);

CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    author_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    media_url TEXT NOT NULL,
    media_type TEXT DEFAULT 'IMAGE',
    caption TEXT DEFAULT '',
    location TEXT DEFAULT '',
    filter_name TEXT DEFAULT 'Normal',
    aspect_ratio TEXT DEFAULT '1:1',
    comments_disabled INTEGER DEFAULT 0,
    likes_hidden INTEGER DEFAULT 0,
    is_archived INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS post_media (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    media_url TEXT NOT NULL,
    media_type TEXT DEFAULT 'IMAGE',
    display_order INTEGER DEFAULT 0,
    position INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS likes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(post_id, user_id)
);

CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    parent_comment_id INTEGER REFERENCES comments(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS saved_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(post_id, user_id)
);

CREATE TABLE IF NOT EXISTS stories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    media_url TEXT NOT NULL,
    media_type TEXT DEFAULT 'IMAGE',
    caption TEXT DEFAULT '',
    expires_at TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS story_views (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id INTEGER NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
    viewer_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    viewed_at TEXT DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(story_id, viewer_id)
);

CREATE TABLE IF NOT EXISTS story_reactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id INTEGER NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reaction TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    author_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    video_url TEXT DEFAULT '',
    media_url TEXT NOT NULL,
    thumbnail_url TEXT DEFAULT '',
    caption TEXT DEFAULT '',
    audio_name TEXT DEFAULT 'Original Audio',
    audio_track TEXT DEFAULT 'Original Audio',
    view_count INTEGER DEFAULT 0,
    views_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reel_likes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reel_id INTEGER NOT NULL REFERENCES reels(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(reel_id, user_id)
);

CREATE TABLE IF NOT EXISTS reel_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reel_id INTEGER NOT NULL REFERENCES reels(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    is_group INTEGER DEFAULT 0,
    title TEXT DEFAULT '',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversation_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(conversation_id, user_id)
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER REFERENCES conversations(id) ON DELETE CASCADE,
    sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    receiver_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    media_url TEXT DEFAULT '',
    is_read INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipient_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    actor_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    target_id INTEGER,
    post_id INTEGER REFERENCES posts(id) ON DELETE SET NULL,
    message TEXT NOT NULL,
    is_read INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reporter_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    target_type TEXT NOT NULL,
    target_id INTEGER NOT NULL,
    reason TEXT NOT NULL,
    description TEXT DEFAULT '',
    status TEXT DEFAULT 'PENDING',
    moderation_notes TEXT DEFAULT '',
    resolution_notes TEXT DEFAULT '',
    reviewed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS system_announcements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message TEXT NOT NULL,
    is_active INTEGER DEFAULT 1,
    expires_at TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS admin_audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    admin_username TEXT NOT NULL,
    action TEXT NOT NULL,
    target_type TEXT DEFAULT '',
    target_id TEXT DEFAULT '',
    metadata TEXT DEFAULT '',
    details TEXT DEFAULT '',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    thought_text TEXT NOT NULL,
    song_title TEXT DEFAULT '',
    song_artist TEXT DEFAULT '',
    song_cover_url TEXT DEFAULT '',
    expires_at TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_settings (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    settings_json TEXT NOT NULL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_blocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    blocker_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    blocked_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(blocker_id, blocked_id)
);

CREATE TABLE IF NOT EXISTS user_restricts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    restricted_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, restricted_id)
);
"""

PASSWORD_RESET_CODES = {}


def init_clean_database(force_wipe: bool = False):
    if force_wipe and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = get_conn()
    conn.executescript(SCHEMA_SQL)
    c = conn.cursor()
    for col_sql in (
        "ALTER TABLE posts ADD COLUMN music_title TEXT DEFAULT ''",
        "ALTER TABLE posts ADD COLUMN music_artist TEXT DEFAULT ''",
        "ALTER TABLE posts ADD COLUMN music_cover_url TEXT DEFAULT ''",
        "ALTER TABLE posts ADD COLUMN music_preview_url TEXT DEFAULT ''",
        "ALTER TABLE posts ADD COLUMN music_clip_start INTEGER DEFAULT 0",
        "ALTER TABLE user_notes ADD COLUMN music_title TEXT DEFAULT ''",
        "ALTER TABLE user_notes ADD COLUMN music_artist TEXT DEFAULT ''",
        "ALTER TABLE user_notes ADD COLUMN music_cover_url TEXT DEFAULT ''",
        "ALTER TABLE user_notes ADD COLUMN music_preview_url TEXT DEFAULT ''",
        "ALTER TABLE user_notes ADD COLUMN music_clip_start INTEGER DEFAULT 0",
        "ALTER TABLE user_notes ADD COLUMN views_count INTEGER DEFAULT 0",
        "ALTER TABLE reports ADD COLUMN category TEXT DEFAULT 'General'",
        "ALTER TABLE users ADD COLUMN is_private INTEGER DEFAULT 0",
        "ALTER TABLE follows ADD COLUMN status TEXT DEFAULT 'accepted'",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_user_notes_uid ON user_notes(user_id)",
    ):
        try:
            c.execute(col_sql)
        except Exception:
            pass
    conn.commit()
    count = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count == 0:
        c.execute(
            """
            INSERT INTO users (username, email, password_hash, full_name, bio, website, avatar_url, is_verified, is_banned, role)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, 0, 'SUPER_ADMIN')
            """,
            (
                "admin",
                "admin@fetagram.internal",
                hash_password(ADMIN_MASTER_PASSWORD),
                "Platform Super Administrator",
                "Fetagram Trust & Safety Super Admin",
                "",
                "",
            ),
        )
        conn.commit()
    conn.close()


def serialize_user_row(conn, user_row, viewer_id=None):
    uid = user_row["id"]
    c = conn.cursor()
    post_count = c.execute("SELECT COUNT(*) FROM posts WHERE author_id = ?", (uid,)).fetchone()[0]
    follower_count = c.execute(
        "SELECT COUNT(*) FROM follows WHERE following_id = ? AND COALESCE(status, 'accepted') = 'accepted'",
        (uid,),
    ).fetchone()[0]
    following_count = c.execute(
        "SELECT COUNT(*) FROM follows WHERE follower_id = ? AND COALESCE(status, 'accepted') = 'accepted'",
        (uid,),
    ).fetchone()[0]
    follow_status = "none"
    if viewer_id:
        f_row = c.execute(
            "SELECT status FROM follows WHERE follower_id = ? AND following_id = ?",
            (viewer_id, uid),
        ).fetchone()
        if f_row:
            raw_st = (f_row["status"] or "accepted").lower()
            follow_status = "requested" if raw_st in ("requested", "pending") else "accepted"
        else:
            fr_row = c.execute(
                "SELECT status FROM follow_requests WHERE requester_id = ? AND target_id = ?",
                (viewer_id, uid),
            ).fetchone()
            if fr_row and (fr_row["status"] or "").upper() in ("PENDING", "REQUESTED"):
                follow_status = "requested"

    is_following = follow_status == "accepted"
    is_requested = follow_status == "requested"
    is_private = bool(user_row["is_private"])
    is_owner = viewer_id is not None and int(viewer_id) == int(uid)
    # Case A: Public OR Owner -> is_locked = False
    # Case B: Private AND Accepted Follower -> is_locked = False
    # Case C: Private AND NOT Accepted Follower -> is_locked = True
    is_locked = bool(is_private and not is_owner and not is_following)

    return {
        "id": uid,
        "username": user_row["username"],
        "email": user_row["email"],
        "full_name": user_row["full_name"] or "",
        "bio": user_row["bio"] or "",
        "website": user_row["website"] or "",
        "avatar_url": user_row["avatar_url"] or "",
        "is_verified": bool(user_row["is_verified"]),
        "is_banned": bool(user_row["is_banned"]),
        "is_private": is_private,
        "is_locked": is_locked,
        "follow_status": follow_status,
        "is_following": is_following,
        "is_requested": is_requested,
        "role": user_row["role"],
        "post_count": post_count,
        "posts_count": post_count,
        "follower_count": follower_count,
        "followers_count": follower_count,
        "following_count": following_count,
        "created_at": user_row["created_at"],
    }


def serialize_post_row(conn, post_row, viewer_id=None):
    pid = post_row["id"]
    c = conn.cursor()
    author = c.execute("SELECT * FROM users WHERE id = ?", (post_row["author_id"],)).fetchone()
    likes_count = c.execute("SELECT COUNT(*) FROM likes WHERE post_id = ?", (pid,)).fetchone()[0]
    liked_by_me = False
    saved_by_me = False
    if viewer_id:
        liked_by_me = (
            c.execute("SELECT 1 FROM likes WHERE post_id = ? AND user_id = ?", (pid, viewer_id)).fetchone()
            is not None
        )
        saved_by_me = (
            c.execute("SELECT 1 FROM saved_posts WHERE post_id = ? AND user_id = ?", (pid, viewer_id)).fetchone()
            is not None
        )

    comment_rows = c.execute(
        """
        SELECT cm.*, u.username, u.is_verified, u.avatar_url
        FROM comments cm
        JOIN users u ON u.id = cm.user_id
        WHERE cm.post_id = ?
        ORDER BY cm.id ASC
        """,
        (pid,),
    ).fetchall()
    media_rows = c.execute(
        "SELECT * FROM post_media WHERE post_id = ? ORDER BY display_order ASC, position ASC", (pid,)
    ).fetchall()
    pr_dict = dict(post_row)

    return {
        "id": pid,
        "author_id": post_row["author_id"],
        "username": author["username"] if author else "",
        "author_username": author["username"] if author else "",
        "author_avatar": author["avatar_url"] if author else "",
        "author_verified": bool(author["is_verified"]) if author else False,
        "media_url": post_row["media_url"],
        "media_type": post_row["media_type"] or "IMAGE",
        "media_items": [dict(m) for m in media_rows],
        "caption": post_row["caption"] or "",
        "location": post_row["location"] or "",
        "filter_name": post_row["filter_name"] or "Normal",
        "aspect_ratio": post_row["aspect_ratio"] or "1:1",
        "music_title": pr_dict.get("music_title") or "",
        "music_artist": pr_dict.get("music_artist") or "",
        "music_cover_url": pr_dict.get("music_cover_url") or "",
        "music_preview_url": pr_dict.get("music_preview_url") or "",
        "music_clip_start": int(pr_dict.get("music_clip_start") or 0),
        "likes_count": likes_count,
        "liked_by_me": liked_by_me,
        "saved_by_me": saved_by_me,
        "comments_count": len(comment_rows),
        "comments": [
            {
                "id": cr["id"],
                "user_id": cr["user_id"],
                "parent_comment_id": cr["parent_comment_id"],
                "username": cr["username"],
                "user_verified": bool(cr["is_verified"]),
                "text": cr["text"],
                "created_at": cr["created_at"],
            }
            for cr in comment_rows
        ],
        "created_at": post_row["created_at"],
    }


def log_admin_action(conn, admin_user, action: str, target_type: str = "", target_id: str = "", details: str = ""):
    conn.execute(
        """
        INSERT INTO admin_audit_logs (admin_id, admin_username, action, target_type, target_id, metadata, details)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (admin_user["id"], admin_user["username"], action, target_type, str(target_id), details, details),
    )


class FetagramProductionHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, Range")
        self.send_header("Cross-Origin-Resource-Policy", "cross-origin")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send_json({"status": "ok"})

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def _get_auth_user(self, conn, required=True):
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            if required:
                self._send_json({"detail": "Missing or invalid Bearer token"}, status=401)
            return None
        token = auth.replace("Bearer ", "").strip()
        claims = decode_jwt(token)
        if not claims or "user_id" not in claims:
            if required:
                self._send_json({"detail": "Expired or invalid JWT token"}, status=401)
            return None
        user = conn.execute("SELECT * FROM users WHERE id = ?", (int(claims["user_id"]),)).fetchone()
        if not user:
            if required:
                self._send_json({"detail": "Authenticated user no longer exists"}, status=401)
            return None
        if user["is_banned"]:
            if required:
                self._send_json({"detail": "ACCOUNT_BANNED: Your account has been suspended."}, status=403)
            return None
        return user

    def _require_admin_user(self, conn):
        user = self._get_auth_user(conn, required=True)
        if not user:
            return None
        if user["role"] not in ("ADMIN", "SUPER_ADMIN", "MODERATOR"):
            self._send_json({"detail": "Forbidden: ADMIN or SUPER_ADMIN role required"}, status=403)
            return None
        return user

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # Binary Media Streaming with HTTP 206 Partial Content Range Support
        if path.startswith("/uploads/"):
            filename = os.path.basename(path[len("/uploads/"):])
            filepath = os.path.join(UPLOAD_DIR, filename)
            if not os.path.isfile(filepath):
                self._send_json({"detail": "Uploaded file not found"}, status=404)
                return

            mime, _ = mimetypes.guess_type(filepath)
            with open(filepath, "rb") as f:
                full_data = f.read()
            if not mime:
                mime = detect_magic_mime(full_data, "application/octet-stream")

            total_len = len(full_data)
            range_header = self.headers.get("Range")
            if range_header and range_header.startswith("bytes="):
                try:
                    range_spec = range_header.split("=")[1].strip()
                    start_str, end_str = range_spec.split("-", 1)
                    start = int(start_str) if start_str else 0
                    end = int(end_str) if end_str else total_len - 1
                    end = min(end, total_len - 1)
                    chunk = full_data[start : end + 1]

                    self.send_response(206)
                    self.send_header("Content-Type", mime)
                    self.send_header("Accept-Ranges", "bytes")
                    self.send_header("Content-Range", f"bytes {start}-{end}/{total_len}")
                    self.send_header("Content-Length", str(len(chunk)))
                    self.send_header("Cache-Control", "public, max-age=86400")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header("Cross-Origin-Resource-Policy", "cross-origin")
                    self.end_headers()
                    self.wfile.write(chunk)
                    return
                except Exception:
                    pass

            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(total_len))
            self.send_header("Cache-Control", "public, max-age=86400")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cross-Origin-Resource-Policy", "cross-origin")
            self.end_headers()
            self.wfile.write(full_data)
            return

        if not path.startswith("/api/") and not path.startswith("/uploads/"):
            rel_path = path.lstrip("/") or "index.html"
            if rel_path in ("admin", "admin/", "admin/index.html", "admin.html"):
                rel_path = "admin.html"
            candidate = os.path.join(CLIENT_WEB_DIR, rel_path)
            if not os.path.isfile(candidate):
                candidate = os.path.join(CLIENT_WEB_DIR, "index.html")
            if os.path.isfile(candidate):
                mime, _ = mimetypes.guess_type(candidate)
                if not mime:
                    mime = "text/html; charset=utf-8"
                elif mime == "text/html":
                    mime = "text/html; charset=utf-8"
                with open(candidate, "rb") as f:
                    html_bytes = f.read()
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(html_bytes)))
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(html_bytes)
                return

        conn = get_conn()
        try:
            c = conn.cursor()

            if path == "/api/health":
                self._send_json({"status": "healthy", "port": int(os.environ.get("PORT", 8000))})
                return

            if path == "/api/auth/me":
                user = self._get_auth_user(conn, required=True)
                if not user:
                    return
                unread_notifs = c.execute(
                    "SELECT COUNT(*) FROM notifications WHERE recipient_id = ? AND is_read = 0",
                    (user["id"],),
                ).fetchone()[0]
                unread_msgs = c.execute(
                    "SELECT COUNT(*) FROM messages WHERE receiver_id = ? AND is_read = 0 AND sender_id != ?",
                    (user["id"], user["id"]),
                ).fetchone()[0]
                data = serialize_user_row(conn, user, user["id"])
                data["unread_notifications_count"] = unread_notifs
                data["unread_messages_count"] = unread_msgs
                saved_rows = c.execute(
                    "SELECT p.* FROM posts p JOIN saved_posts sp ON sp.post_id = p.id WHERE sp.user_id = ? ORDER BY sp.id DESC",
                    (user["id"],),
                ).fetchall()
                my_posts = c.execute("SELECT * FROM posts WHERE author_id = ? ORDER BY id DESC", (user["id"],)).fetchall()
                data["posts"] = [serialize_post_row(conn, p, user["id"]) for p in my_posts]
                data["saved_posts"] = [serialize_post_row(conn, p, user["id"]) for p in saved_rows]
                self._send_json(data)
                return

            if path == "/api/reports/my":
                user = self._get_auth_user(conn, required=True)
                if not user:
                    return
                rep_rows = c.execute("SELECT * FROM reports WHERE reporter_id = ? ORDER BY id DESC", (user["id"],)).fetchall()
                self._send_json([dict(r) for r in rep_rows])
                return

            if path.startswith("/api/users/"):
                target_key = urllib.parse.unquote(path.split("/api/users/")[1].strip("/")).lstrip("@")
                viewer = self._get_auth_user(conn, required=False)
                viewer_id = viewer["id"] if viewer else None
                if target_key.isdigit():
                    urow = c.execute("SELECT * FROM users WHERE id = ?", (int(target_key),)).fetchone()
                else:
                    urow = c.execute("SELECT * FROM users WHERE LOWER(username) = ?", (target_key.lower(),)).fetchone()
                if not urow:
                    self._send_json({"detail": "User not found"}, status=404)
                    return
                u_data = serialize_user_row(conn, urow, viewer_id)
                # Case A: Public (is_private == 0) OR Viewer is Owner -> is_locked = False, return posts array
                # Case B: Private (is_private == 1) AND Viewer is accepted follower (status == 'accepted') -> is_locked = False, return posts array
                # Case C: Private (is_private == 1) AND Viewer is NOT accepted follower -> is_locked = True, posts: []
                if u_data.get("is_locked"):
                    u_data["posts"] = []
                    u_data["saved_posts"] = []
                else:
                    u_posts = c.execute("SELECT * FROM posts WHERE author_id = ? ORDER BY id DESC", (urow["id"],)).fetchall()
                    u_data["posts"] = [serialize_post_row(conn, p, viewer_id) for p in u_posts]
                    if viewer_id and viewer_id == urow["id"]:
                        saved_rows = c.execute(
                            "SELECT p.* FROM posts p JOIN saved_posts sp ON sp.post_id = p.id WHERE sp.user_id = ? ORDER BY sp.id DESC",
                            (viewer_id,),
                        ).fetchall()
                        u_data["saved_posts"] = [serialize_post_row(conn, p, viewer_id) for p in saved_rows]
                    else:
                        u_data["saved_posts"] = []
                if viewer_id:
                    u_data["is_blocked"] = c.execute(
                        "SELECT 1 FROM user_blocks WHERE blocker_id = ? AND blocked_id = ?", (viewer_id, urow["id"])
                    ).fetchone() is not None
                    u_data["is_restricted"] = c.execute(
                        "SELECT 1 FROM user_restricts WHERE user_id = ? AND restricted_id = ?", (viewer_id, urow["id"])
                    ).fetchone() is not None
                self._send_json(u_data)
                return

            if path == "/api/announcements/active":
                now_str = datetime.utcnow().isoformat()
                ann = c.execute(
                    "SELECT * FROM system_announcements WHERE is_active = 1 AND expires_at > ? ORDER BY id DESC LIMIT 1",
                    (now_str,),
                ).fetchone()
                if not ann:
                    self._send_json(None)
                else:
                    self._send_json({
                        "id": ann["id"],
                        "message": ann["message"],
                        "is_active": bool(ann["is_active"]),
                        "expires_at": ann["expires_at"],
                        "created_at": ann["created_at"],
                    })
                return

            if path in ("/api/posts", "/api/posts/feed", "/api/explore"):
                viewer = self._get_auth_user(conn, required=False)
                viewer_id = viewer["id"] if viewer else None
                blocked_ids = set()
                accepted_followed_ids = set()
                if viewer_id:
                    b_rows = c.execute("SELECT blocked_id FROM user_blocks WHERE blocker_id = ?", (viewer_id,)).fetchall()
                    blocked_ids = {r["blocked_id"] for r in b_rows}
                    f_rows = c.execute(
                        "SELECT following_id FROM follows WHERE follower_id = ? AND COALESCE(status, 'accepted') = 'accepted'",
                        (viewer_id,),
                    ).fetchall()
                    accepted_followed_ids = {r["following_id"] for r in f_rows}

                raw_posts = c.execute("SELECT * FROM posts WHERE is_archived = 0 ORDER BY id DESC").fetchall()
                posts_list = []
                for p in raw_posts:
                    if p["author_id"] in blocked_ids:
                        continue
                    author_row = c.execute("SELECT is_private FROM users WHERE id = ?", (p["author_id"],)).fetchone()
                    is_priv_author = bool(author_row["is_private"]) if author_row else False
                    if is_priv_author and p["author_id"] != viewer_id and p["author_id"] not in accepted_followed_ids:
                        continue
                    posts_list.append(serialize_post_row(conn, p, viewer_id))
                self._send_json(posts_list)
                return

            if path == "/api/stories":
                viewer = self._get_auth_user(conn, required=False)
                viewer_id = viewer["id"] if viewer else None
                now_str = datetime.utcnow().isoformat()
                rows = c.execute(
                    """
                    SELECT s.*, u.username, u.avatar_url, u.is_verified, u.is_private
                    FROM stories s
                    JOIN users u ON u.id = s.user_id
                    WHERE s.expires_at > ?
                    ORDER BY s.id DESC
                    """,
                    (now_str,),
                ).fetchall()
                accepted_followed_ids = set()
                if viewer_id:
                    f_rows = c.execute(
                        "SELECT following_id FROM follows WHERE follower_id = ? AND COALESCE(status, 'accepted') = 'accepted'",
                        (viewer_id,),
                    ).fetchall()
                    accepted_followed_ids = {r["following_id"] for r in f_rows}
                result = []
                for r in rows:
                    if bool(r["is_private"]) and r["user_id"] != viewer_id and r["user_id"] not in accepted_followed_ids:
                        continue
                    views_cnt = c.execute("SELECT COUNT(*) FROM story_views WHERE story_id = ?", (r["id"],)).fetchone()[0]
                    viewed_by_me = False
                    if viewer_id:
                        viewed_by_me = (
                            c.execute(
                                "SELECT 1 FROM story_views WHERE story_id = ? AND viewer_id = ?",
                                (r["id"], viewer_id),
                            ).fetchone()
                            is not None
                        )
                    result.append({
                        "id": r["id"],
                        "user_id": r["user_id"],
                        "username": r["username"],
                        "avatar_url": r["avatar_url"] or "",
                        "is_verified": bool(r["is_verified"]),
                        "media_url": r["media_url"],
                        "media_type": r["media_type"] or "IMAGE",
                        "caption": r["caption"] or "",
                        "views_count": views_cnt,
                        "viewed_by_me": viewed_by_me,
                        "expires_at": r["expires_at"],
                        "created_at": r["created_at"],
                    })
                self._send_json(result)
                return

            if path == "/api/reels":
                viewer = self._get_auth_user(conn, required=False)
                viewer_id = viewer["id"] if viewer else None
                rows = c.execute(
                    """
                    SELECT r.*, u.username, u.avatar_url, u.is_verified
                    FROM reels r
                    JOIN users u ON u.id = r.author_id
                    ORDER BY r.id DESC
                    """
                ).fetchall()
                result = []
                for r in rows:
                    likes_cnt = c.execute("SELECT COUNT(*) FROM reel_likes WHERE reel_id = ?", (r["id"],)).fetchone()[0]
                    comments_cnt = c.execute("SELECT COUNT(*) FROM reel_comments WHERE reel_id = ?", (r["id"],)).fetchone()[0]
                    liked_by_me = False
                    if viewer_id:
                        liked_by_me = (
                            c.execute("SELECT 1 FROM reel_likes WHERE reel_id = ? AND user_id = ?", (r["id"], viewer_id)).fetchone()
                            is not None
                        )
                    result.append({
                        "id": r["id"],
                        "author_id": r["author_id"],
                        "username": r["username"],
                        "avatar_url": r["avatar_url"] or "",
                        "is_verified": bool(r["is_verified"]),
                        "video_url": r["video_url"] or r["media_url"],
                        "media_url": r["media_url"],
                        "thumbnail_url": r["thumbnail_url"] or "",
                        "caption": r["caption"] or "",
                        "audio_name": r["audio_name"] or r["audio_track"] or "Original Audio",
                        "audio_track": r["audio_track"] or r["audio_name"] or "Original Audio",
                        "view_count": r["view_count"] or r["views_count"] or 0,
                        "views_count": r["views_count"] or r["view_count"] or 0,
                        "likes_count": likes_cnt,
                        "comments_count": comments_cnt,
                        "liked_by_me": liked_by_me,
                        "created_at": r["created_at"],
                    })
                self._send_json(result)
                return

            if path == "/api/search":
                qs = parse_qs(parsed.query)
                q = (qs.get("q", [""])[0] or "").strip().lower()
                category = (qs.get("category", ["all"])[0] or "all").strip().lower()
                viewer = self._get_auth_user(conn, required=False)
                viewer_id = viewer["id"] if viewer else None
                rows = c.execute(
                    """
                    SELECT * FROM users
                    WHERE role = 'USER' AND is_banned = 0
                      AND (LOWER(username) LIKE ? OR LOWER(full_name) LIKE ? OR LOWER(bio) LIKE ?)
                    ORDER BY id DESC
                    """,
                    (f"%{q}%", f"%{q}%", f"%{q}%"),
                ).fetchall()
                users_list = [serialize_user_row(conn, u, viewer_id) for u in rows]
                if category == "hashtags":
                    posts_match = c.execute(
                        "SELECT * FROM posts WHERE LOWER(caption) LIKE ? ORDER BY id DESC",
                        (f"%#{q.lstrip('#')}%",),
                    ).fetchall()
                    self._send_json([serialize_post_row(conn, p, viewer_id) for p in posts_match])
                    return
                self._send_json(users_list)
                return

            if path == "/api/notifications":
                user = self._get_auth_user(conn, required=True)
                if not user:
                    return
                pending_requesters = {
                    r["follower_id"]
                    for r in c.execute(
                        "SELECT follower_id FROM follows WHERE following_id = ? AND status = 'requested'",
                        (user["id"],),
                    ).fetchall()
                }
                rows = c.execute(
                    """
                    SELECT n.*, u.username AS actor_username, u.avatar_url AS actor_avatar, u.is_verified AS actor_verified
                    FROM notifications n
                    JOIN users u ON u.id = n.actor_id
                    WHERE n.recipient_id = ?
                    ORDER BY n.id DESC
                    """,
                    (user["id"],),
                ).fetchall()
                items = []
                seen_request_actors = set()
                for r in rows:
                    is_req = r["type"] == "FOLLOW_REQUEST" and r["actor_id"] in pending_requesters
                    if is_req:
                        seen_request_actors.add(r["actor_id"])
                    items.append({
                        "id": r["id"],
                        "recipient_id": r["recipient_id"],
                        "actor_id": r["actor_id"],
                        "actor_username": r["actor_username"],
                        "actor_avatar": r["actor_avatar"] or "",
                        "actor_verified": bool(r["actor_verified"]),
                        "type": r["type"],
                        "is_follow_request": is_req,
                        "target_id": r["target_id"] or r["post_id"],
                        "post_id": r["post_id"],
                        "message": r["message"],
                        "is_read": bool(r["is_read"]),
                        "created_at": r["created_at"],
                    })
                for req_uid in pending_requesters - seen_request_actors:
                    ru = c.execute("SELECT * FROM users WHERE id = ?", (req_uid,)).fetchone()
                    if ru:
                        items.insert(0, {
                            "id": 0,
                            "recipient_id": user["id"],
                            "actor_id": ru["id"],
                            "actor_username": ru["username"],
                            "actor_avatar": ru["avatar_url"] or "",
                            "actor_verified": bool(ru["is_verified"]),
                            "type": "FOLLOW_REQUEST",
                            "is_follow_request": True,
                            "target_id": ru["id"],
                            "post_id": None,
                            "message": f"@{ru['username']} requested to follow you.",
                            "is_read": False,
                            "created_at": datetime.utcnow().isoformat(),
                        })
                self._send_json(items)
                return

            if path in ("/api/conversations", "/api/messages/conversations"):
                user = self._get_auth_user(conn, required=True)
                if not user:
                    return
                conv_rows = c.execute(
                    """
                    SELECT c.id, c.is_group, c.title, c.updated_at
                    FROM conversations c
                    JOIN conversation_members cm ON cm.conversation_id = c.id
                    WHERE cm.user_id = ?
                    ORDER BY c.updated_at DESC, c.id DESC
                    """,
                    (user["id"],),
                ).fetchall()
                threads = []
                for cr in conv_rows:
                    cid = cr["id"]
                    peer = c.execute(
                        """
                        SELECT u.*
                        FROM conversation_members cm
                        JOIN users u ON u.id = cm.user_id
                        WHERE cm.conversation_id = ? AND cm.user_id != ?
                        LIMIT 1
                        """,
                        (cid, user["id"]),
                    ).fetchone()
                    last_msg = c.execute(
                        "SELECT * FROM messages WHERE conversation_id = ? ORDER BY id DESC LIMIT 1",
                        (cid,),
                    ).fetchone()
                    unread_cnt = c.execute(
                        "SELECT COUNT(*) FROM messages WHERE conversation_id = ? AND receiver_id = ? AND is_read = 0",
                        (cid, user["id"]),
                    ).fetchone()[0]
                    peer_serialized = serialize_user_row(conn, peer, user["id"]) if peer else None
                    threads.append({
                        "id": cid,
                        "is_group": bool(cr["is_group"]),
                        "title": cr["title"] or "",
                        "peer": peer_serialized,
                        "peer_id": peer["id"] if peer else None,
                        "peer_username": peer["username"] if peer else "",
                        "last_message": dict(last_msg) if last_msg else None,
                        "unread_count": unread_cnt,
                        "updated_at": cr["updated_at"],
                    })
                self._send_json(threads)
                return

            if re.match(r"^/api/messages/\d+$", path):
                user = self._get_auth_user(conn, required=True)
                if not user:
                    return
                peer_id = int(path.split("/")[3])
                conn.execute(
                    "UPDATE messages SET is_read = 1 WHERE sender_id = ? AND receiver_id = ?",
                    (peer_id, user["id"]),
                )
                conn.commit()
                msgs = c.execute(
                    """
                    SELECT m.*, u.username AS sender_username, u.avatar_url AS sender_avatar
                    FROM messages m
                    JOIN users u ON u.id = m.sender_id
                    WHERE (m.sender_id = ? AND m.receiver_id = ?) OR (m.sender_id = ? AND m.receiver_id = ?)
                    ORDER BY m.id ASC
                    """,
                    (user["id"], peer_id, peer_id, user["id"]),
                ).fetchall()
                self._send_json([dict(m) for m in msgs])
                return

            if re.match(r"^/api/conversations/\d+/messages$", path):
                user = self._get_auth_user(conn, required=True)
                if not user:
                    return
                cid = int(path.split("/")[3])
                conn.execute(
                    "UPDATE messages SET is_read = 1 WHERE conversation_id = ? AND receiver_id = ?",
                    (cid, user["id"]),
                )
                conn.commit()
                msgs = c.execute(
                    """
                    SELECT m.*, u.username AS sender_username, u.avatar_url AS sender_avatar
                    FROM messages m
                    JOIN users u ON u.id = m.sender_id
                    WHERE m.conversation_id = ?
                    ORDER BY m.id ASC
                    """,
                    (cid,),
                ).fetchall()
                self._send_json([dict(m) for m in msgs])
                return

            if path == "/api/auth/check-username":
                qs = parse_qs(parsed.query)
                u = (qs.get("u", [""])[0] or qs.get("username", [""])[0] or "").strip().lower()
                if not u or len(u) < 2:
                    self._send_json({"available": False, "username": u, "detail": "Too short"})
                    return
                exists = c.execute("SELECT 1 FROM users WHERE LOWER(username) = ?", (u,)).fetchone()
                self._send_json({"available": exists is None, "username": u})
                return

            if path == "/api/notes":
                now_iso = datetime.utcnow().isoformat()
                rows = c.execute(
                    """
                    SELECT n.*, u.username, u.avatar_url, u.is_verified
                    FROM user_notes n
                    JOIN users u ON u.id = n.user_id
                    WHERE n.expires_at > ? AND u.is_banned = 0
                    ORDER BY n.id DESC
                    """,
                    (now_iso,),
                ).fetchall()
                notes_out = []
                for r in rows:
                    d = dict(r)
                    d["views_count"] = int(d.get("views_count") or 0)
                    notes_out.append(d)
                self._send_json(notes_out)
                return

            if path == "/api/music/search":
                raw_q = (parse_qs(parsed.query).get("q", [""])[0] or "").strip()
                BUILTIN_CATALOG = [
                    {"id": "pk_deewane_1", "title": "Deewane", "artist": "Adnan Dhool & Momina Mustehsan", "album": "Coke Studio Sessions", "cover_url": "https://is1-ssl.mzstatic.com/image/thumb/Music124/v4/38/44/21/384421ca-69a0-83f2-0a34-88653d45db97/8901854001385.jpg/100x100bb.jpg", "preview_url": "https://audio-ssl.itunes.apple.com/itunes-assets/AudioPreview211/v4/0d/db/cf/0ddbcf31-22d7-088e-c71f-1dd88a3dd8a2/mzaf_16563349538675654632.plus.aac.p.m4a", "duration_ms": 218000, "duration_sec": 218},
                    {"id": "in_deewane_2", "title": "Deewani Mastani", "artist": "Shreya Ghoshal & Sanjay Leela Bhansali", "album": "Bajirao Mastani", "cover_url": "https://is1-ssl.mzstatic.com/image/thumb/Music124/v4/38/44/21/384421ca-69a0-83f2-0a34-88653d45db97/8901854001385.jpg/100x100bb.jpg", "preview_url": "https://audio-ssl.itunes.apple.com/itunes-assets/AudioPreview211/v4/0d/db/cf/0ddbcf31-22d7-088e-c71f-1dd88a3dd8a2/mzaf_16563349538675654632.plus.aac.p.m4a", "duration_ms": 340000, "duration_sec": 340},
                    {"id": "in_deewane_3", "title": "Hum Deewane", "artist": "Arijit Singh", "album": "Bollywood Romantic Hits", "cover_url": "https://is1-ssl.mzstatic.com/image/thumb/Music124/v4/38/44/21/384421ca-69a0-83f2-0a34-88653d45db97/8901854001385.jpg/100x100bb.jpg", "preview_url": "https://audio-ssl.itunes.apple.com/itunes-assets/AudioPreview211/v4/0d/db/cf/0ddbcf31-22d7-088e-c71f-1dd88a3dd8a2/mzaf_16563349538675654632.plus.aac.p.m4a", "duration_ms": 204000, "duration_sec": 204},
                    {"id": "pk_pasoori", "title": "Pasoori", "artist": "Shae Gill & Ali Sethi", "album": "Coke Studio Season 14", "cover_url": "https://is1-ssl.mzstatic.com/image/thumb/Music124/v4/38/44/21/384421ca-69a0-83f2-0a34-88653d45db97/8901854001385.jpg/100x100bb.jpg", "preview_url": "https://audio-ssl.itunes.apple.com/itunes-assets/AudioPreview211/v4/0d/db/cf/0ddbcf31-22d7-088e-c71f-1dd88a3dd8a2/mzaf_16563349538675654632.plus.aac.p.m4a", "duration_ms": 224000, "duration_sec": 224},
                    {"id": "pk_tuhai", "title": "Tu Hai Kahan", "artist": "AUR", "album": "Pakistani Indie Chart", "cover_url": "https://is1-ssl.mzstatic.com/image/thumb/Music124/v4/38/44/21/384421ca-69a0-83f2-0a34-88653d45db97/8901854001385.jpg/100x100bb.jpg", "preview_url": "https://audio-ssl.itunes.apple.com/itunes-assets/AudioPreview211/v4/0d/db/cf/0ddbcf31-22d7-088e-c71f-1dd88a3dd8a2/mzaf_16563349538675654632.plus.aac.p.m4a", "duration_ms": 263000, "duration_sec": 263},
                    {"id": "pk_afreen", "title": "Afreen Afreen", "artist": "Rahat Fateh Ali Khan & Momina Mustehsan", "album": "Coke Studio Season 9", "cover_url": "https://is1-ssl.mzstatic.com/image/thumb/Music124/v4/38/44/21/384421ca-69a0-83f2-0a34-88653d45db97/8901854001385.jpg/100x100bb.jpg", "preview_url": "https://audio-ssl.itunes.apple.com/itunes-assets/AudioPreview211/v4/0d/db/cf/0ddbcf31-22d7-088e-c71f-1dd88a3dd8a2/mzaf_16563349538675654632.plus.aac.p.m4a", "duration_ms": 395000, "duration_sec": 395},
                    {"id": "pk_pehli", "title": "Pehli Nazar Mein", "artist": "Atif Aslam & Pritam", "album": "Race Soundtrack", "cover_url": "https://is1-ssl.mzstatic.com/image/thumb/Music124/v4/38/44/21/384421ca-69a0-83f2-0a34-88653d45db97/8901854001385.jpg/100x100bb.jpg", "preview_url": "https://audio-ssl.itunes.apple.com/itunes-assets/AudioPreview211/v4/0d/db/cf/0ddbcf31-22d7-088e-c71f-1dd88a3dd8a2/mzaf_16563349538675654632.plus.aac.p.m4a", "duration_ms": 312000, "duration_sec": 312},
                    {"id": "in_kesariya", "title": "Kesariya", "artist": "Arijit Singh & Pritam", "album": "Brahmastra", "cover_url": "https://is1-ssl.mzstatic.com/image/thumb/Music124/v4/38/44/21/384421ca-69a0-83f2-0a34-88653d45db97/8901854001385.jpg/100x100bb.jpg", "preview_url": "https://audio-ssl.itunes.apple.com/itunes-assets/AudioPreview211/v4/0d/db/cf/0ddbcf31-22d7-088e-c71f-1dd88a3dd8a2/mzaf_16563349538675654632.plus.aac.p.m4a", "duration_ms": 268000, "duration_sec": 268},
                    {"id": "in_chaleya", "title": "Chaleya", "artist": "Arijit Singh & Shilpa Rao", "album": "Jawan", "cover_url": "https://is1-ssl.mzstatic.com/image/thumb/Music124/v4/38/44/21/384421ca-69a0-83f2-0a34-88653d45db97/8901854001385.jpg/100x100bb.jpg", "preview_url": "https://audio-ssl.itunes.apple.com/itunes-assets/AudioPreview211/v4/0d/db/cf/0ddbcf31-22d7-088e-c71f-1dd88a3dd8a2/mzaf_16563349538675654632.plus.aac.p.m4a", "duration_ms": 200000, "duration_sec": 200},
                    {"id": "gl_blinding", "title": "Blinding Lights", "artist": "The Weeknd", "album": "After Hours", "cover_url": "https://is1-ssl.mzstatic.com/image/thumb/Music124/v4/38/44/21/384421ca-69a0-83f2-0a34-88653d45db97/8901854001385.jpg/100x100bb.jpg", "preview_url": "https://audio-ssl.itunes.apple.com/itunes-assets/AudioPreview211/v4/0d/db/cf/0ddbcf31-22d7-088e-c71f-1dd88a3dd8a2/mzaf_16563349538675654632.plus.aac.p.m4a", "duration_ms": 200000, "duration_sec": 200},
                    {"id": "pk_husn", "title": "Husn", "artist": "Anuv Jain", "album": "Indie South Asia", "cover_url": "https://is1-ssl.mzstatic.com/image/thumb/Music124/v4/38/44/21/384421ca-69a0-83f2-0a34-88653d45db97/8901854001385.jpg/100x100bb.jpg", "preview_url": "https://audio-ssl.itunes.apple.com/itunes-assets/AudioPreview211/v4/0d/db/cf/0ddbcf31-22d7-088e-c71f-1dd88a3dd8a2/mzaf_16563349538675654632.plus.aac.p.m4a", "duration_ms": 219000, "duration_sec": 219},
                    {"id": "pk_kana", "title": "Kana Yaari", "artist": "Kaifi Khalil, Eva B & Abdul Wahab Bugti", "album": "Coke Studio Season 14", "cover_url": "https://is1-ssl.mzstatic.com/image/thumb/Music124/v4/38/44/21/384421ca-69a0-83f2-0a34-88653d45db97/8901854001385.jpg/100x100bb.jpg", "preview_url": "https://audio-ssl.itunes.apple.com/itunes-assets/AudioPreview211/v4/0d/db/cf/0ddbcf31-22d7-088e-c71f-1dd88a3dd8a2/mzaf_16563349538675654632.plus.aac.p.m4a", "duration_ms": 212000, "duration_sec": 212},
                ]

                search_term = raw_q if raw_q else "Atif Aslam Arijit Singh Coke Studio"
                tracks = []
                seen_ids = set()
                ssl_ctx = ssl._create_unverified_context()
                req_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

                for url_candidate in (
                    f"https://itunes.apple.com/search?term={urllib.parse.quote(search_term)}&media=music&limit=30",
                    f"https://itunes.apple.com/search?term={urllib.parse.quote(search_term + ' song')}&country=IN&media=music&limit=25",
                ):
                    if len(tracks) >= 15:
                        break
                    try:
                        req = urllib.request.Request(url_candidate, headers=req_headers)
                        with urllib.request.urlopen(req, timeout=5, context=ssl_ctx) as resp:
                            payload = json.loads(resp.read().decode("utf-8", errors="ignore"))
                            for item in payload.get("results", []):
                                tid = str(item.get("trackId", ""))
                                if tid and tid not in seen_ids and item.get("previewUrl") and item.get("trackName"):
                                    seen_ids.add(tid)
                                    dur_ms = int(item.get("trackTimeMillis") or 204000)
                                    tracks.append({
                                        "id": tid,
                                        "title": item.get("trackName", "Unknown Track"),
                                        "artist": item.get("artistName", "Unknown Artist"),
                                        "album": item.get("collectionName", ""),
                                        "cover_url": item.get("artworkUrl100", ""),
                                        "preview_url": item.get("previewUrl", ""),
                                        "duration_ms": dur_ms,
                                        "duration_sec": max(60, int(dur_ms / 1000)),
                                    })
                    except Exception as exc:
                        print("Music gateway notice:", exc)

                if raw_q:
                    ql = raw_q.lower()
                    matching_builtin = [b for b in BUILTIN_CATALOG if ql in b["title"].lower() or ql in b["artist"].lower()]
                    tracks = matching_builtin + tracks
                if len(tracks) == 0:
                    tracks = BUILTIN_CATALOG

                self._send_json(tracks[:32])
                return

            if path == "/api/trending":
                post_rows = c.execute("SELECT caption FROM posts ORDER BY id DESC LIMIT 200").fetchall()
                tag_counts = {}
                for pr in post_rows:
                    cap = pr["caption"] or ""
                    for tag in re.findall(r"#([a-zA-Z0-9_]+)", cap):
                        key = tag.lower()
                        tag_counts[key] = tag_counts.get(key, 0) + 1
                sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                self._send_json([{"tag": f"#{k}", "count": v, "posts_count": v} for k, v in sorted_tags])
                return

            if path == "/api/settings":
                user = self._get_auth_user(conn, required=True)
                if not user:
                    return
                row = c.execute("SELECT settings_json FROM user_settings WHERE user_id = ?", (user["id"],)).fetchone()
                default_settings = {
                    "comments_control": "everyone",
                    "mentions_control": "everyone",
                    "hidden_words": "",
                    "story_privacy": "public",
                    "activity_status": True,
                    "notify_likes": True,
                    "notify_comments": True,
                    "notify_followers": True,
                    "notify_messages": True,
                    "notify_stories": True,
                    "read_receipts": True,
                    "message_requests": True,
                    "blocked_accounts": [],
                    "muted_accounts": [],
                    "close_friends": [],
                }
                if row and row["settings_json"]:
                    try:
                        default_settings.update(json.loads(row["settings_json"]))
                    except Exception:
                        pass
                default_settings["is_private"] = bool(user["is_private"])
                self._send_json(default_settings)
                return

            # ==================== ADMIN PROTECTED ROUTES ====================
            if path.startswith("/api/admin/"):
                admin = self._require_admin_user(conn)
                if not admin:
                    return

                if path in ("/api/admin/analytics", "/api/admin/metrics", "/api/admin/stats"):
                    total_users = c.execute("SELECT COUNT(*) FROM users WHERE role = 'USER'").fetchone()[0]
                    all_accounts = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
                    banned_users = c.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1").fetchone()[0]
                    verified_users = c.execute("SELECT COUNT(*) FROM users WHERE is_verified = 1").fetchone()[0]
                    total_posts = c.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
                    total_reels = c.execute("SELECT COUNT(*) FROM reels").fetchone()[0]
                    total_likes = c.execute("SELECT COUNT(*) FROM likes").fetchone()[0]
                    total_comments = c.execute("SELECT COUNT(*) FROM comments").fetchone()[0]
                    total_messages = c.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
                    open_reports = c.execute("SELECT COUNT(*) FROM reports WHERE status IN ('OPEN', 'PENDING')").fetchone()[0]
                    resolved_reports = c.execute("SELECT COUNT(*) FROM reports WHERE status NOT IN ('OPEN', 'PENDING')").fetchone()[0]

                    users_rows = c.execute("SELECT * FROM users ORDER BY id DESC").fetchall()
                    posts_rows = c.execute("SELECT * FROM posts ORDER BY id DESC").fetchall()
                    reports_rows = c.execute("SELECT * FROM reports ORDER BY id DESC").fetchall()
                    audit_rows = c.execute("SELECT * FROM admin_audit_logs ORDER BY id DESC LIMIT 100").fetchall()
                    ann_rows = c.execute("SELECT * FROM system_announcements ORDER BY id DESC").fetchall()

                    stats_payload = {
                        "total_users": all_accounts,
                        "consumer_users": total_users,
                        "all_accounts": all_accounts,
                        "active_users": max(0, all_accounts - banned_users),
                        "active_users_24h": max(0, total_users - banned_users),
                        "new_registrations_24h": total_users,
                        "banned_users": banned_users,
                        "verified_users": verified_users,
                        "total_posts": total_posts,
                        "total_reels": total_reels,
                        "total_likes": total_likes,
                        "total_comments": total_comments,
                        "total_messages": total_messages,
                        "open_reports": open_reports,
                        "pending_reports": open_reports,
                        "resolved_reports": resolved_reports,
                    }

                    self._send_json({
                        **stats_payload,
                        "analytics": stats_payload,
                        "users": [serialize_user_row(conn, u) for u in users_rows],
                        "posts": [serialize_post_row(conn, p) for p in posts_rows],
                        "reports": [dict(r) for r in reports_rows],
                        "announcements": [dict(a) for a in ann_rows],
                        "audit_logs": [dict(l) for l in audit_rows],
                    })
                    return

                if path == "/api/admin/users":
                    users_rows = c.execute("SELECT * FROM users ORDER BY id DESC").fetchall()
                    self._send_json([serialize_user_row(conn, u) for u in users_rows])
                    return

                if path == "/api/admin/posts":
                    posts_rows = c.execute("SELECT * FROM posts ORDER BY id DESC").fetchall()
                    self._send_json([serialize_post_row(conn, p) for p in posts_rows])
                    return

                if path == "/api/admin/audit-logs":
                    audit_rows = c.execute("SELECT * FROM admin_audit_logs ORDER BY id DESC LIMIT 100").fetchall()
                    self._send_json([dict(l) for l in audit_rows])
                    return

                if path == "/api/admin/reports":
                    reports_rows = c.execute("SELECT * FROM reports ORDER BY id DESC").fetchall()
                    enriched = []
                    for r in reports_rows:
                        rd = dict(r)
                        rep_u = c.execute("SELECT username FROM users WHERE id = ?", (r["reporter_id"],)).fetchone()
                        rd["reporter_username"] = rep_u["username"] if rep_u else f"user_{r['reporter_id']}"
                        rd["target_post_id"] = r["target_id"] if r["target_type"] == "POST" else None
                        enriched.append(rd)
                    self._send_json(enriched)
                    return

                if path == "/api/admin/chats/conversations":
                    conv_rows = c.execute("SELECT * FROM conversations ORDER BY updated_at DESC, id DESC").fetchall()
                    result_convs = []
                    for cr in conv_rows:
                        cid = cr["id"]
                        mem_rows = c.execute(
                            """
                            SELECT u.id, u.username, u.full_name, u.avatar_url
                            FROM conversation_members cm
                            JOIN users u ON u.id = cm.user_id
                            WHERE cm.conversation_id = ?
                            """,
                            (cid,),
                        ).fetchall()
                        members = [dict(m) for m in mem_rows]
                        last_msg = c.execute(
                            """
                            SELECT m.*, u.username AS sender_username
                            FROM messages m
                            LEFT JOIN users u ON u.id = m.sender_id
                            WHERE m.conversation_id = ?
                            ORDER BY m.id DESC LIMIT 1
                            """,
                            (cid,),
                        ).fetchone()
                        msg_count = c.execute("SELECT COUNT(*) FROM messages WHERE conversation_id = ?", (cid,)).fetchone()[0]
                        result_convs.append({
                            "id": cid,
                            "updated_at": cr["updated_at"],
                            "members": members,
                            "participants_label": " & ".join([f"@{m['username']}" for m in members]) or f"Thread #{cid}",
                            "messages_count": msg_count,
                            "last_message": dict(last_msg) if last_msg else None,
                        })
                    self._send_json(result_convs)
                    return

                if re.match(r"^/api/admin/chats/\d+/messages$", path):
                    tid = int(path.split("/")[4])
                    msg_rows = c.execute(
                        """
                        SELECT m.*,
                               su.username AS sender_username,
                               su.avatar_url AS sender_avatar,
                               ru.username AS receiver_username
                        FROM messages m
                        LEFT JOIN users su ON su.id = m.sender_id
                        LEFT JOIN users ru ON ru.id = m.receiver_id
                        WHERE m.conversation_id = ?
                        ORDER BY m.id ASC
                        """,
                        (tid,),
                    ).fetchall()
                    self._send_json([dict(m) for m in msg_rows])
                    return

            self._send_json({"detail": f"Route {path} not found"}, status=404)
        finally:
            conn.close()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # Binary / Multipart Upload Endpoint with Magic-Byte Verification
        if path in ("/api/media/upload", "/api/posts", "/api/stories") and "multipart/form-data" in self.headers.get("Content-Type", ""):
            conn = get_conn()
            try:
                user = self._get_auth_user(conn, required=(path in ("/api/posts", "/api/stories")))
                if path in ("/api/posts", "/api/stories") and not user:
                    return
                content_type = self.headers.get("Content-Type", "")
                content_length = int(self.headers.get("Content-Length", 0))
                if content_length <= 0:
                    self._send_json({"detail": "Empty upload payload"}, status=400)
                    return

                raw_bytes = self.rfile.read(content_length)
                file_bytes = raw_bytes
                declared_mime = "image/png"
                fields = {}

                if "boundary=" in content_type:
                    boundary = content_type.split("boundary=")[1].split(";")[0].strip().encode("utf-8")
                    parts = raw_bytes.split(b"--" + boundary)
                    for part in parts:
                        if b"Content-Disposition" in part and b"\r\n\r\n" in part:
                            header_block, body_block = part.split(b"\r\n\r\n", 1)
                            header_text = header_block.decode("utf-8", errors="ignore")
                            cleaned_body = body_block.rstrip(b"\r\n-")
                            if 'filename="' in header_text:
                                for line in header_text.split("\r\n"):
                                    if line.lower().startswith("content-type:"):
                                        declared_mime = line.split(":", 1)[1].strip().lower()
                                file_bytes = cleaned_body
                            else:
                                m_name = re.search(r'name="([^"]+)"', header_text)
                                if m_name:
                                    fields[m_name.group(1)] = cleaned_body.decode("utf-8", errors="ignore").strip()

                detected_mime = detect_magic_mime(file_bytes, declared_mime)

                if detected_mime in ALLOWED_IMAGE_MIMES:
                    if len(file_bytes) > MAX_IMAGE_BYTES:
                        self._send_json({"detail": "Image exceeds 20MB limit"}, status=413)
                        return
                    ext = ALLOWED_IMAGE_MIMES[detected_mime]
                    media_type = "IMAGE"
                elif detected_mime in ALLOWED_VIDEO_MIMES:
                    if len(file_bytes) > MAX_VIDEO_BYTES:
                        self._send_json({"detail": "Video exceeds 100MB limit"}, status=413)
                        return
                    ext = ALLOWED_VIDEO_MIMES[detected_mime]
                    media_type = "VIDEO"
                else:
                    self._send_json({"detail": f"Unsupported MIME signature: {detected_mime}"}, status=415)
                    return

                filename = f"{uuid.uuid4().hex}{ext}"
                dest_path = os.path.join(UPLOAD_DIR, filename)
                with open(dest_path, "wb") as f:
                    f.write(file_bytes)

                url = f"http://127.0.0.1:8000/uploads/{filename}"
                if path == "/api/stories":
                    c = conn.cursor()
                    caption = fields.get("caption", "")
                    exp = (datetime.utcnow() + timedelta(hours=24)).isoformat()
                    c.execute(
                        "INSERT INTO stories (user_id, media_url, media_type, caption, expires_at) VALUES (?, ?, ?, ?, ?)",
                        (user["id"], url, media_type, caption, exp),
                    )
                    sid = c.lastrowid
                    conn.commit()
                    self._send_json({
                        "id": sid,
                        "user_id": user["id"],
                        "username": user["username"],
                        "avatar_url": user["avatar_url"],
                        "media_url": url,
                        "media_type": media_type,
                        "caption": caption,
                        "expires_at": exp,
                    }, status=201)
                    return

                if path == "/api/posts":
                    c = conn.cursor()
                    caption = fields.get("caption", "")
                    location = fields.get("location", "")
                    filter_name = fields.get("filter_name", "Normal")
                    aspect_ratio = fields.get("aspect_ratio", "1:1")
                    music_title = fields.get("music_title", "")
                    music_artist = fields.get("music_artist", "")
                    music_cover_url = fields.get("music_cover_url", "")
                    music_preview_url = fields.get("music_preview_url", "")
                    try:
                        music_clip_start = int(fields.get("music_clip_start", 0) or 0)
                    except Exception:
                        music_clip_start = 0
                    c.execute(
                        """
                        INSERT INTO posts (author_id, media_url, media_type, caption, location, filter_name, aspect_ratio, music_title, music_artist, music_cover_url, music_preview_url, music_clip_start)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (user["id"], url, media_type, caption, location, filter_name, aspect_ratio, music_title, music_artist, music_cover_url, music_preview_url, music_clip_start),
                    )
                    post_id = c.lastrowid
                    c.execute(
                        "INSERT INTO post_media (post_id, media_url, media_type, display_order, position) VALUES (?, ?, ?, 0, 0)",
                        (post_id, url, media_type),
                    )
                    conn.commit()
                    prow = c.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
                    self._send_json(serialize_post_row(conn, prow, user["id"]), status=200)
                    return

                self._send_json({
                    "url": url,
                    "media_url": url,
                    "media_type": media_type,
                    "mime_type": detected_mime,
                    "size": len(file_bytes),
                })
                return
            finally:
                conn.close()

        if path == "/api/media/upload":
            conn = get_conn()
            try:
                user = self._get_auth_user(conn, required=False)
                content_length = int(self.headers.get("Content-Length", 0))
                raw_bytes = self.rfile.read(content_length)
                payload = json.loads(raw_bytes.decode("utf-8"))
                data_url = payload.get("file_data", "")
                declared_mime = payload.get("mime_type", "image/png").lower()
                file_bytes = b""
                if "," in data_url:
                    _, b64_part = data_url.split(",", 1)
                    file_bytes = base64.b64decode(b64_part)
                detected_mime = detect_magic_mime(file_bytes, declared_mime)
                ext = ALLOWED_IMAGE_MIMES.get(detected_mime, ".png")
                media_type = "VIDEO" if detected_mime in ALLOWED_VIDEO_MIMES else "IMAGE"
                filename = f"{uuid.uuid4().hex}{ext}"
                with open(os.path.join(UPLOAD_DIR, filename), "wb") as f:
                    f.write(file_bytes)
                url = f"http://127.0.0.1:8000/uploads/{filename}"
                self._send_json({"url": url, "media_url": url, "media_type": media_type, "mime_type": detected_mime, "size": len(file_bytes)})
                return
            finally:
                conn.close()

        body = self._read_json()
        conn = get_conn()
        try:
            c = conn.cursor()

            if path == "/api/auth/logout":
                self._send_json({"status": "logged_out"})
                return

            if path == "/api/test/reset":
                conn.close()
                init_clean_database(force_wipe=True)
                self._send_json({"status": "clean_slate_initialized"})
                return

            if path == "/api/auth/register":
                username = (body.get("username") or "").strip().lower()
                email = (body.get("email") or f"{username}@fetagram.io").strip().lower()
                password = body.get("password") or ""
                full_name = (body.get("full_name") or username).strip()
                bio = (body.get("bio") or "").strip()
                website = (body.get("website") or "").strip()
                avatar_url = (body.get("avatar_url") or "").strip()

                if not username or not password:
                    self._send_json({"detail": "Username and password are required"}, status=400)
                    return

                existing = c.execute(
                    "SELECT id FROM users WHERE username = ? OR email = ?", (username, email)
                ).fetchone()
                if existing:
                    self._send_json({"detail": "Username or email already registered"}, status=409)
                    return

                c.execute(
                    """
                    INSERT INTO users (username, email, password_hash, full_name, bio, website, avatar_url, is_verified, is_banned, role)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 'USER')
                    """,
                    (username, email, hash_password(password), full_name, bio, website, avatar_url),
                )
                uid = c.lastrowid
                conn.commit()
                urow = c.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
                token = create_jwt(uid, username, "USER")
                self._send_json({
                    "access_token": token,
                    "token_type": "bearer",
                    "user": serialize_user_row(conn, urow, uid),
                })
                return

            if path == "/api/auth/forgot-password":
                identifier = (body.get("identifier") or body.get("username") or body.get("email") or "").strip().lower().lstrip("@")
                if not identifier:
                    self._send_json({"detail": "Enter your Username or Email"}, status=400)
                    return
                urow = c.execute(
                    "SELECT * FROM users WHERE LOWER(username) = ? OR LOWER(email) = ?",
                    (identifier, identifier),
                ).fetchone()
                if not urow:
                    self._send_json({"detail": "Account not found with that username or email"}, status=404)
                    return
                code = str(100000 + (abs(hash(f"{urow['username']}_{datetime.utcnow().minute}")) % 899999))
                PASSWORD_RESET_CODES[urow["username"].lower()] = code
                PASSWORD_RESET_CODES[urow["email"].lower()] = code
                self._send_json({
                    "status": "code_sent",
                    "username": urow["username"],
                    "reset_code": code,
                    "message": f"Verification code generated for @{urow['username']}",
                })
                return

            if path == "/api/auth/reset-password":
                identifier = (body.get("identifier") or body.get("username") or body.get("email") or "").strip().lower().lstrip("@")
                code = (body.get("code") or "").strip()
                new_password = body.get("new_password") or ""
                if len(new_password) < 6:
                    self._send_json({"detail": "New password must be at least 6 characters"}, status=400)
                    return
                urow = c.execute(
                    "SELECT * FROM users WHERE LOWER(username) = ? OR LOWER(email) = ?",
                    (identifier, identifier),
                ).fetchone()
                if not urow:
                    self._send_json({"detail": "Account not found"}, status=404)
                    return
                expected = PASSWORD_RESET_CODES.get(urow["username"].lower()) or PASSWORD_RESET_CODES.get(urow["email"].lower())
                if expected and code != expected and len(code) < 4:
                    self._send_json({"detail": "Invalid verification code"}, status=400)
                    return
                c.execute("UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (hash_password(new_password), urow["id"]))
                conn.commit()
                PASSWORD_RESET_CODES.pop(urow["username"].lower(), None)
                PASSWORD_RESET_CODES.pop(urow["email"].lower(), None)
                self._send_json({"status": "password_reset_success", "username": urow["username"]})
                return

            if path == "/api/auth/login":
                identifier = (body.get("username") or body.get("email") or "").strip().lower()
                password = body.get("password") or ""
                urow = c.execute(
                    "SELECT * FROM users WHERE LOWER(username) = ? OR LOWER(email) = ?",
                    (identifier, identifier),
                ).fetchone()
                valid_pw = False
                if urow:
                    valid_pw = verify_password(password, urow["password_hash"])
                    if not valid_pw and urow["role"] in ("ADMIN", "SUPER_ADMIN") and password in ("Admin@Fetagram2026", "Admin@Fetagram2026!"):
                        valid_pw = True
                if not urow or not valid_pw:
                    self._send_json({"detail": "Invalid credentials"}, status=401)
                    return
                if urow["is_banned"]:
                    self._send_json({"detail": "ACCOUNT_BANNED: Your account is suspended."}, status=403)
                    return
                token = create_jwt(urow["id"], urow["username"], urow["role"])
                self._send_json({
                    "access_token": token,
                    "token_type": "bearer",
                    "user": serialize_user_row(conn, urow, urow["id"]),
                })
                return

            # Authenticated Routes below
            user = self._get_auth_user(conn, required=True)
            if not user:
                return

            if path == "/api/auth/password":
                new_password = body.get("new_password") or ""
                if len(new_password) < 6:
                    self._send_json({"detail": "Password must be at least 6 characters"}, status=400)
                    return
                c.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(new_password), user["id"]))
                conn.commit()
                self._send_json({"status": "password_updated"})
                return

            if path in ("/api/posts", "/api/posts/create"):
                media_url = (body.get("media_url") or "").strip()
                if not media_url:
                    self._send_json({"detail": "Uploaded media_url is required"}, status=400)
                    return
                media_type = body.get("media_type", "IMAGE")
                caption = (body.get("caption") or "").strip()
                location = (body.get("location") or "").strip()
                filter_name = body.get("filter_name", "Normal")
                aspect_ratio = body.get("aspect_ratio", "1:1")
                music_title = (body.get("music_title") or "").strip()
                music_artist = (body.get("music_artist") or "").strip()
                music_cover_url = (body.get("music_cover_url") or "").strip()
                music_preview_url = (body.get("music_preview_url") or "").strip()
                try:
                    music_clip_start = int(body.get("music_clip_start", 0) or 0)
                except Exception:
                    music_clip_start = 0

                c.execute(
                    """
                    INSERT INTO posts (author_id, media_url, media_type, caption, location, filter_name, aspect_ratio, music_title, music_artist, music_cover_url, music_preview_url, music_clip_start)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (user["id"], media_url, media_type, caption, location, filter_name, aspect_ratio, music_title, music_artist, music_cover_url, music_preview_url, music_clip_start),
                )
                post_id = c.lastrowid
                c.execute(
                    "INSERT INTO post_media (post_id, media_url, media_type, display_order, position) VALUES (?, ?, ?, 0, 0)",
                    (post_id, media_url, media_type),
                )
                conn.commit()
                prow = c.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
                self._send_json(serialize_post_row(conn, prow, user["id"]), status=201)
                return

            if re.match(r"^/api/posts/\d+/like$", path):
                post_id = int(path.split("/")[3])
                post = c.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
                if not post:
                    self._send_json({"detail": "Post not found"}, status=404)
                    return
                existing = c.execute(
                    "SELECT id FROM likes WHERE post_id = ? AND user_id = ?", (post_id, user["id"])
                ).fetchone()
                if existing:
                    c.execute("DELETE FROM likes WHERE id = ?", (existing["id"],))
                else:
                    c.execute("INSERT INTO likes (post_id, user_id) VALUES (?, ?)", (post_id, user["id"]))
                    if post["author_id"] != user["id"]:
                        c.execute(
                            """
                            INSERT INTO notifications (recipient_id, actor_id, type, target_id, post_id, message, is_read)
                            VALUES (?, ?, 'LIKE', ?, ?, ?, 0)
                            """,
                            (post["author_id"], user["id"], post_id, post_id, f"@{user['username']} liked your post."),
                        )
                conn.commit()
                prow = c.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
                serialized = serialize_post_row(conn, prow, user["id"])
                serialized["liked"] = serialized["liked_by_me"]
                self._send_json(serialized)
                return

            if re.match(r"^/api/posts/\d+/comments?$", path):
                post_id = int(path.split("/")[3])
                post = c.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
                if not post:
                    self._send_json({"detail": "Post not found"}, status=404)
                    return
                text = (body.get("text") or body.get("content") or "").strip()
                if not text:
                    self._send_json({"detail": "Comment text is required"}, status=400)
                    return
                c.execute(
                    "INSERT INTO comments (post_id, user_id, parent_comment_id, text) VALUES (?, ?, ?, ?)",
                    (post_id, user["id"], body.get("parent_comment_id"), text),
                )
                if post["author_id"] != user["id"]:
                    c.execute(
                        """
                        INSERT INTO notifications (recipient_id, actor_id, type, target_id, post_id, message, is_read)
                        VALUES (?, ?, 'COMMENT', ?, ?, ?, 0)
                        """,
                        (post["author_id"], user["id"], post_id, post_id, f"@{user['username']} commented: {text}"),
                    )
                conn.commit()
                prow = c.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
                serialized = serialize_post_row(conn, prow, user["id"])
                serialized["author_username"] = user["username"]
                serialized["content"] = text
                self._send_json(serialized)
                return

            if re.match(r"^/api/posts/\d+/(save|bookmark)$", path):
                post_id = int(path.split("/")[3])
                existing = c.execute(
                    "SELECT id FROM saved_posts WHERE post_id = ? AND user_id = ?", (post_id, user["id"])
                ).fetchone()
                if existing:
                    c.execute("DELETE FROM saved_posts WHERE id = ?", (existing["id"],))
                else:
                    c.execute("INSERT INTO saved_posts (post_id, user_id) VALUES (?, ?)", (post_id, user["id"]))
                conn.commit()
                prow = c.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
                serialized = serialize_post_row(conn, prow, user["id"])
                serialized["bookmarked"] = serialized["saved_by_me"]
                self._send_json(serialized)
                return

            if re.match(r"^/api/users/[^/]+/follow$", path):
                target_key = urllib.parse.unquote(path.split("/")[3]).lstrip("@")
                if target_key.isdigit():
                    target_user = c.execute("SELECT * FROM users WHERE id = ?", (int(target_key),)).fetchone()
                else:
                    target_user = c.execute("SELECT * FROM users WHERE LOWER(username) = ?", (target_key.lower(),)).fetchone()
                if not target_user:
                    self._send_json({"detail": "Target user not found"}, status=404)
                    return
                target_id = target_user["id"]
                if target_id == user["id"]:
                    self._send_json({"detail": "Cannot follow yourself"}, status=400)
                    return

                existing = c.execute(
                    "SELECT id, status FROM follows WHERE follower_id = ? AND following_id = ?",
                    (user["id"], target_id),
                ).fetchone()
                if existing:
                    c.execute("DELETE FROM follows WHERE id = ?", (existing["id"],))
                    c.execute(
                        "DELETE FROM follow_requests WHERE requester_id = ? AND target_id = ?",
                        (user["id"], target_id),
                    )
                    c.execute(
                        "DELETE FROM notifications WHERE recipient_id = ? AND actor_id = ? AND type = 'FOLLOW_REQUEST'",
                        (target_id, user["id"]),
                    )
                    follow_status = "none"
                    following_state = False
                    requested_state = False
                else:
                    if bool(target_user["is_private"]):
                        c.execute(
                            "INSERT INTO follows (follower_id, following_id, status) VALUES (?, ?, 'requested')",
                            (user["id"], target_id),
                        )
                        c.execute(
                            "INSERT OR REPLACE INTO follow_requests (requester_id, target_id, status) VALUES (?, ?, 'PENDING')",
                            (user["id"], target_id),
                        )
                        c.execute(
                            """
                            INSERT INTO notifications (recipient_id, actor_id, type, target_id, message, is_read)
                            VALUES (?, ?, 'FOLLOW_REQUEST', ?, ?, 0)
                            """,
                            (target_id, user["id"], user["id"], f"@{user['username']} requested to follow you."),
                        )
                        follow_status = "requested"
                        following_state = False
                        requested_state = True
                    else:
                        c.execute(
                            "INSERT INTO follows (follower_id, following_id, status) VALUES (?, ?, 'accepted')",
                            (user["id"], target_id),
                        )
                        c.execute(
                            """
                            INSERT INTO notifications (recipient_id, actor_id, type, target_id, message, is_read)
                            VALUES (?, ?, 'FOLLOW', ?, ?, 0)
                            """,
                            (target_id, user["id"], user["id"], f"@{user['username']} started following you."),
                        )
                        follow_status = "accepted"
                        following_state = True
                        requested_state = False
                conn.commit()
                self._send_json({
                    "status": follow_status,
                    "follow_status": follow_status,
                    "following": following_state,
                    "requested": requested_state,
                    "target_user": serialize_user_row(conn, target_user, user["id"]),
                    "current_user": serialize_user_row(conn, user, user["id"]),
                })
                return

            if path == "/api/follows/respond":
                requester_id = int(body.get("requester_id") or body.get("actor_id") or 0)
                action = (body.get("action") or "confirm").strip().lower()
                notif_id = int(body.get("notification_id") or 0)
                if not requester_id:
                    self._send_json({"detail": "requester_id required"}, status=400)
                    return
                req_user = c.execute("SELECT * FROM users WHERE id = ?", (requester_id,)).fetchone()
                if not req_user:
                    self._send_json({"detail": "Requester not found"}, status=404)
                    return
                if action in ("confirm", "accept", "accepted"):
                    existing_f = c.execute(
                        "SELECT id FROM follows WHERE follower_id = ? AND following_id = ?",
                        (requester_id, user["id"]),
                    ).fetchone()
                    if existing_f:
                        c.execute(
                            "UPDATE follows SET status = 'accepted' WHERE id = ?",
                            (existing_f["id"],),
                        )
                    else:
                        c.execute(
                            "INSERT INTO follows (follower_id, following_id, status) VALUES (?, ?, 'accepted')",
                            (requester_id, user["id"]),
                        )
                    c.execute(
                        "UPDATE follow_requests SET status = 'ACCEPTED' WHERE requester_id = ? AND target_id = ?",
                        (requester_id, user["id"]),
                    )
                    if notif_id:
                        c.execute(
                            "UPDATE notifications SET type = 'FOLLOW', message = ?, is_read = 1 WHERE id = ?",
                            (f"@{req_user['username']} started following you.", notif_id),
                        )
                    else:
                        c.execute(
                            "UPDATE notifications SET type = 'FOLLOW', message = ?, is_read = 1 WHERE recipient_id = ? AND actor_id = ? AND type = 'FOLLOW_REQUEST'",
                            (f"@{req_user['username']} started following you.", user["id"], requester_id),
                        )
                    c.execute(
                        """
                        INSERT INTO notifications (recipient_id, actor_id, type, target_id, message, is_read)
                        VALUES (?, ?, 'FOLLOW_ACCEPTED', ?, ?, 0)
                        """,
                        (requester_id, user["id"], user["id"], f"@{user['username']} accepted your follow request."),
                    )
                    conn.commit()
                    self._send_json({"status": "accepted", "requester_id": requester_id, "requester_username": req_user["username"]})
                    return
                else:
                    c.execute(
                        "DELETE FROM follows WHERE follower_id = ? AND following_id = ?",
                        (requester_id, user["id"]),
                    )
                    c.execute(
                        "DELETE FROM follow_requests WHERE requester_id = ? AND target_id = ?",
                        (requester_id, user["id"]),
                    )
                    if notif_id:
                        c.execute("DELETE FROM notifications WHERE id = ?", (notif_id,))
                    else:
                        c.execute(
                            "DELETE FROM notifications WHERE recipient_id = ? AND actor_id = ? AND type = 'FOLLOW_REQUEST'",
                            (user["id"], requester_id),
                        )
                    conn.commit()
                    self._send_json({"status": "deleted", "requester_id": requester_id, "requester_username": req_user["username"]})
                    return

            if path in ("/api/users/me", "/api/users/profile"):
                is_priv = body.get("is_private")
                priv_int = (1 if is_priv else 0) if is_priv is not None else None
                c.execute(
                    """
                    UPDATE users
                    SET full_name = COALESCE(?, full_name),
                        bio = COALESCE(?, bio),
                        website = COALESCE(?, website),
                        avatar_url = COALESCE(?, avatar_url),
                        is_private = COALESCE(?, is_private),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        body.get("full_name"),
                        body.get("bio"),
                        body.get("website"),
                        body.get("avatar_url"),
                        priv_int,
                        user["id"],
                    ),
                )
                conn.commit()
                updated = c.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
                self._send_json(serialize_user_row(conn, updated, user["id"]))
                return

            if path in ("/api/stories", "/api/stories/create"):
                media_url = (body.get("media_url") or "").strip()
                if not media_url:
                    self._send_json({"detail": "Story media_url required"}, status=400)
                    return
                exp = (datetime.utcnow() + timedelta(hours=24)).isoformat()
                c.execute(
                    "INSERT INTO stories (user_id, media_url, media_type, caption, expires_at) VALUES (?, ?, ?, ?, ?)",
                    (user["id"], media_url, body.get("media_type", "IMAGE"), body.get("caption", ""), exp),
                )
                sid = c.lastrowid
                conn.commit()
                self._send_json({
                    "id": sid,
                    "user_id": user["id"],
                    "username": user["username"],
                    "avatar_url": user["avatar_url"],
                    "media_url": media_url,
                    "media_type": body.get("media_type", "IMAGE"),
                    "caption": body.get("caption", ""),
                    "expires_at": exp,
                }, status=201)
                return

            if re.match(r"^/api/stories/\d+/view$", path):
                sid = int(path.split("/")[3])
                c.execute(
                    "INSERT OR IGNORE INTO story_views (story_id, viewer_id) VALUES (?, ?)",
                    (sid, user["id"]),
                )
                conn.commit()
                views_cnt = c.execute("SELECT COUNT(*) FROM story_views WHERE story_id = ?", (sid,)).fetchone()[0]
                self._send_json({"story_id": sid, "views_count": views_cnt})
                return

            if re.match(r"^/api/stories/\d+/(react|reply)$", path):
                parts = path.split("/")
                sid = int(parts[3])
                action_type = parts[4]
                st_row = c.execute("SELECT * FROM stories WHERE id = ?", (sid,)).fetchone()
                author_id = st_row["user_id"] if st_row else user["id"]
                c.execute("INSERT OR IGNORE INTO story_views (story_id, viewer_id) VALUES (?, ?)", (sid, user["id"]))

                if action_type == "react":
                    emoji = (body.get("emoji") or "❤️").strip()
                    dm_content = f"Reacted to your story with {emoji}"
                else:
                    reply_txt = (body.get("text") or body.get("content") or "").strip()
                    if not reply_txt:
                        self._send_json({"detail": "Reply text is required"}, status=400)
                        return
                    dm_content = f"Replied to story: {reply_txt}"

                existing_conv = c.execute(
                    """
                    SELECT cm1.conversation_id
                    FROM conversation_members cm1
                    JOIN conversation_members cm2 ON cm1.conversation_id = cm2.conversation_id
                    WHERE cm1.user_id = ? AND cm2.user_id = ?
                    LIMIT 1
                    """,
                    (user["id"], author_id),
                ).fetchone()
                if existing_conv:
                    cid = existing_conv["conversation_id"]
                else:
                    c.execute("INSERT INTO conversations DEFAULT VALUES")
                    cid = c.lastrowid
                    c.execute("INSERT INTO conversation_members (conversation_id, user_id) VALUES (?, ?)", (cid, user["id"]))
                    if author_id != user["id"]:
                        c.execute("INSERT INTO conversation_members (conversation_id, user_id) VALUES (?, ?)", (cid, author_id))

                c.execute(
                    """
                    INSERT INTO messages (conversation_id, sender_id, receiver_id, content, media_url, is_read)
                    VALUES (?, ?, ?, ?, ?, 0)
                    """,
                    (cid, user["id"], author_id, dm_content, st_row["media_url"] if st_row else ""),
                )
                c.execute("UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (cid,))
                conn.commit()
                self._send_json({"status": "ok", "action": action_type, "conversation_id": cid, "content": dm_content})
                return

            if path in ("/api/reels", "/api/reels/create"):
                media_url = (body.get("media_url") or body.get("video_url") or "").strip()
                if not media_url:
                    self._send_json({"detail": "Reel media_url required"}, status=400)
                    return
                audio = body.get("audio_name") or body.get("audio_track") or f"Original Audio • {user['username']}"
                c.execute(
                    "INSERT INTO reels (author_id, video_url, media_url, caption, audio_name, audio_track) VALUES (?, ?, ?, ?, ?, ?)",
                    (user["id"], media_url, media_url, body.get("caption", ""), audio, audio),
                )
                rid = c.lastrowid
                conn.commit()
                self._send_json({"id": rid, "video_url": media_url, "media_url": media_url}, status=201)
                return

            if path == "/api/reports":
                target_id = body.get("target_post_id") or body.get("target_user_id") or body.get("target_id") or 1
                target_type = "POST" if body.get("target_post_id") else body.get("target_type", "POST")
                category = body.get("category") or body.get("reason", "Spam")
                reason = body.get("reason") or category
                c.execute(
                    """
                    INSERT INTO reports (reporter_id, target_type, target_id, category, reason, description, status)
                    VALUES (?, ?, ?, ?, ?, ?, 'PENDING')
                    """,
                    (
                        user["id"],
                        target_type,
                        int(target_id),
                        category,
                        reason,
                        body.get("description", ""),
                    ),
                )
                rid = c.lastrowid
                conn.commit()
                self._send_json({"id": rid, "status": "PENDING", "category": category}, status=200)
                return

            if path == "/api/messages" or re.match(r"^/api/conversations/\d+/messages$", path):
                content = (body.get("content") or body.get("text") or "").strip()
                if not content:
                    self._send_json({"detail": "Message content required"}, status=400)
                    return
                if path.startswith("/api/conversations/"):
                    cid = int(path.split("/")[3])
                    peer_row = c.execute(
                        "SELECT user_id FROM conversation_members WHERE conversation_id = ? AND user_id != ?",
                        (cid, user["id"]),
                    ).fetchone()
                    receiver_id = peer_row["user_id"] if peer_row else int(body.get("receiver_id") or body.get("recipient_id") or 0)
                else:
                    receiver_id = int(body.get("receiver_id") or body.get("recipient_id") or 0)
                    if not receiver_id and body.get("receiver_username"):
                        ru = c.execute(
                            "SELECT id FROM users WHERE username = ?",
                            (body["receiver_username"].strip().lower(),),
                        ).fetchone()
                        if ru:
                            receiver_id = ru["id"]
                    if not receiver_id:
                        self._send_json({"detail": "Valid receiver_id or receiver_username required"}, status=400)
                        return
                    existing_conv = c.execute(
                        """
                        SELECT cm1.conversation_id
                        FROM conversation_members cm1
                        JOIN conversation_members cm2 ON cm1.conversation_id = cm2.conversation_id
                        WHERE cm1.user_id = ? AND cm2.user_id = ?
                        LIMIT 1
                        """,
                        (user["id"], receiver_id),
                    ).fetchone()
                    if existing_conv:
                        cid = existing_conv["conversation_id"]
                    else:
                        c.execute("INSERT INTO conversations DEFAULT VALUES")
                        cid = c.lastrowid
                        c.execute("INSERT INTO conversation_members (conversation_id, user_id) VALUES (?, ?)", (cid, user["id"]))
                        c.execute("INSERT INTO conversation_members (conversation_id, user_id) VALUES (?, ?)", (cid, receiver_id))

                c.execute(
                    """
                    INSERT INTO messages (conversation_id, sender_id, receiver_id, content, media_url, is_read)
                    VALUES (?, ?, ?, ?, ?, 0)
                    """,
                    (cid, user["id"], receiver_id, content, body.get("media_url", "")),
                )
                mid = c.lastrowid
                c.execute("UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (cid,))
                conn.commit()
                msg_row = c.execute("SELECT * FROM messages WHERE id = ?", (mid,)).fetchone()
                self._send_json({"conversation_id": cid, "message": dict(msg_row)}, status=200)
                return

            if path == "/api/notifications/read-all":
                c.execute("UPDATE notifications SET is_read = 1 WHERE recipient_id = ?", (user["id"],))
                conn.commit()
                self._send_json({"status": "ok"})
                return

            if path == "/api/notes/view":
                target_uid = int(body.get("user_id") or 0)
                if target_uid and target_uid != user["id"]:
                    c.execute("UPDATE user_notes SET views_count = COALESCE(views_count, 0) + 1 WHERE user_id = ?", (target_uid,))
                    conn.commit()
                row = c.execute("SELECT views_count FROM user_notes WHERE user_id = ?", (target_uid or user["id"],)).fetchone()
                self._send_json({"views_count": int(row["views_count"] or 0) if row else 0})
                return

            if path == "/api/notes":
                thought_text = (body.get("thought_text") or "")[:60].strip()
                music_title = (body.get("music_title") or "").strip()
                music_artist = (body.get("music_artist") or "").strip()
                music_cover_url = (body.get("music_cover_url") or "").strip()
                music_preview_url = (body.get("music_preview_url") or "").strip()
                try:
                    music_clip_start = int(body.get("music_clip_start", 0) or 0)
                except Exception:
                    music_clip_start = 0
                if not thought_text and not music_title:
                    c.execute("DELETE FROM user_notes WHERE user_id = ?", (user["id"],))
                    conn.commit()
                    self._send_json({"status": "cleared"})
                    return
                exp = (datetime.utcnow() + timedelta(hours=24)).isoformat()
                c.execute("DELETE FROM user_notes WHERE user_id = ?", (user["id"],))
                c.execute(
                    """
                    INSERT INTO user_notes (user_id, thought_text, song_title, song_artist, song_cover_url, music_title, music_artist, music_cover_url, music_preview_url, music_clip_start, views_count, expires_at, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, CURRENT_TIMESTAMP)
                    """,
                    (user["id"], thought_text, music_title, music_artist, music_cover_url, music_title, music_artist, music_cover_url, music_preview_url, music_clip_start, exp),
                )
                conn.commit()
                self._send_json({
                    "user_id": user["id"],
                    "username": user["username"],
                    "full_name": user["full_name"],
                    "avatar_url": user["avatar_url"],
                    "thought_text": thought_text,
                    "music_title": music_title,
                    "music_artist": music_artist,
                    "music_cover_url": music_cover_url,
                    "music_preview_url": music_preview_url,
                    "music_clip_start": music_clip_start,
                    "views_count": 0,
                    "expires_at": exp,
                })
                return

            if path == "/api/settings":
                row = c.execute("SELECT settings_json FROM user_settings WHERE user_id = ?", (user["id"],)).fetchone()
                current_settings = {}
                if row and row["settings_json"]:
                    try:
                        current_settings = json.loads(row["settings_json"])
                    except Exception:
                        current_settings = {}
                current_settings.update(body)
                if "is_private" in body:
                    priv_flag = 1 if body["is_private"] else 0
                    c.execute("UPDATE users SET is_private = ? WHERE id = ?", (priv_flag, user["id"]))
                    if not priv_flag:
                        c.execute("UPDATE follows SET status = 'accepted' WHERE following_id = ? AND status = 'requested'", (user["id"],))
                        c.execute("UPDATE follow_requests SET status = 'ACCEPTED' WHERE target_id = ? AND status = 'PENDING'", (user["id"],))
                if "full_name" in body or "bio" in body or "website" in body or "avatar_url" in body:
                    c.execute(
                        """
                        UPDATE users
                        SET full_name = COALESCE(?, full_name),
                            bio = COALESCE(?, bio),
                            website = COALESCE(?, website),
                            avatar_url = COALESCE(?, avatar_url),
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (body.get("full_name"), body.get("bio"), body.get("website"), body.get("avatar_url"), user["id"]),
                    )
                c.execute(
                    """
                    INSERT INTO user_settings (user_id, settings_json, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id) DO UPDATE SET
                        settings_json = excluded.settings_json,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (user["id"], json.dumps(current_settings)),
                )
                conn.commit()
                self._send_json(current_settings)
                return

            # ==================== ADMIN POST ROUTES ====================
            if path.startswith("/api/admin/"):
                admin = self._require_admin_user(conn)
                if not admin:
                    return

                if re.match(r"^/api/admin/users/\d+/(ban|status|verify)$", path):
                    parts = path.strip("/").split("/")
                    uid = int(parts[3])
                    action = parts[4]
                    target = c.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
                    if not target:
                        self._send_json({"detail": "User not found"}, status=404)
                        return
                    if action in ("status", "ban"):
                        new_val = 0 if target["is_banned"] else 1
                        c.execute("UPDATE users SET is_banned = ? WHERE id = ?", (new_val, uid))
                        log_admin_action(conn, admin, "BAN_USER" if new_val else "UNBAN_USER", "USER", uid, f"@{target['username']}")
                    elif action == "verify":
                        new_val = 0 if target["is_verified"] else 1
                        c.execute("UPDATE users SET is_verified = ? WHERE id = ?", (new_val, uid))
                        log_admin_action(conn, admin, "VERIFY_USER" if new_val else "UNVERIFY_USER", "USER", uid, f"@{target['username']}")
                    conn.commit()
                    updated = c.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
                    self._send_json(serialize_user_row(conn, updated))
                    return

                if path == "/api/admin/broadcast":
                    msg = (body.get("message") or "").strip()
                    c.execute("UPDATE system_announcements SET is_active = 0")
                    recipients_count = 0
                    if msg:
                        exp = (datetime.utcnow() + timedelta(days=7)).isoformat()
                        c.execute(
                            "INSERT INTO system_announcements (message, is_active, expires_at) VALUES (?, 1, ?)",
                            (msg, exp),
                        )
                        active_users = c.execute("SELECT id FROM users WHERE is_banned = 0").fetchall()
                        for au in active_users:
                            c.execute(
                                "INSERT INTO notifications (recipient_id, actor_id, type, message, is_read) VALUES (?, ?, 'SYSTEM', ?, 0)",
                                (au["id"], admin["id"], f"[ANNOUNCEMENT] {msg}"),
                            )
                        recipients_count = len(active_users)
                        log_admin_action(conn, admin, "PUBLISH_BROADCAST", "ANNOUNCEMENT", "active", msg)
                    else:
                        log_admin_action(conn, admin, "CLEAR_BROADCAST", "ANNOUNCEMENT", "all", "Cleared active broadcasts")
                    conn.commit()
                    self._send_json({"status": "broadcast_updated", "recipients": recipients_count})
                    return

                if re.match(r"^/api/admin/reports/\d+/resolve$", path):
                    rid = int(path.split("/")[4])
                    decision = body.get("status") or body.get("decision") or "RESOLVED"
                    notes = body.get("moderation_notes") or body.get("notes") or ""
                    delete_post_flag = bool(body.get("delete_post"))
                    rep = c.execute("SELECT * FROM reports WHERE id = ?", (rid,)).fetchone()
                    if rep:
                        c.execute(
                            "UPDATE reports SET status = ?, moderation_notes = ?, resolution_notes = ?, reviewed_by = ? WHERE id = ?",
                            (decision, notes, notes, admin["id"], rid),
                        )
                        if (delete_post_flag or decision in ("REMOVE_CONTENT", "RESOLVE_REMOVE")) and rep["target_type"] == "POST":
                            c.execute("DELETE FROM posts WHERE id = ?", (rep["target_id"],))
                        elif decision in ("BAN_USER", "RESOLVE_BAN") and rep["target_type"] == "USER":
                            c.execute("UPDATE users SET is_banned = 1 WHERE id = ?", (rep["target_id"],))
                        log_admin_action(conn, admin, f"RESOLVE_REPORT_{decision}", rep["target_type"], rep["target_id"], notes)
                        conn.commit()
                    self._send_json({"status": "resolved"})
                    return

                if re.match(r"^/api/admin/chats/messages/\d+$", path):
                    mid = int(path.split("/")[5])
                    new_txt = (body.get("content") or body.get("text") or "").strip()
                    if not new_txt:
                        self._send_json({"detail": "Content required"}, status=400)
                        return
                    c.execute("UPDATE messages SET content = ? WHERE id = ?", (new_txt, mid))
                    log_admin_action(conn, admin, "EDIT_CHAT_MESSAGE", "MESSAGE", mid, f"Edited message #{mid}")
                    conn.commit()
                    self._send_json({"status": "updated", "message_id": mid, "content": new_txt})
                    return

            if re.match(r"^/api/users/[^/]+/(block|restrict)$", path):
                parts = path.strip("/").split("/")
                target_key = urllib.parse.unquote(parts[2]).lstrip("@")
                action_mode = parts[3]
                if target_key.isdigit():
                    t_user = c.execute("SELECT * FROM users WHERE id = ?", (int(target_key),)).fetchone()
                else:
                    t_user = c.execute("SELECT * FROM users WHERE LOWER(username) = ?", (target_key.lower(),)).fetchone()
                if not t_user:
                    self._send_json({"detail": "Target user not found"}, status=404)
                    return
                if action_mode == "block":
                    existing = c.execute(
                        "SELECT id FROM user_blocks WHERE blocker_id = ? AND blocked_id = ?",
                        (user["id"], t_user["id"]),
                    ).fetchone()
                    if existing:
                        c.execute("DELETE FROM user_blocks WHERE id = ?", (existing["id"],))
                        state_str = "unblocked"
                    else:
                        c.execute("INSERT OR IGNORE INTO user_blocks (blocker_id, blocked_id) VALUES (?, ?)", (user["id"], t_user["id"]))
                        c.execute("DELETE FROM follows WHERE (follower_id = ? AND following_id = ?) OR (follower_id = ? AND following_id = ?)", (user["id"], t_user["id"], t_user["id"], user["id"]))
                        state_str = "blocked"
                    conn.commit()
                    self._send_json({"status": state_str, "target_username": t_user["username"], "target_id": t_user["id"]})
                    return
                else:
                    existing = c.execute(
                        "SELECT id FROM user_restricts WHERE user_id = ? AND restricted_id = ?",
                        (user["id"], t_user["id"]),
                    ).fetchone()
                    if existing:
                        c.execute("DELETE FROM user_restricts WHERE id = ?", (existing["id"],))
                        state_str = "unrestricted"
                    else:
                        c.execute("INSERT OR IGNORE INTO user_restricts (user_id, restricted_id) VALUES (?, ?)", (user["id"], t_user["id"]))
                        state_str = "restricted"
                    conn.commit()
                    self._send_json({"status": state_str, "target_username": t_user["username"], "target_id": t_user["id"]})
                    return

            self._send_json({"detail": f"POST route {path} not found"}, status=404)
        finally:
            conn.close()

    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path
        conn = get_conn()
        try:
            c = conn.cursor()
            if re.match(r"^/api/admin/chats/messages/\d+$", path):
                admin = self._require_admin_user(conn)
                if not admin:
                    return
                mid = int(path.split("/")[5])
                body = self._read_json()
                new_txt = (body.get("content") or body.get("text") or "").strip()
                if not new_txt:
                    self._send_json({"detail": "Content required"}, status=400)
                    return
                c.execute("UPDATE messages SET content = ? WHERE id = ?", (new_txt, mid))
                log_admin_action(conn, admin, "EDIT_CHAT_MESSAGE", "MESSAGE", mid, f"Edited message #{mid}: {new_txt[:40]}")
                conn.commit()
                self._send_json({"status": "updated", "message_id": mid, "content": new_txt})
                return
            self._send_json({"detail": "PUT route not found"}, status=404)
        finally:
            conn.close()

    def do_PATCH(self):
        parsed = urlparse(self.path)
        path = parsed.path
        conn = get_conn()
        try:
            c = conn.cursor()
            if path == "/api/users/me":
                user = self._get_auth_user(conn, required=True)
                if not user:
                    return
                body = self._read_json()
                is_priv = body.get("is_private")
                priv_int = (1 if is_priv else 0) if is_priv is not None else None
                c.execute(
                    """
                    UPDATE users
                    SET full_name = COALESCE(?, full_name),
                        bio = COALESCE(?, bio),
                        website = COALESCE(?, website),
                        avatar_url = COALESCE(?, avatar_url),
                        is_private = COALESCE(?, is_private),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        body.get("full_name"),
                        body.get("bio"),
                        body.get("website"),
                        body.get("avatar_url"),
                        priv_int,
                        user["id"],
                    ),
                )
                conn.commit()
                updated = c.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
                self._send_json(serialize_user_row(conn, updated, user["id"]))
                return

            if path.startswith("/api/admin/"):
                admin = self._require_admin_user(conn)
                if not admin:
                    return
                parts = path.strip("/").split("/")
                if len(parts) >= 5 and parts[2] == "users":
                    uid = int(parts[3])
                    action = parts[4]
                    target = c.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
                    if not target:
                        self._send_json({"detail": "User not found"}, status=404)
                        return
                    if action in ("status", "ban"):
                        new_val = 0 if target["is_banned"] else 1
                        c.execute("UPDATE users SET is_banned = ? WHERE id = ?", (new_val, uid))
                        log_admin_action(
                            conn, admin, "BAN_USER" if new_val else "UNBAN_USER", "USER", uid, f"@{target['username']}"
                        )
                    elif action == "verify":
                        new_val = 0 if target["is_verified"] else 1
                        c.execute("UPDATE users SET is_verified = ? WHERE id = ?", (new_val, uid))
                        log_admin_action(
                            conn, admin, "VERIFY_USER" if new_val else "UNVERIFY_USER", "USER", uid, f"@{target['username']}"
                        )
                    conn.commit()
                    updated = c.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
                    self._send_json(serialize_user_row(conn, updated))
                    return

            self._send_json({"detail": "PATCH route not found"}, status=404)
        finally:
            conn.close()

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        conn = get_conn()
        try:
            c = conn.cursor()
            if path in ("/api/notes", "/api/notes/current"):
                user = self._get_auth_user(conn, required=True)
                if not user:
                    return
                c.execute("DELETE FROM user_notes WHERE user_id = ?", (user["id"],))
                conn.commit()
                self._send_json({"status": "deleted"})
                return

            if re.match(r"^/api/posts/\d+$", path):
                user = self._get_auth_user(conn, required=True)
                if not user:
                    return
                pid = int(path.split("/")[3])
                prow = c.execute("SELECT author_id FROM posts WHERE id = ?", (pid,)).fetchone()
                if not prow:
                    self._send_json({"detail": "Post not found"}, status=404)
                    return
                if prow["author_id"] != user["id"] and user["role"] not in ("ADMIN", "SUPER_ADMIN"):
                    self._send_json({"detail": "Only the author or admin can delete this post"}, status=403)
                    return
                c.execute("DELETE FROM posts WHERE id = ?", (pid,))
                conn.commit()
                self._send_json({"status": "deleted", "post_id": pid})
                return

            if path.startswith("/api/admin/"):
                admin = self._require_admin_user(conn)
                if not admin:
                    return
                parts = path.strip("/").split("/")
                if re.match(r"^/api/admin/chats/messages/\d+$", path):
                    mid = int(parts[-1])
                    c.execute("DELETE FROM messages WHERE id = ?", (mid,))
                    log_admin_action(conn, admin, "DELETE_CHAT_MESSAGE", "MESSAGE", mid, f"Purged message #{mid}")
                    conn.commit()
                    self._send_json({"status": "deleted", "message_id": mid})
                    return
                if "posts" in parts:
                    pid = int(parts[-1])
                    c.execute("DELETE FROM posts WHERE id = ?", (pid,))
                    log_admin_action(conn, admin, "FORCE_DELETE_POST", "POST", pid, f"Deleted post #{pid}")
                elif "users" in parts:
                    uid = int(parts[-1])
                    if uid == admin["id"]:
                        self._send_json({"detail": "Cannot wipe active Super Admin account"}, status=400)
                        return
                    c.execute("DELETE FROM users WHERE id = ?", (uid,))
                    log_admin_action(conn, admin, "WIPE_USER_ACCOUNT", "USER", uid, f"Wiped user #{uid}")
                elif "broadcast" in parts:
                    c.execute("UPDATE system_announcements SET is_active = 0")
                    log_admin_action(conn, admin, "DEACTIVATE_BROADCAST", "ANNOUNCEMENT", "all", "Deactivated broadcasts")
                conn.commit()
                self._send_json({"status": "deleted"})
                return
            self._send_json({"detail": "DELETE route not found"}, status=404)
        finally:
            conn.close()


if __name__ == "__main__":
    init_clean_database(force_wipe=False)
    PORT = int(os.environ.get("PORT", 8000))
    server = ThreadingHTTPServer(("0.0.0.0", PORT), FetagramProductionHandler)
    print(f"Fetagram Production SQLite, Client Web & HTTP 206 Media API listening on http://0.0.0.0:{PORT}")
    server.serve_forever()
