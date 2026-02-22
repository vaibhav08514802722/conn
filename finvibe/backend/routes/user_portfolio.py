"""
User Portfolio & AI Portfolio routes.

- User Portfolio: manual add/remove of any global stock, SIP tracking
- AI Portfolio: live shadow portfolio with $1M, real-time P&L + predictions
"""
import json
import re
from fastapi import APIRouter, HTTPException, Header, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone

from backend.services.auth_service import decode_token
from backend.services.market_service import get_stock_price
from backend.services.portfolio_service import (
    get_portfolio,
    create_portfolio,
    get_trade_logs,
    get_portfolio_value_history,
)
from backend.deps import get_db, get_market_sentiments_col, get_llm_client, get_active_model
from backend.config import settings

router = APIRouter(prefix="/api/portfolios", tags=["Portfolios"])


# ──────────────── Helpers ───────────────────────────────────────────────────

def _get_user_id(authorization: Optional[str]) -> str:
    """Extract user_id from Bearer token or raise 401."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Not authenticated")
    data = decode_token(authorization.split(" ", 1)[1])
    if not data:
        raise HTTPException(401, "Invalid or expired token")
    return data["sub"]


def _user_col():
    return get_db()["user_portfolios"]


# ──────────────── Request Models ────────────────────────────────────────────

class AddHoldingReq(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=20)
    shares: float = Field(..., gt=0)
    avg_cost: float = Field(..., gt=0)
    investment_type: str = Field(default="stock", description="stock | sip | etf | mf | crypto")
    sip_amount: Optional[float] = Field(None, description="Monthly SIP amount if applicable")
    notes: Optional[str] = None


class RemoveHoldingReq(BaseModel):
    ticker: str


# ──────────────── AI Prediction Helper ──────────────────────────────────────

def _get_ticker_vibe(ticker: str) -> dict:
    """Get latest vibe/sentiment data for a ticker from MongoDB."""
    try:
        doc = get_market_sentiments_col().find_one(
            {"ticker": ticker.upper()},
            {"_id": 0},
            sort=[("analyzed_at", -1)],
        )
        return doc or {}
    except Exception:
        return {}


def _derive_vibe_from_price(price_data: dict) -> dict:
    """Fallback vibe when no stored sentiment exists for ticker."""
    change = float(price_data.get("change_pct", 0) or 0)
    if change >= 2:
        return {"vibe_label": "bullish", "anxiety_score": 3.0, "sentiment_score": 0.55}
    if change >= 0.5:
        return {"vibe_label": "cautious bullish", "anxiety_score": 4.5, "sentiment_score": 0.25}
    if change <= -2:
        return {"vibe_label": "panic", "anxiety_score": 8.2, "sentiment_score": -0.65}
    if change <= -0.5:
        return {"vibe_label": "bearish", "anxiety_score": 6.8, "sentiment_score": -0.3}
    return {"vibe_label": "neutral", "anxiety_score": 5.0, "sentiment_score": 0.0}


def _extract_json(raw: str) -> dict:
    """Best-effort JSON extraction from model output."""
    text = (raw or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        pass
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        try:
            return json.loads(text)
        except Exception:
            pass
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            return {}
    return {}


def _normalize_prediction(pred: dict, current_price: float) -> dict:
    """Normalize model output to a stable schema for UI + API consumers."""
    signal = str(pred.get("signal", "HOLD")).upper().strip()
    if signal not in {"BUY", "HOLD", "SELL"}:
        signal = "HOLD"

    confidence = pred.get("confidence", 0)
    try:
        confidence = max(0.0, min(1.0, float(confidence)))
    except Exception:
        confidence = 0.0

    horizon_days = pred.get("horizon_days", 7)
    try:
        horizon_days = int(horizon_days)
    except Exception:
        horizon_days = 7
    horizon_days = max(1, min(30, horizon_days))

    target_price = pred.get("target_price", 0)
    try:
        target_price = float(target_price)
    except Exception:
        target_price = 0.0

    target_pct = pred.get("target_pct", None)
    if target_pct is not None:
        try:
            target_pct = float(target_pct)
        except Exception:
            target_pct = None

    if target_pct is None and current_price > 0 and target_price > 0:
        target_pct = ((target_price - current_price) / current_price) * 100

    if target_pct is None:
        target_pct = 0.0

    # If target_price missing, derive from target_pct
    if (target_price <= 0) and current_price > 0:
        target_price = current_price * (1 + (target_pct / 100))

    return {
        "signal": signal,
        "prediction": str(pred.get("prediction", "No clear prediction available"))[:220],
        "reason": str(pred.get("reason", "Insufficient supporting evidence"))[:220],
        "target_price": round(float(target_price), 2) if current_price > 0 else 0,
        "target_pct": round(float(target_pct), 2),
        "horizon_days": horizon_days,
        "confidence": round(confidence, 3),
    }


def _generate_ai_prediction(ticker: str, price_data: dict, vibe: dict) -> dict:
    """
    Use active LLM to produce a concise prediction for a stock.
    Returns {signal, prediction, confidence} in plain language.
    """
    try:
        client = get_llm_client()
        price = price_data.get("current_price", 0)
        change = price_data.get("change_pct", 0)
        high = price_data.get("high", 0)
        low = price_data.get("low", 0)
        volume = price_data.get("volume", 0)
        vibe_label = vibe.get("vibe_label", "unknown")
        anxiety = vibe.get("anxiety_score", 5)
        sentiment = vibe.get("sentiment_score", 0)
        driver = vibe.get("content_summary", "")
        history_5d = price_data.get("history_5d", [])
        prices_str = ", ".join(
            [f"{h['date']}: ${h['close']}" for h in history_5d[-5:]]
        ) if history_5d else "N/A"

        prompt = f"""You are a concise but sharp stock analyst.

Given this data for {ticker}:
- Current Price: ${price} ({'+' if change >= 0 else ''}{change}% today)
- Day Range: ${low} - ${high}
- Volume: {volume:,}
- 5-Day Prices: {prices_str}
- Market Vibe: {vibe_label} (anxiety: {anxiety}/10, sentiment: {sentiment})
- Key News: {driver[:220] if driver else 'No recent news'}

Respond in EXACTLY this JSON format (no markdown, no extra text):
{{
    "signal": "BUY",
    "prediction": "One clear sentence with directional view",
    "reason": "One clear sentence explaining why",
    "target_price": 123.45,
    "target_pct": 6.5,
    "horizon_days": 7,
    "confidence": 0.78
}}

Rules:
- signal must be BUY/HOLD/SELL
- target_pct is expected % move from current price (can be negative)
- horizon_days must be 1..30
- confidence must be 0..1"""

        response = client.chat.completions.create(
            model=get_active_model(),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=260,
        )
        raw = response.choices[0].message.content.strip()
        parsed = _extract_json(raw)
        return _normalize_prediction(parsed, price)
    except Exception as e:
        fallback = {
            "signal": "HOLD",
            "prediction": "Insufficient data for prediction",
            "reason": "Could not analyze this stock",
            "target_price": price_data.get("current_price", 0),
            "target_pct": 0,
            "horizon_days": 7,
            "confidence": 0,
        }
        return _normalize_prediction(fallback, price_data.get("current_price", 0))


# ──────────────── Stock Search ──────────────────────────────────────────────

# ──────────────── Stock Search ──────────────────────────────────────────────

@router.get("/predict/{ticker}")
def get_stock_prediction(ticker: str):
    """Get AI prediction for a single ticker in simple terms."""
    price_data = get_stock_price(ticker.upper().strip())
    vibe = _get_ticker_vibe(ticker.upper().strip()) or _derive_vibe_from_price(price_data)
    prediction = _generate_ai_prediction(ticker.upper().strip(), price_data, vibe)
    return {
        "status": "ok",
        "ticker": ticker.upper().strip(),
        "price": price_data.get("current_price", 0),
        "change_pct": price_data.get("change_pct", 0),
        "vibe": {
            "label": vibe.get("vibe_label", "unknown"),
            "anxiety": vibe.get("anxiety_score", 5),
            "sentiment": vibe.get("sentiment_score", 0),
        },
        "prediction": prediction,
    }


@router.post("/predict")
def get_bulk_predictions(tickers: List[str]):
    """Get AI predictions for multiple tickers."""
    results = {}
    for t in tickers[:10]:  # Max 10
        t = t.upper().strip()
        price_data = get_stock_price(t)
        vibe = _get_ticker_vibe(t) or _derive_vibe_from_price(price_data)
        prediction = _generate_ai_prediction(t, price_data, vibe)
        results[t] = {
            "price": price_data.get("current_price", 0),
            "change_pct": price_data.get("change_pct", 0),
            "high": price_data.get("high", 0),
            "low": price_data.get("low", 0),
            "volume": price_data.get("volume", 0),
            "vibe_label": vibe.get("vibe_label", "unknown"),
            "anxiety": vibe.get("anxiety_score", 5),
            "prediction": prediction,
        }
    return {"status": "ok", "predictions": results}


@router.get("/search")
def search_stock(q: str = Query(..., min_length=1, max_length=30)):
    """Search for a stock/ETF globally using yfinance."""
    import yfinance as yf
    try:
        stock = yf.Ticker(q.upper().strip())
        info = stock.info or {}
        if not info.get("regularMarketPrice") and not info.get("currentPrice"):
            # Try as-is — might be an Indian (.NS, .BO) or international ticker
            hist = stock.history(period="1d")
            if hist.empty:
                return {"status": "ok", "results": []}
            price = round(float(hist.iloc[-1]["Close"]), 2)
        else:
            price = info.get("regularMarketPrice") or info.get("currentPrice") or 0

        return {
            "status": "ok",
            "results": [{
                "ticker": q.upper().strip(),
                "name": info.get("longName") or info.get("shortName") or q.upper(),
                "exchange": info.get("exchange", ""),
                "currency": info.get("currency", "USD"),
                "sector": info.get("sector", ""),
                "industry": info.get("industry", ""),
                "price": round(float(price), 2),
                "market_cap": info.get("marketCap"),
                "pe_ratio": info.get("trailingPE"),
                "day_high": info.get("dayHigh"),
                "day_low": info.get("dayLow"),
                "52w_high": info.get("fiftyTwoWeekHigh"),
                "52w_low": info.get("fiftyTwoWeekLow"),
            }],
        }
    except Exception as e:
        return {"status": "ok", "results": [], "error": str(e)}


# ────────────── USER PORTFOLIO: CRUD ────────────────────────────────────────

@router.get("/user")
def get_user_portfolio(authorization: Optional[str] = Header(None)):
    """Get the authenticated user's personal portfolio."""
    uid = _get_user_id(authorization)
    doc = _user_col().find_one({"user_id": uid})
    if not doc:
        # Auto-create empty portfolio
        doc = {
            "user_id": uid,
            "holdings": [],
            "total_invested": 0,
            "current_value": 0,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        _user_col().insert_one(doc)
    doc["_id"] = str(doc["_id"])
    return {"status": "ok", "portfolio": doc}


@router.post("/user/add")
def add_user_holding(req: AddHoldingReq, authorization: Optional[str] = Header(None)):
    """Add or update a holding in the user's portfolio."""
    uid = _get_user_id(authorization)
    col = _user_col()

    doc = col.find_one({"user_id": uid})
    if not doc:
        doc = {
            "user_id": uid,
            "holdings": [],
            "total_invested": 0,
            "current_value": 0,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        col.insert_one(doc)

    # Fetch live price
    price_data = get_stock_price(req.ticker.upper().strip())
    live_price = price_data.get("current_price", req.avg_cost)

    holdings = doc.get("holdings", [])
    found = False
    for h in holdings:
        if h["ticker"] == req.ticker.upper().strip():
            # Weighted avg cost
            old_total = h["shares"] * h["avg_cost"]
            new_total = req.shares * req.avg_cost
            combined_shares = h["shares"] + req.shares
            h["shares"] = combined_shares
            h["avg_cost"] = round((old_total + new_total) / combined_shares, 2)
            h["current_price"] = live_price
            h["investment_type"] = req.investment_type
            h["updated_at"] = datetime.now(timezone.utc).isoformat()
            if req.sip_amount:
                h["sip_amount"] = req.sip_amount
            if req.notes:
                h["notes"] = req.notes
            found = True
            break

    if not found:
        holdings.append({
            "ticker": req.ticker.upper().strip(),
            "shares": req.shares,
            "avg_cost": req.avg_cost,
            "current_price": live_price,
            "investment_type": req.investment_type,
            "sip_amount": req.sip_amount,
            "notes": req.notes or "",
            "added_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })

    # Recalculate totals
    total_invested = sum(h["shares"] * h["avg_cost"] for h in holdings)
    current_value = sum(h["shares"] * h.get("current_price", h["avg_cost"]) for h in holdings)

    col.update_one(
        {"user_id": uid},
        {"$set": {
            "holdings": holdings,
            "total_invested": round(total_invested, 2),
            "current_value": round(current_value, 2),
            "updated_at": datetime.now(timezone.utc),
        }},
    )
    return {
        "status": "ok",
        "message": f"Added {req.ticker.upper()} to portfolio",
        "holding_count": len(holdings),
        "total_invested": round(total_invested, 2),
        "current_value": round(current_value, 2),
    }


@router.delete("/user/remove")
def remove_user_holding(req: RemoveHoldingReq, authorization: Optional[str] = Header(None)):
    """Remove a holding from user portfolio."""
    uid = _get_user_id(authorization)
    col = _user_col()
    doc = col.find_one({"user_id": uid})
    if not doc:
        raise HTTPException(404, "Portfolio not found")

    holdings = [h for h in doc.get("holdings", []) if h["ticker"] != req.ticker.upper().strip()]
    total_invested = sum(h["shares"] * h["avg_cost"] for h in holdings)
    current_value = sum(h["shares"] * h.get("current_price", h["avg_cost"]) for h in holdings)

    col.update_one(
        {"user_id": uid},
        {"$set": {
            "holdings": holdings,
            "total_invested": round(total_invested, 2),
            "current_value": round(current_value, 2),
            "updated_at": datetime.now(timezone.utc),
        }},
    )
    return {"status": "ok", "message": f"Removed {req.ticker.upper()}"}


@router.post("/user/refresh")
def refresh_user_prices(authorization: Optional[str] = Header(None)):
    """Refresh all live prices + AI predictions for user portfolio holdings."""
    uid = _get_user_id(authorization)
    col = _user_col()
    doc = col.find_one({"user_id": uid})
    if not doc:
        raise HTTPException(404, "Portfolio not found")

    holdings = doc.get("holdings", [])
    for h in holdings:
        price_data = get_stock_price(h["ticker"])
        h["current_price"] = price_data.get("current_price", h.get("current_price", h["avg_cost"]))
        h["change_pct"] = price_data.get("change_pct", 0)
        h["day_high"] = price_data.get("high", 0)
        h["day_low"] = price_data.get("low", 0)
        h["volume"] = price_data.get("volume", 0)
        # Get vibe data
        vibe = _get_ticker_vibe(h["ticker"]) or _derive_vibe_from_price(price_data)
        h["vibe_label"] = vibe.get("vibe_label", "unknown")
        h["anxiety"] = vibe.get("anxiety_score", 5)
        # AI prediction
        prediction = _generate_ai_prediction(h["ticker"], price_data, vibe)
        h["ai_signal"] = prediction.get("signal", "HOLD")
        h["ai_prediction"] = prediction.get("prediction", "")
        h["ai_reason"] = prediction.get("reason", "")
        h["ai_target"] = prediction.get("target_price", 0)
        h["ai_target_pct"] = prediction.get("target_pct", 0)
        h["ai_horizon_days"] = prediction.get("horizon_days", 7)
        h["ai_confidence"] = prediction.get("confidence", 0)

    total_invested = sum(h["shares"] * h["avg_cost"] for h in holdings)
    current_value = sum(h["shares"] * h.get("current_price", h["avg_cost"]) for h in holdings)

    col.update_one(
        {"user_id": uid},
        {"$set": {
            "holdings": holdings,
            "total_invested": round(total_invested, 2),
            "current_value": round(current_value, 2),
            "updated_at": datetime.now(timezone.utc),
        }},
    )

    doc = col.find_one({"user_id": uid})
    doc["_id"] = str(doc["_id"])
    return {"status": "ok", "portfolio": doc}


# ────────────── AI PORTFOLIO: Live Shadow Portfolio ─────────────────────────

@router.get("/ai")
def get_ai_portfolio():
    """
    Get the live AI-managed shadow portfolio.
    Always returns the finvibe-agent shadow portfolio with $1M capital —
    includes live P&L, per-holding profit/loss, and AI predictions.
    """
    portfolio = get_portfolio("finvibe-agent", "shadow")
    if not portfolio:
        # Auto-create if not exists
        portfolio = create_portfolio("finvibe-agent", "shadow", settings.shadow_portfolio_cash)

    holdings = portfolio.get("holdings", [])

    # Enrich each holding with live prices, P&L, and AI predictions
    enriched = []
    for h in holdings:
        ticker = h.get("ticker", "")
        price_data = get_stock_price(ticker)
        live_price = price_data.get("current_price", h.get("current_price", h.get("avg_cost", 0)))
        avg_cost = h.get("avg_cost", 0)
        shares = h.get("shares", 0)
        market_value = shares * live_price
        cost_basis = shares * avg_cost
        pnl = market_value - cost_basis
        pnl_pct = ((live_price - avg_cost) / avg_cost * 100) if avg_cost > 0 else 0

        # Get vibe
        vibe = _get_ticker_vibe(ticker) or _derive_vibe_from_price(price_data)
        # AI prediction
        prediction = _generate_ai_prediction(ticker, price_data, vibe)

        enriched.append({
            "ticker": ticker,
            "shares": shares,
            "avg_cost": round(avg_cost, 2),
            "current_price": round(live_price, 2),
            "market_value": round(market_value, 2),
            "cost_basis": round(cost_basis, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "day_change_pct": price_data.get("change_pct", 0),
            "day_high": price_data.get("high", 0),
            "day_low": price_data.get("low", 0),
            "volume": price_data.get("volume", 0),
            "vibe_label": vibe.get("vibe_label", "unknown"),
            "anxiety": vibe.get("anxiety_score", 5),
            "ai_signal": prediction.get("signal", "HOLD"),
            "ai_prediction": prediction.get("prediction", ""),
            "ai_reason": prediction.get("reason", ""),
            "ai_target": prediction.get("target_price", 0),
            "ai_target_pct": prediction.get("target_pct", 0),
            "ai_horizon_days": prediction.get("horizon_days", 7),
            "ai_confidence": prediction.get("confidence", 0),
        })

    total_invested = sum(e["cost_basis"] for e in enriched)
    current_value = sum(e["market_value"] for e in enriched)
    cash = portfolio.get("cash_balance", settings.shadow_portfolio_cash)
    total_portfolio_value = current_value + cash
    total_pnl = total_portfolio_value - settings.shadow_portfolio_cash
    total_pnl_pct = (total_pnl / settings.shadow_portfolio_cash) * 100

    return {
        "status": "ok",
        "portfolio": {
            "initial_capital": settings.shadow_portfolio_cash,
            "cash_balance": round(cash, 2),
            "invested_value": round(total_invested, 2),
            "current_value": round(current_value, 2),
            "total_portfolio_value": round(total_portfolio_value, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_pct": round(total_pnl_pct, 2),
            "holdings_count": len(enriched),
            "holdings": enriched,
            "updated_at": portfolio.get("updated_at", datetime.now(timezone.utc)).isoformat()
                          if hasattr(portfolio.get("updated_at", ""), "isoformat")
                          else str(portfolio.get("updated_at", "")),
        },
    }


@router.get("/ai/trades")
def get_ai_trade_history(limit: int = Query(50, ge=1, le=200)):
    """Get the AI agent's trade history with outcomes."""
    trades = get_trade_logs("shadow", limit)
    # Enrich with current price for live P&L
    for t in trades:
        ticker = t.get("ticker", "")
        price_data = get_stock_price(ticker)
        t["current_price"] = price_data.get("current_price", t.get("price_at_execution", 0))
        exec_price = t.get("price_at_execution", 0)
        if exec_price > 0:
            t["live_pnl_pct"] = round(
                ((t["current_price"] - exec_price) / exec_price) * 100, 2
            )
        else:
            t["live_pnl_pct"] = 0
    return {"status": "ok", "trades": trades, "count": len(trades)}


@router.get("/ai/history")
def get_ai_value_history(days: int = Query(30, ge=1, le=365)):
    """Get daily value history of the AI portfolio."""
    history = get_portfolio_value_history("finvibe-agent", days)
    return {"status": "ok", "history": history, "count": len(history)}
