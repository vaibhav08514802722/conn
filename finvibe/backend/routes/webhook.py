"""
Vapi Webhook Route — handles call status callbacks from Vapi.ai.

Vapi sends POST requests here when a call's status changes
(queued, ringing, in-progress, completed, failed).
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Request

from backend.deps import get_db

router = APIRouter(prefix="/api/webhook", tags=["Webhooks"])


@router.post("/vapi")
async def vapi_webhook(request: Request):
    """
    Handle Vapi call status callbacks.

    Vapi sends events like:
      - status-update: call status changed (queued → ringing → in-progress → ended)
      - end-of-call-report: final report with transcript, duration, cost
      - transcript: real-time transcript chunks
    """
    try:
        payload = await request.json()
    except Exception:
        return {"status": "error", "message": "Invalid JSON"}

    event_type = payload.get("message", {}).get("type", "unknown")
    call_id = payload.get("message", {}).get("call", {}).get("id", "")

    print(f"[Vapi Webhook] Event: {event_type}, Call: {call_id}")

    # Store all webhook events in MongoDB for debugging / audit
    webhook_doc = {
        "event_type": event_type,
        "call_id": call_id,
        "payload": payload,
        "received_at": datetime.now(timezone.utc),
    }

    try:
        get_db()["vapi_webhooks"].insert_one(webhook_doc)
    except Exception as e:
        print(f"[Vapi Webhook] Failed to store event: {e}")

    # Handle specific events
    if event_type == "end-of-call-report":
        _handle_call_ended(payload)
    elif event_type == "status-update":
        _handle_status_update(payload)

    return {"status": "ok"}


def _handle_call_ended(payload: dict):
    """Process the end-of-call report — save transcript and update alert."""
    message = payload.get("message", {})
    call = message.get("call", {})
    call_id = call.get("id", "")
    transcript = message.get("transcript", "")
    duration = message.get("endedReason", "unknown")
    cost = message.get("cost", 0)

    print(f"[Vapi Webhook] Call {call_id} ended — reason: {duration}")
    if transcript:
        print(f"[Vapi Webhook] Transcript: {transcript[:200]}...")

    # Update the alert document with call outcome
    try:
        alerts_col = get_db()["alerts"]
        alerts_col.update_one(
            {"call_details.call_id": call_id},
            {"$set": {
                "call_outcome": {
                    "ended_reason": duration,
                    "transcript": transcript,
                    "cost": cost,
                    "completed_at": datetime.now(timezone.utc),
                },
            }},
        )
    except Exception as e:
        print(f"[Vapi Webhook] Failed to update alert: {e}")


def _handle_status_update(payload: dict):
    """Log call status transitions."""
    message = payload.get("message", {})
    call = message.get("call", {})
    status = call.get("status", "unknown")
    call_id = call.get("id", "")
    print(f"[Vapi Webhook] Call {call_id} status → {status}")
