"""
STRATEGIST NODE
================
Third node in the graph. The "decision-making brain".

Takes:  vibe_scores + market_data + portfolio snapshot + reflection memories
Makes:  trade decisions (BUY/SELL/HOLD) + alert decisions

This node:
1. Loads the shadow portfolio from MongoDB
2. Retrieves past lessons from Qdrant (reflection_memory)
3. Retrieves user preferences from Mem0
4. Sends ALL context to Gemini → structured JSON trade decisions
5. Checks if anxiety crosses threshold → sets should_alert

Input:  state["vibe_scores"], state["market_data"], state["news_articles"]
Output: state["trade_decisions"], state["portfolio_snapshot"],
        state["reflection_memories"], state["should_alert"], state["alert_reason"]
"""
import json

from backend.schemas.agent_state import AgentState
from backend.deps import get_llm_client, get_portfolios_col, get_active_model
from backend.config import settings
from backend.services.vector_service import search_reflection_memory
from backend.services.memory_service import search_user_memory


STRATEGY_PROMPT = """You are FinVibe's Portfolio Strategist — an expert quantitative trader who combines 
sentiment analysis with position management.

You manage a $1M shadow portfolio (paper trading). Your job is to ACTIVELY TRADE to demonstrate
the system's capability. Be decisive — don't just HOLD everything.

POSITION SIZING RULES:
- Max single position: 10% of total portfolio value
- Max single trade: 5% of total portfolio value  
- Always keep at least 10% cash reserve ($100k)
- If anxiety > 7.0, reduce position sizes by 50%

DECISION FRAMEWORK:
- sentiment > 0.0 AND anxiety < 5 → BUY (bullish lean, take a position)
- sentiment < -0.3 AND anxiety > 5 → SELL if we hold, or AVOID buying
- anxiety > 7.0 → SELL all positions in panicking tickers + ALERT user
- If portfolio has NO positions and signals are not terrible, BUY selectively
- Even with neutral sentiment, it's OK to build small starter positions
- If we already hold a stock, evaluate whether to add more or reduce

IMPORTANT: 
- An empty portfolio should prompt buying — you CANNOT make money sitting in cash.
- When starting fresh, allocate 30-50% of the portfolio across promising tickers.
- Always assign a realistic prediction and confidence level.
- Be specific with share quantities based on current prices and position sizing rules.

You MUST respond with valid JSON in exactly this format:
{
  "trades": [
    {
      "ticker": "AAPL",
      "action": "BUY",
      "shares": 50,
      "rationale": {
        "signal": "Strong bullish sentiment with low anxiety",
        "prediction": "AAPL +3% in 5 days based on earnings momentum",
        "target_pct": 3.0,
        "horizon_days": 5,
        "confidence": 0.75
      }
    }
  ],
  "should_alert": false,
  "alert_reason": ""
}

If anxiety is critical, set should_alert=true with a clear alert_reason.
"""


def strategist_node(state: AgentState) -> dict:
    """
    Analyze vibes + portfolio + history → produce trade decisions.
    """
    vibe_scores = state.get("vibe_scores", [])
    market_data = state.get("market_data", {})
    user_id = state.get("user_id", "demo")
    tickers = state.get("tickers", [])

    if not vibe_scores:
        return {
            "trade_decisions": [],
            "portfolio_snapshot": {},
            "reflection_memories": [],
            "should_alert": False,
            "alert_reason": "",
            "messages": [{"role": "assistant", "content": "No vibe data — skipping strategy."}],
        }

    print(f"[Strategist] Building strategy for {len(tickers)} tickers...")

    # ── 1. Load shadow portfolio from MongoDB ──
    portfolio_snapshot = _load_portfolio()
    print(f"  [Strategist] Portfolio: ${portfolio_snapshot.get('total_value', 0):,.2f} "
          f"({len(portfolio_snapshot.get('holdings', []))} positions)")

    # ── 2. Retrieve reflection memories (past lessons) from Qdrant ──
    reflection_query = " ".join(tickers) + " trade strategy lessons"
    reflection_memories = search_reflection_memory(reflection_query, k=5)
    print(f"  [Strategist] Retrieved {len(reflection_memories)} reflection memories")

    # ── 3. Retrieve user preferences from Mem0 ──
    user_memories = search_user_memory(user_id, f"investment preferences risk tolerance {' '.join(tickers)}")
    print(f"  [Strategist] Retrieved {len(user_memories)} user memories")

    # ── 4. Build context for LLM ──
    context_block = _build_strategy_context(
        vibe_scores, market_data, portfolio_snapshot,
        reflection_memories, user_memories
    )

    # ── 5. Call Gemini for trade decisions ──
    trade_decisions, should_alert, alert_reason = _get_strategy_from_llm(context_block, tickers)

    # ── 6. Override: force alert if any anxiety > threshold ──
    max_anxiety = max((vs.get("anxiety_score", 0) for vs in vibe_scores), default=0)
    if max_anxiety >= settings.anxiety_threshold and not should_alert:
        should_alert = True
        panicking = [vs["ticker"] for vs in vibe_scores
                     if vs.get("anxiety_score", 0) >= settings.anxiety_threshold]
        alert_reason = (
            f"ANXIETY ALERT: {', '.join(panicking)} scored {max_anxiety:.1f}/10. "
            f"Threshold is {settings.anxiety_threshold}."
        )
        print(f"  [Strategist] ANXIETY OVERRIDE: {alert_reason}")

    print(f"  [Strategist] Decided {len(trade_decisions)} trades, alert={should_alert}")

    # ── Build summary message ──
    summary_lines = []
    for td in trade_decisions:
        r = td.get("rationale", {})
        summary_lines.append(
            f"- **{td['action']} {td['shares']} {td['ticker']}** "
            f"(confidence: {r.get('confidence', '?')}, "
            f"target: {r.get('target_pct', '?')}% in {r.get('horizon_days', '?')}d)"
        )

    if not trade_decisions:
        summary_lines.append("- No trades warranted. All positions HOLD.")

    if should_alert:
        summary_lines.append(f"\n⚠️ **ALERT**: {alert_reason}")

    summary = "**Strategy Complete** 🧠\n" + "\n".join(summary_lines)

    return {
        "trade_decisions": trade_decisions,
        "portfolio_snapshot": portfolio_snapshot,
        "reflection_memories": reflection_memories,
        "should_alert": should_alert,
        "alert_reason": alert_reason,
        "messages": [{"role": "assistant", "content": summary}],
    }


def _load_portfolio() -> dict:
    """Load the shadow portfolio from MongoDB."""
    try:
        doc = get_portfolios_col().find_one({
            "user_id": "finvibe-agent",
            "portfolio_type": "shadow",
        })
        if doc:
            doc.pop("_id", None)  # Remove MongoDB ObjectId (not serializable)
            return doc
        return {"holdings": [], "cash_balance": settings.shadow_portfolio_cash, "total_value": settings.shadow_portfolio_cash}
    except Exception as e:
        print(f"  [Strategist] Failed to load portfolio: {e}")
        return {"holdings": [], "cash_balance": settings.shadow_portfolio_cash, "total_value": settings.shadow_portfolio_cash}


def _build_strategy_context(
    vibe_scores: list[dict],
    market_data: dict,
    portfolio: dict,
    reflections: list[str],
    user_memories: list[str],
) -> str:
    """Assemble all context into a single text block for the LLM."""
    parts = []

    # Portfolio state
    parts.append("=== SHADOW PORTFOLIO ===")
    parts.append(f"Cash: ${portfolio.get('cash_balance', 0):,.2f}")
    parts.append(f"Total Value: ${portfolio.get('total_value', 0):,.2f}")
    holdings = portfolio.get("holdings", [])
    if holdings:
        for h in holdings:
            parts.append(
                f"  {h.get('ticker', '?')}: {h.get('shares', 0)} shares "
                f"@ ${h.get('avg_cost', 0):.2f} avg cost"
            )
    else:
        parts.append("  (No positions yet)")

    # Vibe scores
    parts.append("\n=== VIBE SCORES ===")
    for vs in vibe_scores:
        parts.append(
            f"{vs.get('ticker', '?')}: {vs.get('vibe_label', '?')} "
            f"(sentiment={vs.get('sentiment_score', 0):+.2f}, "
            f"anxiety={vs.get('anxiety_score', 0):.1f}/10) "
            f"— {vs.get('key_driver', 'N/A')}"
        )

    # Price data
    parts.append("\n=== CURRENT PRICES ===")
    for ticker, data in market_data.items():
        if "error" not in data:
            parts.append(
                f"{ticker}: ${data.get('current_price', '?')} "
                f"({data.get('change_pct', 0):+.2f}%)"
            )

    # Reflection memories
    parts.append("\n=== PAST LESSONS (from reflection memory) ===")
    if reflections:
        for i, lesson in enumerate(reflections, 1):
            parts.append(f"  [{i}] {lesson}")
    else:
        parts.append("  (No past lessons yet — first trade cycle)")

    # User preferences
    parts.append("\n=== USER PREFERENCES (from episodic memory) ===")
    if user_memories:
        for i, mem in enumerate(user_memories, 1):
            parts.append(f"  [{i}] {mem}")
    else:
        parts.append("  (No user history yet)")

    return "\n".join(parts)


def _get_strategy_from_llm(context: str, tickers: list[str]) -> tuple[list[dict], bool, str]:
    """Call Gemini to get trade decisions."""
    try:
        response = get_llm_client().chat.completions.create(
            model=get_active_model(),
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": STRATEGY_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Decide trades for tickers: {tickers}\n\n"
                        f"{context}"
                    ),
                },
            ],
        )

        raw = response.choices[0].message.content
        parsed = json.loads(raw)

        trades = parsed.get("trades", [])
        should_alert = parsed.get("should_alert", False)
        alert_reason = parsed.get("alert_reason", "")

        return trades, should_alert, alert_reason

    except Exception as e:
        print(f"  [Strategist] LLM call failed: {e}")
        return [], False, ""
