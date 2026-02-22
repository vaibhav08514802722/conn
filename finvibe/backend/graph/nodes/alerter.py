"""
ALERTER NODE
=============
Conditional node — only runs when should_alert=True.
Sends an emergency notification when market anxiety crosses the threshold
and the user's portfolio is at risk.

Day 3: Integrates Vapi voice call to phone the user during crises.

Input:  state["should_alert"], state["alert_reason"], state["vibe_scores"], state["user_id"]
Output: state["alert_sent"]
"""
from datetime import datetime, timezone

from backend.schemas.agent_state import AgentState
from backend.deps import get_db
from backend.config import settings
from backend.services.vapi_service import trigger_crisis_call


def alerter_node(state: AgentState) -> dict:
    """
    Send an anxiety alert to the user.
    Currently: logs to MongoDB + console.
    Future: triggers Vapi voice call.
    """
    should_alert = state.get("should_alert", False)
    alert_reason = state.get("alert_reason", "")
    vibe_scores = state.get("vibe_scores", [])
    user_id = state.get("user_id", "demo")
    market_data = state.get("market_data", {})

    if not should_alert:
        return {
            "alert_sent": False,
            "messages": [{"role": "assistant", "content": "No alert needed."}],
        }

    print(f"\n{'!'*60}")
    print(f"[Alerter] ⚠️  ANXIETY ALERT for user={user_id}")
    print(f"[Alerter] Reason: {alert_reason}")
    print(f"{'!'*60}")

    # Identify affected tickers (anxiety above threshold)
    affected_tickers = []
    max_anxiety = 0
    for vs in vibe_scores:
        anxiety = vs.get("anxiety_score", 0)
        if anxiety >= settings.anxiety_threshold:
            affected_tickers.append(vs.get("ticker", ""))
        max_anxiety = max(max_anxiety, anxiety)

    # Estimate portfolio impact
    portfolio_impact_pct = _estimate_portfolio_impact(affected_tickers, market_data)

    # Generate suggested actions
    suggested_actions = _generate_suggestions(affected_tickers, vibe_scores, market_data)

    # Build the alert document
    alert_doc = {
        "user_id": user_id,
        "affected_tickers": affected_tickers,
        "max_anxiety_score": max_anxiety,
        "portfolio_impact_pct": portfolio_impact_pct,
        "alert_reason": alert_reason,
        "suggested_actions": suggested_actions,
        "triggered_at": datetime.now(timezone.utc),
        "delivery_method": "console",
        "call_details": None,
        "acknowledged": False,
    }

    # Persist alert to MongoDB
    _save_alert(alert_doc)

    # ── Trigger Vapi voice call ──
    call_result = _trigger_voice_alert(user_id, alert_reason, suggested_actions,
                                        affected_tickers, max_anxiety)
    if call_result.get("status") == "initiated":
        # Update delivery method in MongoDB
        try:
            alerts_col = get_db()["alerts"]
            alerts_col.update_one(
                {"user_id": user_id, "triggered_at": alert_doc["triggered_at"]},
                {"$set": {
                    "delivery_method": "vapi_call",
                    "call_details": call_result,
                }},
            )
        except Exception:
            pass

    print(f"[Alerter] Alert saved. Affected: {affected_tickers}")
    print(f"[Alerter] Impact: {portfolio_impact_pct:.1f}%")
    print(f"[Alerter] Suggestions: {suggested_actions}")

    # Build user-facing message
    suggestions_text = "\n".join(f"  {i}. {s}" for i, s in enumerate(suggested_actions, 1))
    summary = (
        f"**⚠️ ANXIETY ALERT** 🚨\n\n"
        f"**Reason:** {alert_reason}\n"
        f"**Affected Tickers:** {', '.join(affected_tickers)}\n"
        f"**Max Anxiety:** {max_anxiety:.1f}/10\n"
        f"**Est. Portfolio Impact:** {portfolio_impact_pct:+.1f}%\n\n"
        f"**Suggested Actions:**\n{suggestions_text}"
    )

    return {
        "alert_sent": True,
        "messages": [{"role": "assistant", "content": summary}],
    }


def _estimate_portfolio_impact(affected_tickers: list[str], market_data: dict) -> float:
    """
    Rough estimate of how much the user's portfolio might drop
    based on the change_pct of affected tickers.
    """
    if not affected_tickers:
        return 0.0

    total_impact = 0.0
    for ticker in affected_tickers:
        data = market_data.get(ticker, {})
        change = data.get("change_pct", 0)
        # Assume equal weight per ticker as a rough estimate
        total_impact += change

    # Average impact across affected tickers
    avg_impact = total_impact / len(affected_tickers) if affected_tickers else 0
    return round(avg_impact, 2)


def _generate_suggestions(
    affected_tickers: list[str],
    vibe_scores: list[dict],
    market_data: dict,
) -> list[str]:
    """Generate actionable suggestions for the user."""
    suggestions = []

    for ticker in affected_tickers:
        # Find vibe for this ticker
        vibe = next((vs for vs in vibe_scores if vs.get("ticker") == ticker), {})
        anxiety = vibe.get("anxiety_score", 0)
        label = vibe.get("vibe_label", "unknown")
        driver = vibe.get("key_driver", "")

        data = market_data.get(ticker, {})
        price = data.get("current_price", 0)
        change = data.get("change_pct", 0)

        if anxiety >= 8.0:  # Extreme panic
            suggestions.append(
                f"URGENT: Consider selling {ticker} (${price:.2f}, {change:+.1f}%). "
                f"Vibe: {label}. Reason: {driver}"
            )
        elif anxiety >= settings.anxiety_threshold:
            suggestions.append(
                f"CAUTION: Reduce {ticker} position (${price:.2f}, {change:+.1f}%). "
                f"Set stop-loss. Reason: {driver}"
            )

    suggestions.append("Review your risk tolerance and rebalance if needed.")
    suggestions.append("Don't panic-sell everything — consider a staged exit over 2-3 days.")

    return suggestions


def _save_alert(alert_doc: dict) -> None:
    """Persist the alert to MongoDB alerts collection."""
    try:
        alerts_col = get_db()["alerts"]
        alerts_col.insert_one(alert_doc)
        print(f"  [Alerter] Alert persisted to MongoDB")
    except Exception as e:
        print(f"  [Alerter] Failed to save alert: {e}")


def _trigger_voice_alert(
    user_id: str,
    alert_reason: str,
    suggested_actions: list[str],
    affected_tickers: list[str],
    anxiety_score: float,
) -> dict:
    """
    Trigger a Vapi voice call to the user.
    Looks up the user's phone number from MongoDB users collection.
    Falls back gracefully if Vapi is not configured.
    """
    # Look up phone number from MongoDB (or use a default for demo)
    phone_number = _get_user_phone(user_id)
    if not phone_number:
        print(f"  [Alerter] No phone number for user={user_id}, skipping voice call")
        return {"status": "skipped", "reason": "no_phone_number"}

    print(f"  [Alerter] Triggering Vapi call to {phone_number}...")
    result = trigger_crisis_call(
        phone_number=phone_number,
        alert_reason=alert_reason,
        suggested_actions=suggested_actions,
        affected_tickers=affected_tickers,
        anxiety_score=anxiety_score,
    )
    print(f"  [Alerter] Vapi result: {result.get('status', 'unknown')}")
    return result


def _get_user_phone(user_id: str) -> str | None:
    """Look up user's phone number from MongoDB users collection."""
    try:
        users_col = get_db()["users"]
        user = users_col.find_one({"user_id": user_id})
        if user:
            return user.get("phone_number")
    except Exception:
        pass
    return None
