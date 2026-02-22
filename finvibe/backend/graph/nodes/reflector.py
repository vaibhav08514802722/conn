"""
REFLECTOR NODE
===============
Fifth node — runs AFTER the Executor. Generates lessons from each trade
and stores them in Qdrant (reflection_memory) + Mem0 (user memory).

This is the self-learning loop:
  Execute → Reflect → Store lesson → Next cycle retrieves the lesson

Why this matters:
  If the agent bought TSLA on hype and it crashed, the reflector stores
  "TSLA: bought on euphoric sentiment without checking earnings date — lost 8%".
  Next time TSLA comes up, the Strategist retrieves that lesson and adjusts.

Input:  state["execution_results"], state["trade_decisions"], state["vibe_scores"]
Output: (no state changes — side-effect only: writes to Qdrant + Mem0)
"""
from datetime import datetime

from backend.schemas.agent_state import AgentState
from backend.services.vector_service import store_reflection_lesson
from backend.services.memory_service import add_user_memory


def reflector_node(state: AgentState) -> dict:
    """
    Generate and store reflection lessons from executed trades.
    This is a side-effect node — it writes to external stores but
    doesn't modify the graph state (except adding a summary message).
    """
    execution_results = state.get("execution_results", [])
    trade_decisions = state.get("trade_decisions", [])
    vibe_scores = state.get("vibe_scores", [])
    user_id = state.get("user_id", "demo")

    executed_trades = [r for r in execution_results if r.get("status") == "EXECUTED"]

    if not executed_trades:
        return {
            "messages": [{"role": "assistant", "content": "No trades to reflect on."}],
        }

    print(f"[Reflector] Generating reflections for {len(executed_trades)} trades...")

    # Build a vibe lookup for quick access
    vibe_lookup = {vs.get("ticker"): vs for vs in vibe_scores}

    lessons_stored = 0
    lesson_summaries = []

    for result in executed_trades:
        ticker = result.get("ticker", "")
        action = result.get("action", "")
        trade_id = result.get("trade_id", "")
        shares = result.get("shares", 0)
        price = result.get("price", 0)

        # Find the matching trade decision for rationale
        rationale = {}
        for td in trade_decisions:
            if td.get("ticker") == ticker and td.get("action") == action:
                rationale = td.get("rationale", {})
                break

        # Find the vibe score for this ticker
        vibe = vibe_lookup.get(ticker, {})

        # Generate the lesson text
        lesson = _generate_lesson(ticker, action, shares, price, rationale, vibe)

        # Store in Qdrant (reflection_memory collection)
        metadata = {
            "ticker": ticker,
            "trade_id": trade_id,
            "action": action,
            "confidence": rationale.get("confidence", 0),
            "sentiment_at_trade": vibe.get("sentiment_score", 0),
            "anxiety_at_trade": vibe.get("anxiety_score", 0),
            "created_at": datetime.utcnow().isoformat(),
        }
        store_reflection_lesson(lesson, metadata)
        lessons_stored += 1
        lesson_summaries.append(f"- {ticker}: {lesson[:100]}...")

        print(f"  [Reflector] Stored lesson for {ticker}: {lesson[:80]}...")

    # Also store the conversation in Mem0 for user-level memory
    _store_conversation_memory(user_id, state)

    summary = (
        f"**Reflection Complete** 📝 ({lessons_stored} lessons stored)\n"
        + "\n".join(lesson_summaries)
    )

    return {
        "messages": [{"role": "assistant", "content": summary}],
    }


def _generate_lesson(
    ticker: str, action: str, shares: float, price: float,
    rationale: dict, vibe: dict
) -> str:
    """
    Generate a human-readable lesson from a single trade.
    These lessons are embedded and stored for future retrieval.
    """
    signal = rationale.get("signal", "unknown signal")
    prediction = rationale.get("prediction", "no prediction")
    confidence = rationale.get("confidence", 0)
    target_pct = rationale.get("target_pct", 0)
    horizon = rationale.get("horizon_days", "?")

    vibe_label = vibe.get("vibe_label", "unknown")
    sentiment = vibe.get("sentiment_score", 0)
    anxiety = vibe.get("anxiety_score", 0)

    lesson = (
        f"{action} {shares} shares of {ticker} at ${price:.2f}. "
        f"Vibe was {vibe_label} (sentiment={sentiment:+.2f}, anxiety={anxiety:.1f}/10). "
        f"Signal: {signal}. "
        f"Prediction: {prediction} (target={target_pct:+.1f}% in {horizon}d, "
        f"confidence={confidence:.0%}). "
        f"Outcome: PENDING — will be evaluated after {horizon} days."
    )

    return lesson


def _store_conversation_memory(user_id: str, state: AgentState) -> None:
    """
    Store the key parts of this analysis cycle into Mem0 as user memory.
    This helps the agent remember what it told the user and what actions it took.
    """
    tickers = state.get("tickers", [])
    vibe_scores = state.get("vibe_scores", [])
    trade_decisions = state.get("trade_decisions", [])

    # Build a compact summary for Mem0
    vibe_summary = ", ".join(
        f"{vs.get('ticker')}: {vs.get('vibe_label')} ({vs.get('sentiment_score', 0):+.1f})"
        for vs in vibe_scores
    )

    trade_summary = ", ".join(
        f"{td.get('action')} {td.get('shares', 0)} {td.get('ticker')}"
        for td in trade_decisions
    ) or "No trades"

    messages = [
        {
            "role": "user",
            "content": f"Analyzed tickers: {', '.join(tickers)}"
        },
        {
            "role": "assistant",
            "content": (
                f"Vibes: {vibe_summary}. "
                f"Trades executed: {trade_summary}."
            ),
        },
    ]

    try:
        add_user_memory(user_id, messages)
        print(f"  [Reflector] Stored conversation memory for user={user_id}")
    except Exception as e:
        print(f"  [Reflector] Failed to store user memory: {e}")
