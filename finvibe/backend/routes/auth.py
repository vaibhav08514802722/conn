"""
Authentication routes — signup, login, current user.
"""
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, EmailStr
from typing import Optional

from backend.services.auth_service import (
    create_user,
    authenticate_user,
    create_token,
    get_user_from_token,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


# ─────────── Request / Response Models ──────────────────────────────────

class SignupRequest(BaseModel):
    name: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    status: str
    token: str
    user: dict


class UserResponse(BaseModel):
    status: str
    user: dict


# ─────────── Routes ─────────────────────────────────────────────────────

@router.post("/signup", response_model=AuthResponse)
async def signup(req: SignupRequest):
    """Register a new user account."""
    if len(req.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    if not req.name.strip():
        raise HTTPException(400, "Name is required")
    if "@" not in req.email:
        raise HTTPException(400, "Invalid email address")

    try:
        user = await create_user(req.name, req.email, req.password)
        token = create_token(
            user_id=str(user["_id"]),
            email=user["email"],
            name=user["name"],
        )
        return {
            "status": "ok",
            "token": token,
            "user": {
                "id": str(user["_id"]),
                "name": user["name"],
                "email": user["email"],
            },
        }
    except ValueError as e:
        raise HTTPException(409, str(e))


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest):
    """Authenticate and return a JWT token."""
    try:
        user = await authenticate_user(req.email, req.password)
        token = create_token(
            user_id=str(user["_id"]),
            email=user["email"],
            name=user["name"],
        )
        return {
            "status": "ok",
            "token": token,
            "user": {
                "id": str(user["_id"]),
                "name": user["name"],
                "email": user["email"],
            },
        }
    except ValueError as e:
        raise HTTPException(401, str(e))


@router.get("/me", response_model=UserResponse)
async def get_current_user(authorization: Optional[str] = Header(None)):
    """Get current user from Bearer token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid Authorization header")

    token = authorization.split(" ", 1)[1]
    user = await get_user_from_token(token)
    if not user:
        raise HTTPException(401, "Invalid or expired token")

    return {"status": "ok", "user": user}
