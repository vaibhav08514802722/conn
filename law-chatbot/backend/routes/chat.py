"""
─────────────────────────────────────────────────────────────────────────────
Phase 3 — Chat Routes
POST /api/chat               — ask a legal question
GET  /api/chat/sessions      — list user's sessions
GET  /api/chat/sessions/{id} — get full session history
DELETE /api/chat/sessions/{id}
─────────────────────────────────────────────────────────────────────────────
"""

from fastapi import APIRouter, HTTPException, Header
from typing import Optional

from backend.schemas.chat import ChatRequest, ChatResponse
from backend.services import chat_service, memory_service, auth_service
from backend.routes.auth import _extract_token

router = APIRouter()


# ── Ask a question ────────────────────────────────────────────────────────────
@router.post("", response_model=ChatResponse)
def ask(body: ChatRequest, authorization: Optional[str] = Header(None)):
    user = _get_user(authorization)
    try:
        return chat_service.ask(
            user_id=user["id"],
            question=body.question,
            session_id=body.session_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Sessions ──────────────────────────────────────────────────────────────────
@router.get("/sessions")
def list_sessions(authorization: Optional[str] = Header(None)):
    user = _get_user(authorization)
    return memory_service.list_sessions(user["id"])


@router.get("/sessions/{session_id}")
def get_session(session_id: str, authorization: Optional[str] = Header(None)):
    _get_user(authorization)  # just verify auth
    history = memory_service.get_history(session_id, limit=50)
    if not history:
        raise HTTPException(status_code=404, detail="Session not found or empty.")
    return {"session_id": session_id, "messages": history}


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str, authorization: Optional[str] = Header(None)):
    user = _get_user(authorization)
    deleted = memory_service.delete_session(session_id, user["id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {"message": "Session deleted."}


@router.post("/sessions")
def new_session(authorization: Optional[str] = Header(None)):
    user = _get_user(authorization)
    session_id = memory_service.create_session(user["id"])
    return {"session_id": session_id}


# ── Auth helper ───────────────────────────────────────────────────────────────
def _get_user(authorization: Optional[str]) -> dict:
    token = _extract_token(authorization)
    try:
        return auth_service.get_current_user(token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

