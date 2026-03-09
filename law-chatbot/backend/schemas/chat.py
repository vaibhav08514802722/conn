"""
─────────────────────────────────────────────────────────────────────────────
Law Chatbot — Chat Schemas
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None  # None = start a new session


class Citation(BaseModel):
    section: str          # e.g. "Section 302"
    act: str              # e.g. "Indian Penal Code, 1860"
    chapter: Optional[str] = None
    page: Optional[int] = None
    source: str           # document title or URL
    relevance_score: float = Field(ge=0.0, le=1.0)


class ChatResponse(BaseModel):
    answer: str
    citations: List[Citation] = []
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    disclaimer: str = (
        "This is informational only and does not constitute legal advice. "
        "Please consult a qualified lawyer for your specific situation."
    )
    related_questions: List[str] = []
    session_id: str


class ChatSession(BaseModel):
    id: str
    user_id: str
    title: str
    created_at: str
    message_count: int = 0


class SessionMessage(BaseModel):
    role: str            # "user" | "assistant"
    content: str
    citations: List[Citation] = []
    timestamp: str
