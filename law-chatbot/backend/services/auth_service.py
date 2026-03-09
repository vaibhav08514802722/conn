"""
─────────────────────────────────────────────────────────────────────────────
Phase 4 — Auth Service
JWT (HMAC-SHA256) + password hashing — same pattern as finvibe.
─────────────────────────────────────────────────────────────────────────────
"""

import base64
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta

from backend.config import settings
from backend.deps import get_db

# Token expiry
TOKEN_TTL_HOURS = 24


# ── Password hashing ──────────────────────────────────────────────────────────
def _hash_password(password: str) -> str:
    return hmac.new(
        settings.jwt_secret.encode(),
        password.encode(),
        hashlib.sha256,
    ).hexdigest()


# ── JWT helpers ───────────────────────────────────────────────────────────────
def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    # Re-add padding
    s += "=" * (4 - len(s) % 4)
    return base64.urlsafe_b64decode(s.encode())


def _create_token(payload: dict) -> str:
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = _b64url_encode(json.dumps(payload).encode())
    sig_input = f"{header}.{body}".encode()
    sig = hmac.new(settings.jwt_secret.encode(), sig_input, hashlib.sha256).hexdigest()
    return f"{header}.{body}.{sig}"


def _verify_token(token: str) -> dict | None:
    """Return payload dict if valid; None if invalid or expired."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header, body, sig = parts
        expected_sig = hmac.new(
            settings.jwt_secret.encode(),
            f"{header}.{body}".encode(),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        payload = json.loads(_b64url_decode(body))
        if datetime.utcnow().timestamp() > payload.get("exp", 0):
            return None
        return payload
    except Exception:
        return None


# ── Public API ────────────────────────────────────────────────────────────────
def signup(name: str, email: str, password: str) -> dict:
    """Create a new user. Returns { token, user }. Raises ValueError on conflict."""
    db = get_db()
    if db.users.find_one({"email": email}):
        raise ValueError("An account with this email already exists.")

    user_id = str(uuid.uuid4())
    db.users.insert_one({
        "_id":         user_id,
        "name":        name,
        "email":       email,
        "password":    _hash_password(password),
        "created_at":  datetime.utcnow().isoformat(),
    })

    token = _create_token({
        "sub": user_id,
        "email": email,
        "exp": (datetime.utcnow() + timedelta(hours=TOKEN_TTL_HOURS)).timestamp(),
    })
    return {"token": token, "user": {"id": user_id, "name": name, "email": email}}


def login(email: str, password: str) -> dict:
    """Verify credentials. Returns { token, user }. Raises ValueError on failure."""
    db = get_db()
    user = db.users.find_one({"email": email})
    if not user or user["password"] != _hash_password(password):
        raise ValueError("Invalid email or password.")

    token = _create_token({
        "sub":   user["_id"],
        "email": email,
        "exp":   (datetime.utcnow() + timedelta(hours=TOKEN_TTL_HOURS)).timestamp(),
    })
    return {
        "token": token,
        "user":  {"id": user["_id"], "name": user["name"], "email": email},
    }


def get_current_user(token: str) -> dict:
    """Decode token → return user dict. Raises ValueError if invalid."""
    payload = _verify_token(token)
    if not payload:
        raise ValueError("Token is invalid or expired.")
    db = get_db()
    user = db.users.find_one({"_id": payload["sub"]})
    if not user:
        raise ValueError("User not found.")
    return {"id": user["_id"], "name": user["name"], "email": user["email"]}

