"""
─────────────────────────────────────────────────────────────────────────────
Phase 3 — Memory Service
Stores and retrieves chat sessions + messages in MongoDB.
─────────────────────────────────────────────────────────────────────────────
"""

import uuid
from datetime import datetime

from backend.deps import get_db


# ── Session management ────────────────────────────────────────────────────────

def create_session(user_id: str, title: str = "New Chat") -> str:
    """Create a new chat session and return its ID."""
    db = get_db()
    session_id = str(uuid.uuid4())
    db.chat_sessions.insert_one({
        "_id":         session_id,
        "user_id":     user_id,
        "title":       title,
        "created_at":  datetime.utcnow().isoformat(),
        "message_count": 0,
    })
    return session_id


def list_sessions(user_id: str) -> list:
    """Return all chat sessions for a user, newest first."""
    db = get_db()
    sessions = db.chat_sessions.find(
        {"user_id": user_id},
        sort=[("created_at", -1)],
    )
    return [
        {
            "id":            s["_id"],
            "title":         s.get("title", "Chat"),
            "created_at":    s.get("created_at", ""),
            "message_count": s.get("message_count", 0),
        }
        for s in sessions
    ]


def delete_session(session_id: str, user_id: str) -> bool:
    """Delete a session and all its messages. Returns True if deleted."""
    db = get_db()
    result = db.chat_sessions.delete_one({"_id": session_id, "user_id": user_id})
    if result.deleted_count:
        db.messages.delete_many({"session_id": session_id})
        return True
    return False


# ── Message management ────────────────────────────────────────────────────────

def save_message(session_id: str, role: str, content: str, citations: list = None):
    """Append a message to a session."""
    db = get_db()
    db.messages.insert_one({
        "session_id": session_id,
        "role":       role,       # "user" | "assistant"
        "content":    content,
        "citations":  citations or [],
        "timestamp":  datetime.utcnow().isoformat(),
    })
    # Keep message count up-to-date on the session document
    db.chat_sessions.update_one(
        {"_id": session_id},
        {"$inc": {"message_count": 1}},
    )


def get_history(session_id: str, limit: int = 10) -> list:
    """
    Return the last `limit` messages for a session.
    Each item: { role, content, citations, timestamp }
    """
    db = get_db()
    messages = list(
        db.messages.find(
            {"session_id": session_id},
            sort=[("timestamp", -1)],
            limit=limit,
        )
    )
    # Reverse so oldest-first (natural conversation order)
    messages.reverse()
    return [
        {
            "role":      m["role"],
            "content":   m["content"],
            "citations": m.get("citations", []),
            "timestamp": m.get("timestamp", ""),
        }
        for m in messages
    ]


def auto_title_session(session_id: str, first_question: str):
    """Set the session title based on the user's first question (truncated)."""
    title = first_question[:60] + ("…" if len(first_question) > 60 else "")
    get_db().chat_sessions.update_one(
        {"_id": session_id}, {"$set": {"title": title}}
    )

