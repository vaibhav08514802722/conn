"""
─────────────────────────────────────────────────────────────────────────────
Law Chatbot — Auth Schemas
─────────────────────────────────────────────────────────────────────────────
"""

from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., description="User email address")
    password: str = Field(..., min_length=6, description="Minimum 6 characters")


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    token: str
    user: dict  # { id, name, email }


class UserMe(BaseModel):
    id: str
    name: str
    email: str
