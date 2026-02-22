"""
Market data service — wraps yfinance and NewsAPI.
Pure functions, no LLM calls. Used as tools by the Researcher node.
"""
import yfinance as yf
import requests
from datetime import datetime, timezone

from backend.config import settings


# ─────────────────────────── Stock Prices ───────────────────────────────────

def get_stock_price(ticker: str) -> dict:
    """
    Fetch recent price data for a single ticker via yfinance.
    Returns a dict with current price, change %, volume, and 5-day history.
    """
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="5d")

        if hist.empty:
            return {"ticker": ticker, "error": f"No data found for {ticker}"}

        latest = hist.iloc[-1]
        prev_close = hist.iloc[-2]["Close"] if len(hist) >= 2 else latest["Close"]
        change_pct = ((latest["Close"] - prev_close) / prev_close) * 100

        # Build 5-day price history for context
        history = []
        for date, row in hist.iterrows():
            history.append({
                "date": date.strftime("%Y-%m-%d"),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })

        return {
            "ticker": ticker,
            "current_price": round(float(latest["Close"]), 2),
            "change_pct": round(float(change_pct), 2),
            "volume": int(latest["Volume"]),
            "high": round(float(latest["High"]), 2),
            "low": round(float(latest["Low"]), 2),
            "history_5d": history,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}


def get_multiple_stock_prices(tickers: list[str]) -> dict:
    """Fetch prices for a list of tickers. Returns {ticker: price_data}."""
    result = {}
    for t in tickers:
        result[t] = get_stock_price(t)
    return result


# ─────────────────────────── News Articles ──────────────────────────────────

def get_latest_news(ticker: str, max_articles: int = 5) -> list[dict]:
    """
    Fetch latest news for a ticker via NewsAPI.
    Falls back to yfinance news if NewsAPI key is not set.
    """
    articles = []

    # Try NewsAPI first (if key available)
    if settings.news_api_key:
        articles = _fetch_from_newsapi(ticker, max_articles)

    # Fallback: yfinance built-in news
    if not articles:
        articles = _fetch_from_yfinance(ticker, max_articles)

    return articles


def _fetch_from_newsapi(ticker: str, max_articles: int) -> list[dict]:
    """Fetch from NewsAPI.org /v2/everything endpoint."""
    try:
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": ticker,
            "sortBy": "publishedAt",
            "pageSize": max_articles,
            "language": "en",
            "apiKey": settings.news_api_key,
        }
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code != 200:
            return []

        data = resp.json()
        return [
            {
                "title": a.get("title", ""),
                "summary": a.get("description", ""),
                "url": a.get("url", ""),
                "source": a.get("source", {}).get("name", "Unknown"),
                "published_at": a.get("publishedAt", ""),
            }
            for a in data.get("articles", [])[:max_articles]
        ]
    except Exception:
        return []


def _fetch_from_yfinance(ticker: str, max_articles: int) -> list[dict]:
    """Fallback: use yfinance's built-in news feed."""
    try:
        stock = yf.Ticker(ticker)
        news = stock.news or []
        return [
            {
                "title": n.get("title", ""),
                "summary": n.get("summary", n.get("title", "")),
                "url": n.get("link", ""),
                "source": n.get("publisher", "Yahoo Finance"),
                "published_at": datetime.fromtimestamp(
                    n.get("providerPublishTime", 0)
                ).isoformat() if n.get("providerPublishTime") else "",
            }
            for n in news[:max_articles]
        ]
    except Exception:
        return []
