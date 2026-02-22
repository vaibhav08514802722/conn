"""
RESEARCHER NODE
================
First node in the graph. Fetches live stock prices and news articles
for every ticker in the state. Pure data fetching — no LLM calls here.

Input:  state["tickers"]
Output: state["market_data"], state["news_articles"]
"""
from backend.schemas.agent_state import AgentState
from backend.services.market_service import get_stock_price, get_latest_news


def researcher_node(state: AgentState) -> dict:
    """
    Fetch market data and news for each ticker.
    Runs yfinance + NewsAPI calls in sequence (fast enough for 5-10 tickers).
    """
    tickers = state.get("tickers", [])

    if not tickers:
        return {
            "market_data": {},
            "news_articles": [],
            "messages": [{"role": "assistant", "content": "No tickers provided to research."}],
        }

    print(f"[Researcher] Fetching data for {len(tickers)} tickers: {tickers}")

    # --- Fetch stock prices ---
    market_data = {}
    for ticker in tickers:
        price_data = get_stock_price(ticker)
        market_data[ticker] = price_data
        status = f"${price_data.get('current_price', '?')} ({price_data.get('change_pct', '?')}%)"
        print(f"  [Researcher] {ticker}: {status}")

    # --- Fetch news articles ---
    all_articles = []
    for ticker in tickers:
        articles = get_latest_news(ticker, max_articles=3)
        for article in articles:
            article["related_ticker"] = ticker
        all_articles.extend(articles)
        print(f"  [Researcher] {ticker}: fetched {len(articles)} articles")

    # --- Build a summary message for the conversation history ---
    summary_lines = []
    for t in tickers:
        d = market_data.get(t, {})
        if "error" in d:
            summary_lines.append(f"- {t}: Error - {d['error']}")
        else:
            summary_lines.append(
                f"- {t}: ${d.get('current_price', '?')} "
                f"({d.get('change_pct', 0):+.2f}%) "
                f"Vol: {d.get('volume', 0):,}"
            )

    summary = (
        f"**Market Research Complete** ({len(tickers)} tickers)\n"
        + "\n".join(summary_lines)
        + f"\n\nFetched {len(all_articles)} news articles total."
    )

    return {
        "market_data": market_data,
        "news_articles": all_articles,
        "messages": [{"role": "assistant", "content": summary}],
    }
