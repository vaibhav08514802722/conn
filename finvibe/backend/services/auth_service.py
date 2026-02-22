"""
Authentication service — JWT tokens + password hashing.
"""
import hashlib
import hmac
import json
import time
import base64
from datetime import datetime, timezone
from typing import Optional

from backend.config import settings


# ─────────── Password Hashing (SHA-256 + salt — no extra deps) ───────────

def _hash_password(password: str, salt: str = "finvibe_salt_2026") -> str:
    """Hash password with HMAC-SHA256. Simple but effective."""
    return hmac.new(
        salt.encode(), password.encode(), hashlib.sha256
    ).hexdigest()


def verify_password(plain: str, hashed: str) -> bool:
    return hmac.compare_digest(_hash_password(plain), hashed)


# ─────────── JWT (minimal, no PyJWT dependency) ─────────────────────────

_SECRET = "finvibe_jwt_secret_key_2026_hackathon"
_ALGO = "HS256"
_EXPIRY_HOURS = 24


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    s += "=" * (4 - len(s) % 4)
    return base64.urlsafe_b64decode(s)


def create_token(user_id: str, email: str, name: str) -> str:
    """Create a JWT-like token with HS256 signature."""
    header = _b64url_encode(json.dumps({"alg": _ALGO, "typ": "JWT"}).encode())
    payload_data = {
        "sub": user_id,
        "email": email,
        "name": name,
        "iat": int(time.time()),
        "exp": int(time.time()) + _EXPIRY_HOURS * 3600,
    }
    payload = _b64url_encode(json.dumps(payload_data).encode())
    signature = hmac.new(
        _SECRET.encode(), f"{header}.{payload}".encode(), hashlib.sha256
    ).digest()
    sig = _b64url_encode(signature)
    return f"{header}.{payload}.{sig}"


def decode_token(token: str) -> Optional[dict]:
    """Verify and decode a JWT token. Returns None if invalid."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header, payload, sig = parts

        # Verify signature
        expected_sig = hmac.new(
            _SECRET.encode(), f"{header}.{payload}".encode(), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(_b64url_decode(sig), expected_sig):
            return None

        # Decode payload
        data = json.loads(_b64url_decode(payload))

        # Check expiry
        if data.get("exp", 0) < time.time():
            return None

        return data
    except Exception:
        return None


# ─────────── User CRUD ──────────────────────────────────────────────────

async def create_user(name: str, email: str, password: str) -> dict:
    """Register a new user in MongoDB."""
    from backend.deps import get_db

    db = get_db()
    users = db["users"]

    # Check if email already exists
    existing = users.find_one({"email": email.lower()})
    if existing:
        raise ValueError("An account with this email already exists")

    user_doc = {
        "name": name.strip(),
        "email": email.lower().strip(),
        "password_hash": _hash_password(password),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "portfolio_ids": [],
        "phone": "",
        "preferences": {
            "risk_tolerance": "moderate",
            "alert_channels": ["in-app"],
        },
    }
    result = users.insert_one(user_doc)
    user_doc["_id"] = str(result.inserted_id)
    del user_doc["password_hash"]
    return user_doc


async def authenticate_user(email: str, password: str) -> dict:
    """Validate credentials. Returns user dict or raises ValueError."""
    from backend.deps import get_db

    db = get_db()
    users = db["users"]

    user = users.find_one({"email": email.lower().strip()})
    if not user:
        raise ValueError("Invalid email or password")

    if not verify_password(password, user["password_hash"]):
        raise ValueError("Invalid email or password")

    return {
        "_id": str(user["_id"]),
        "name": user["name"],
        "email": user["email"],
        "created_at": user.get("created_at"),
    }


async def get_user_from_token(token: str) -> Optional[dict]:
    """Decode token and fetch user from DB."""
    data = decode_token(token)
    if not data:
        return None
    return {
        "user_id": data["sub"],
        "email": data["email"],
        "name": data["name"],
    }
