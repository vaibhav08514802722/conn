"""
Market routes — direct access to stock prices, news, vibe data, and evaluation triggers.
Useful for the frontend dashboard.
"""
from fastapi import APIRouter, Query

from backend.services.market_service import get_stock_price, get_latest_news

router = APIRouter(prefix="/api/market", tags=["Market"])


@router.get("/quote")
def get_quote(ticker: str = Query(..., description="Stock ticker symbol, e.g. AAPL")):
    """Get current stock price and 5-day history for a single ticker."""
    ticker = ticker.strip().upper()
    data = get_stock_price(ticker)
    return data


@router.get("/news")
def get_news(
    ticker: str = Query(..., description="Stock ticker to fetch news for"),
    limit: int = Query(5, ge=1, le=20, description="Max articles to return"),
):
    """Get latest news articles for a ticker."""
    ticker = ticker.strip().upper()
    articles = get_latest_news(ticker, max_articles=limit)
    return {"ticker": ticker, "articles": articles, "count": len(articles)}


@router.post("/evaluate")
def trigger_evaluation():
    """Manually trigger evaluation of pending trade predictions."""
    from backend.jobs.evaluator import evaluate_pending_trades
    result = evaluate_pending_trades()
    return {"status": "ok", **result}


@router.get("/vibe/{ticker}")
def get_market_vibe(ticker: str, limit: int = Query(5, ge=1, le=50)):
    """
    Get the latest sentiment/vibe data for a ticker from MongoDB.
    Returns historical MarketSentiment documents.
    """
    ticker = ticker.strip().upper()
    try:
        from backend.deps import get_market_sentiments_col
        docs = list(
            get_market_sentiments_col()
            .find({"ticker": ticker}, {"_id": 0})
            .sort("analyzed_at", -1)
            .limit(limit)
        )
        # Compute aggregate if we have data
        if docs:
            avg_sentiment = sum(d.get("sentiment_score", 0) for d in docs) / len(docs)
            avg_anxiety = sum(d.get("anxiety_score", 0) for d in docs) / len(docs)
            latest_vibe = docs[0].get("vibe_label", "neutral")
        else:
            avg_sentiment = 0
            avg_anxiety = 0
            latest_vibe = "unknown"

        return {
            "ticker": ticker,
            "latest_vibe": latest_vibe,
            "avg_sentiment": round(avg_sentiment, 3),
            "avg_anxiety": round(avg_anxiety, 2),
            "history": docs,
            "count": len(docs),
        }
    except Exception as e:
        return {"ticker": ticker, "error": str(e), "history": [], "count": 0}


@router.get("/vibe")
def get_all_vibes():
    """Get the latest vibe data aggregated across all tracked tickers."""
    try:
        from backend.deps import get_market_sentiments_col
        pipeline = [
            {"$sort": {"analyzed_at": -1}},
            {"$group": {
                "_id": "$ticker",
                "latest_sentiment": {"$first": "$sentiment_score"},
                "latest_anxiety": {"$first": "$anxiety_score"},
                "latest_vibe": {"$first": "$vibe_label"},
                "latest_driver": {"$first": "$content_summary"},
                "analyzed_at": {"$first": "$analyzed_at"},
                "data_points": {"$sum": 1},
            }},
            {"$sort": {"latest_anxiety": -1}},  # Most anxious first
        ]
        results = list(get_market_sentiments_col().aggregate(pipeline))
        for r in results:
            r["ticker"] = r.pop("_id")

        # Compute aggregate anxiety gauge (0-10)
        if results:
            aggregate_anxiety = sum(r["latest_anxiety"] for r in results) / len(results)
        else:
            aggregate_anxiety = 0

        return {
            "aggregate_anxiety": round(aggregate_anxiety, 2),
            "tickers": results,
            "count": len(results),
        }
    except Exception as e:
        return {"error": str(e), "tickers": [], "count": 0}

