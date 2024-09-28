import os
import json
import hmac
import hashlib
import base64
import time
from typing import Optional, Dict, Any
from fastapi import Header, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db
from models.entities import User

JWT_SECRET = os.getenv("JWT_SECRET_KEY", "fetagram-production-hmac-secret-key-2026")
REFRESH_SECRET = os.getenv("JWT_REFRESH_SECRET_KEY", "fetagram-production-refresh-secret-key-2026")


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _b64url_decode(s: str) -> bytes:
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


def create_jwt_token(payload: Dict[str, Any], expires_seconds: int = 86400, is_refresh: bool = False) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    body = dict(payload)
    body["iat"] = int(time.time())
    body["exp"] = int(time.time()) + expires_seconds
    body["type"] = "refresh" if is_refresh else "access"

    h_enc = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    b_enc = _b64url_encode(json.dumps(body, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{h_enc}.{b_enc}".encode("utf-8")
    secret = REFRESH_SECRET if is_refresh else JWT_SECRET
    sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{h_enc}.{b_enc}.{_b64url_encode(sig)}"


def decode_jwt_token(token: str, is_refresh: bool = False) -> Optional[Dict[str, Any]]:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        h_enc, b_enc, sig_enc = parts
        signing_input = f"{h_enc}.{b_enc}".encode("utf-8")
        secret = REFRESH_SECRET if is_refresh else JWT_SECRET
        expected_sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
        if not hmac.compare_digest(_b64url_encode(expected_sig), sig_enc):
            return None
        payload = json.loads(_b64url_decode(b_enc).decode("utf-8"))
        if payload.get("exp", 0) < int(time.time()):
            return None
        return payload
    except Exception:
        return None


def get_current_user(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Bearer token")
    token = authorization.replace("Bearer ", "").strip()
    payload = decode_jwt_token(token)
    if not payload or "user_id" not in payload:
        raise HTTPException(status_code=401, detail="Expired or invalid JWT token")

    user = db.query(User).filter(User.id == int(payload["user_id"])).first()
    if not user:
        raise HTTPException(status_code=401, detail="User account no longer exists")
    if user.is_banned:
        raise HTTPException(status_code=403, detail="ACCOUNT_BANNED")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role not in ("ADMIN", "SUPER_ADMIN"):
        raise HTTPException(status_code=403, detail="Forbidden: ADMIN or SUPER_ADMIN role required")
    return user
