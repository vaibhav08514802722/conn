"""
Vapi.ai Voice Service — triggers emergency phone calls to users during market anxiety.

Sends a POST request to Vapi's API to initiate an outbound call with a crisis script.
Falls back to console logging if VAPI_API_KEY is not configured.
"""
import httpx
from datetime import datetime, timezone

from backend.config import settings

VAPI_BASE_URL = "https://api.vapi.ai"


def trigger_crisis_call(
    phone_number: str,
    alert_reason: str,
    suggested_actions: list[str],
    affected_tickers: list[str],
    anxiety_score: float,
) -> dict:
    """
    Trigger an outbound voice call via Vapi.ai to warn the user about market anxiety.

    Args:
        phone_number: User's phone number (E.164 format, e.g. "+1234567890")
        alert_reason: Why the alert was triggered
        suggested_actions: List of recommended actions
        affected_tickers: Tickers causing anxiety
        anxiety_score: Peak anxiety score (0-10)

    Returns:
        dict with call_id, status, and delivery details
    """
    if not settings.vapi_api_key or settings.vapi_api_key == "your_vapi_api_key_here":
        print("[Vapi] No API key configured — logging alert to console only")
        return {
            "status": "skipped",
            "reason": "VAPI_API_KEY not configured",
            "delivery_method": "console",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # Build the crisis script for the voice assistant
    script = _build_crisis_script(alert_reason, suggested_actions, affected_tickers, anxiety_score)

    try:
        response = httpx.post(
            f"{VAPI_BASE_URL}/call/phone",
            headers={
                "Authorization": f"Bearer {settings.vapi_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "customer": {
                    "number": phone_number,
                },
                "assistantOverrides": {
                    "firstMessage": script,
                    "model": {
                        "provider": "groq",
                        "model": settings.groq_model,
                        "messages": [
                            {
                                "role": "system",
                                "content": (
                                    "You are FinVibe's crisis alert assistant. "
                                    "You are calling the user because their portfolio is at risk. "
                                    "Be calm, professional, and reassuring. "
                                    "Present the facts clearly and offer actionable suggestions. "
                                    "If the user asks questions, answer based on the alert context. "
                                    "Keep the call under 2 minutes."
                                ),
                            }
                        ],
                    },
                },
            },
            timeout=15.0,
        )

        if response.status_code in (200, 201):
            data = response.json()
            call_id = data.get("id", "unknown")
            print(f"[Vapi] Crisis call initiated: call_id={call_id}")
            return {
                "status": "initiated",
                "call_id": call_id,
                "phone_number": phone_number,
                "delivery_method": "vapi_call",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        else:
            print(f"[Vapi] Call failed: {response.status_code} — {response.text}")
            return {
                "status": "failed",
                "error": f"HTTP {response.status_code}: {response.text[:200]}",
                "delivery_method": "console",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    except httpx.TimeoutException:
        print("[Vapi] Call timed out")
        return {"status": "timeout", "delivery_method": "console"}
    except Exception as e:
        print(f"[Vapi] Error: {e}")
        return {"status": "error", "error": str(e), "delivery_method": "console"}


def get_call_status(call_id: str) -> dict:
    """Check the status of a Vapi call."""
    if not settings.vapi_api_key or settings.vapi_api_key == "your_vapi_api_key_here":
        return {"status": "not_configured"}

    try:
        response = httpx.get(
            f"{VAPI_BASE_URL}/call/{call_id}",
            headers={"Authorization": f"Bearer {settings.vapi_api_key}"},
            timeout=10.0,
        )
        if response.status_code == 200:
            return response.json()
        return {"status": "error", "code": response.status_code}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _build_crisis_script(
    alert_reason: str,
    suggested_actions: list[str],
    affected_tickers: list[str],
    anxiety_score: float,
) -> str:
    """Build the opening script for the voice call."""
    tickers_str = ", ".join(affected_tickers)
    actions_str = ". ".join(suggested_actions[:3])  # Keep it concise for voice

    script = (
        f"Hello, this is FinVibe, your AI portfolio advisor, calling with an urgent market alert. "
        f"I'm detecting elevated anxiety levels at {anxiety_score:.1f} out of 10 "
        f"affecting your positions in {tickers_str}. "
        f"Here's what's happening: {alert_reason}. "
        f"My recommended actions are: {actions_str}. "
        f"Would you like me to explain any of these recommendations in more detail?"
    )
    return script
