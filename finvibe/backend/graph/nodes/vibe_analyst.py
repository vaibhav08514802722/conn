"""
VIBE ANALYST NODE
==================
Second node in the graph. Takes market data + news articles from the Researcher
and uses Gemini (structured JSON output) to extract sentiment and anxiety scores.

This is the "emotional vibe check" — the core differentiator of FinVibe.

Input:  state["market_data"], state["news_articles"]
Output: state["vibe_scores"]
"""
import json

from backend.schemas.agent_state import AgentState
from backend.deps import get_llm_client, get_active_model
from backend.config import settings


VIBE_ANALYSIS_PROMPT = """You are FinVibe's Sentiment Analyst — an expert at reading the emotional "vibe" 
of financial markets from news headlines, price action, and market data.

For each ticker provided, analyze ALL available information (price data, news articles, trends) and produce 
a structured vibe assessment.

SCORING GUIDE:
- sentiment_score: -1.0 (extremely bearish) to +1.0 (extremely bullish). 0 = neutral.
- anxiety_score: 0 (minimal market stress) to 10 (full panic/crisis).
- vibe_label: One of ["euphoric", "bullish", "neutral", "anxious", "panic"]
  - euphoric: sentiment > 0.7, strong upward momentum, positive news
  - bullish: sentiment 0.3 to 0.7, generally positive
  - neutral: sentiment -0.3 to 0.3, mixed signals
  - anxious: sentiment -0.3 to -0.7, concerning news, moderate stress
  - panic: sentiment < -0.7, crisis-level anxiety, sharp drops
- key_driver: Single most important factor driving this vibe (1 sentence max).

You MUST respond with valid JSON in exactly this format:
{
  "scores": [
    {
      "ticker": "AAPL",
      "sentiment_score": 0.5,
      "anxiety_score": 3.0,
      "vibe_label": "bullish",
      "key_driver": "Strong earnings beat with raised guidance"
    }
  ]
}

Analyze EVERY ticker provided. Do not skip any.
"""


def vibe_analyst_node(state: AgentState) -> dict:
    """
    Analyze the emotional vibe of each ticker using Gemini structured output.
    Combines price data + news into a single analysis prompt.
    """
    market_data = state.get("market_data", {})
    news_articles = state.get("news_articles", [])
    tickers = state.get("tickers", [])

    if not market_data and not news_articles:
        return {
            "vibe_scores": [],
            "messages": [{"role": "assistant", "content": "No market data to analyze vibes."}],
        }

    print(f"[VibeAnalyst] Analyzing sentiment for {len(tickers)} tickers...")

    # --- Build context block for the LLM ---
    context_parts = []

    # Price data section
    context_parts.append("=== PRICE DATA ===")
    for ticker in tickers:
        data = market_data.get(ticker, {})
        if "error" in data:
            context_parts.append(f"{ticker}: No price data available ({data['error']})")
        else:
            context_parts.append(
                f"{ticker}: Price=${data.get('current_price', '?')} | "
                f"Change={data.get('change_pct', 0):+.2f}% | "
                f"Volume={data.get('volume', 0):,} | "
                f"High=${data.get('high', '?')} | Low=${data.get('low', '?')}"
            )
            # Include 5-day history for trend analysis
            hist = data.get("history_5d", [])
            if hist:
                prices = [str(h["close"]) for h in hist]
                context_parts.append(f"  5-day closes: {' → '.join(prices)}")

    # News section
    context_parts.append("\n=== NEWS ARTICLES ===")
    if news_articles:
        for i, article in enumerate(news_articles, 1):
            ticker = article.get("related_ticker") or "?"
            title = article.get("title") or "No title"
            source = article.get("source") or "Unknown"
            summary = article.get("summary") or "No summary"
            context_parts.append(
                f"[{i}] ({ticker}) "
                f"{title} — {source}\n"
                f"    Summary: {str(summary)[:200]}"
            )
    else:
        context_parts.append("No recent news articles found.")

    context_block = "\n".join(context_parts)

    # --- Call Gemini with structured JSON output ---
    try:
        response = get_llm_client().chat.completions.create(
            model=get_active_model(),
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": VIBE_ANALYSIS_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Analyze the vibe for these tickers: {tickers}\n\n"
                        f"{context_block}"
                    ),
                },
            ],
        )

        raw = response.choices[0].message.content
        parsed = json.loads(raw)
        vibe_scores = parsed.get("scores", [])

        print(f"[VibeAnalyst] Generated {len(vibe_scores)} vibe scores")
        for vs in vibe_scores:
            print(
                f"  [{vs.get('ticker')}] "
                f"sentiment={vs.get('sentiment_score', '?')} "
                f"anxiety={vs.get('anxiety_score', '?')} "
                f"vibe={vs.get('vibe_label', '?')} "
                f"— {vs.get('key_driver', '')[:60]}"
            )

    except Exception as e:
        print(f"[VibeAnalyst] LLM call failed: {e}")
        # Generate fallback neutral scores so the pipeline continues
        vibe_scores = [
            {
                "ticker": t,
                "sentiment_score": 0.0,
                "anxiety_score": 5.0,
                "vibe_label": "neutral",
                "key_driver": f"Analysis unavailable: {str(e)[:50]}",
            }
            for t in tickers
        ]

    # --- Store sentiment docs in MongoDB ---
    _persist_sentiments(vibe_scores, news_articles)

    # --- Build conversation message ---
    vibe_summary_lines = []
    for vs in vibe_scores:
        emoji = _vibe_emoji(vs.get("vibe_label", "neutral"))
        vibe_summary_lines.append(
            f"- {vs['ticker']}: {emoji} **{vs.get('vibe_label', 'neutral').upper()}** "
            f"(Sentiment: {vs.get('sentiment_score', 0):+.1f}, "
            f"Anxiety: {vs.get('anxiety_score', 5):.1f}/10) "
            f"— {vs.get('key_driver', 'N/A')}"
        )

    summary = "**Vibe Check Complete** 🎭\n" + "\n".join(vibe_summary_lines)

    return {
        "vibe_scores": vibe_scores,
        "messages": [{"role": "assistant", "content": summary}],
    }


def _persist_sentiments(vibe_scores: list[dict], news_articles: list[dict]) -> None:
    """Save sentiment records to MongoDB for historical tracking."""
    from backend.deps import get_market_sentiments_col
    from datetime import datetime, timezone

    for vs in vibe_scores:
        # Find related news summary
        related_news = [
            a.get("title", "")
            for a in news_articles
            if a.get("related_ticker") == vs.get("ticker")
        ]
        doc = {
            "ticker": vs.get("ticker"),
            "source": "news",
            "content_summary": "; ".join(related_news[:3]) if related_news else "Price data only",
            "sentiment_score": vs.get("sentiment_score", 0),
            "anxiety_score": vs.get("anxiety_score", 5),
            "vibe_label": vs.get("vibe_label", "neutral"),
            "analyzed_at": datetime.now(timezone.utc),
        }
        try:
            get_market_sentiments_col().insert_one(doc)
        except Exception as e:
            print(f"[VibeAnalyst] Failed to persist sentiment for {vs.get('ticker')}: {e}")


def _vibe_emoji(label: str) -> str:
    """Map vibe label to emoji for display."""
    return {
        "euphoric": "🚀",
        "bullish": "📈",
        "neutral": "😐",
        "anxious": "😰",
        "panic": "🔥",
    }.get(label, "❓")
