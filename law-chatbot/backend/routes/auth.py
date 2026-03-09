"""
─────────────────────────────────────────────────────────────────────────────
Phase 4 — Auth Routes
POST /api/auth/signup  |  POST /api/auth/login  |  GET /api/auth/me
─────────────────────────────────────────────────────────────────────────────
"""

from fastapi import APIRouter, HTTPException, Header
from typing import Optional

from backend.schemas.auth import SignupRequest, LoginRequest, AuthResponse, UserMe
from backend.services import auth_service

router = APIRouter()


@router.post("/signup", response_model=AuthResponse)
def signup(body: SignupRequest):
    try:
        return auth_service.signup(body.name, body.email, body.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest):
    try:
        return auth_service.login(body.email, body.password)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.get("/me", response_model=UserMe)
def me(authorization: Optional[str] = Header(None)):
    token = _extract_token(authorization)
    try:
        return auth_service.get_current_user(token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


# ── Helper: pull Bearer token from Authorization header ───────────────────────
def _extract_token(authorization: Optional[str]) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")
    return authorization[7:]

