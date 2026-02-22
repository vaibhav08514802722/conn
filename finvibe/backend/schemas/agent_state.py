"""
LangGraph AgentState — the single TypedDict that flows through every node.
"""
from typing import Annotated, Optional
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """
    Shared state passed between all LangGraph nodes.

    Fields are populated incrementally as the graph executes:
      START → Researcher (fills market_data, news_articles)
            → Vibe Analyst (fills vibe_scores)
            → Strategist  (fills trade_decisions, should_alert, reflection_memories)
            → Executor     (fills execution_results)
            → Alerter      (fills alert_sent)
    """
    # --- Conversation / LangGraph plumbing ---
    messages: Annotated[list, add_messages]

    # --- Input context ---
    user_id: str
    tickers: list[str]

    # --- Researcher output ---
    market_data: dict          # {ticker: {price, change_pct, volume, high, low, ...}}
    news_articles: list[dict]  # [{title, summary, url, source, published_at}]

    # --- Vibe Analyst output ---
    vibe_scores: list[dict]    # [{ticker, sentiment_score, anxiety_score, vibe_label, key_driver}]

    # --- Strategist output ---
    portfolio_snapshot: dict            # current shadow portfolio state
    reflection_memories: list[str]      # retrieved lessons from Qdrant
    trade_decisions: list[dict]         # [{ticker, action, shares, rationale: {...}}]
    should_alert: bool                  # whether to trigger Vapi call
    alert_reason: str                   # human-readable crisis summary

    # --- Executor output ---
    execution_results: list[dict]       # [{trade_id, status, message}]

    # --- Alerter output ---
    alert_sent: bool
