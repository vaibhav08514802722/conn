"""
Portfolio Service — CRUD operations for portfolios and trade logs in MongoDB.

All functions are pure data operations (no LLM calls).
Used by the Executor node, the Evaluator cron, and the portfolio API routes.
"""
from datetime import datetime, timezone
from typing import Optional

from backend.deps import get_portfolios_col, get_trade_logs_col


# ─────────────────────── Portfolio CRUD ─────────────────────────────────────

def create_portfolio(user_id: str, portfolio_type: str, cash_balance: float = 0) -> dict:
    """
    Create a new portfolio document in MongoDB.
    Returns the created document (without _id).
    """
    doc = {
        "user_id": user_id,
        "portfolio_type": portfolio_type,
        "holdings": [],
        "cash_balance": cash_balance,
        "total_value": cash_balance,
        "inception_date": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    result = get_portfolios_col().insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    return doc


def get_portfolio(user_id: str, portfolio_type: str = "shadow") -> Optional[dict]:
    """
    Fetch a portfolio from MongoDB.
    Returns None if not found.
    """
    doc = get_portfolios_col().find_one({
        "user_id": user_id,
        "portfolio_type": portfolio_type,
    })
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


def get_all_portfolios(user_id: str) -> list[dict]:
    """
    Fetch all portfolios (user + shadow) for a given user.
    """
    docs = list(get_portfolios_col().find({"user_id": user_id}))
    for doc in docs:
        doc["_id"] = str(doc["_id"])
    return docs


def update_holdings(
    user_id: str,
    portfolio_type: str,
    holdings: list[dict],
    cash_balance: float,
) -> bool:
    """
    Replace the holdings array and cash balance for a portfolio.
    Recalculates total_value automatically.
    Returns True if a document was updated.
    """
    holdings_value = sum(
        h.get("shares", 0) * h.get("current_price", 0)
        for h in holdings
    )
    total_value = holdings_value + cash_balance

    result = get_portfolios_col().update_one(
        {"user_id": user_id, "portfolio_type": portfolio_type},
        {"$set": {
            "holdings": holdings,
            "cash_balance": cash_balance,
            "total_value": total_value,
            "updated_at": datetime.now(timezone.utc),
        }},
    )
    return result.modified_count > 0


def add_or_update_holding(
    user_id: str,
    portfolio_type: str,
    ticker: str,
    shares: float,
    avg_cost: float,
    current_price: float = 0,
) -> bool:
    """
    Add a new holding or update an existing one within a portfolio.
    If holding exists, replaces shares and avg_cost.
    """
    portfolio = get_portfolio(user_id, portfolio_type)
    if not portfolio:
        return False

    holdings = portfolio.get("holdings", [])

    # Update existing or append new
    found = False
    for h in holdings:
        if h.get("ticker") == ticker:
            h["shares"] = shares
            h["avg_cost"] = avg_cost
            h["current_price"] = current_price
            found = True
            break

    if not found:
        holdings.append({
            "ticker": ticker,
            "shares": shares,
            "avg_cost": avg_cost,
            "current_price": current_price,
        })

    return update_holdings(
        user_id, portfolio_type,
        holdings, portfolio.get("cash_balance", 0)
    )


def remove_holding(user_id: str, portfolio_type: str, ticker: str) -> bool:
    """Remove a holding completely from a portfolio."""
    portfolio = get_portfolio(user_id, portfolio_type)
    if not portfolio:
        return False

    holdings = [h for h in portfolio.get("holdings", []) if h.get("ticker") != ticker]

    return update_holdings(
        user_id, portfolio_type,
        holdings, portfolio.get("cash_balance", 0)
    )


# ─────────────────────── Trade Log CRUD ─────────────────────────────────────

def record_trade(
    trade_id: str,
    ticker: str,
    action: str,
    shares: float,
    price: float,
    rationale: dict,
    portfolio_type: str = "shadow",
) -> str:
    """
    Insert a trade log document into MongoDB.
    Returns the trade_id.
    """
    doc = {
        "trade_id": trade_id,
        "portfolio_type": portfolio_type,
        "ticker": ticker,
        "action": action,
        "shares": shares,
        "price_at_execution": price,
        "timestamp": datetime.now(timezone.utc),
        "rationale": rationale,
        "outcome": None,
    }
    get_trade_logs_col().insert_one(doc)
    return trade_id


def get_trade_logs(
    portfolio_type: str = "shadow",
    limit: int = 50,
    ticker: Optional[str] = None,
) -> list[dict]:
    """
    Fetch recent trade logs, optionally filtered by ticker.
    """
    query = {"portfolio_type": portfolio_type}
    if ticker:
        query["ticker"] = ticker

    docs = list(
        get_trade_logs_col()
        .find(query, {"_id": 0})
        .sort("timestamp", -1)
        .limit(limit)
    )
    return docs


def get_pending_evaluations() -> list[dict]:
    """
    Fetch all trades where outcome is None (not yet evaluated).
    """
    return list(get_trade_logs_col().find(
        {"outcome": None},
        {"_id": 0}
    ))


def update_trade_outcome(trade_id: str, outcome: dict) -> bool:
    """
    Set the outcome field on a trade log document.
    Called by the Evaluator after checking if the prediction came true.
    """
    result = get_trade_logs_col().update_one(
        {"trade_id": trade_id},
        {"$set": {"outcome": outcome}}
    )
    return result.modified_count > 0


# ─────────────────────── Portfolio History ──────────────────────────────────

def get_portfolio_value_history(user_id: str = "finvibe-agent", days: int = 30) -> list[dict]:
    """
    Compute daily portfolio value snapshots from trade logs.
    Returns list of {"date": "2026-02-19", "total_value": 1003500.50}.

    Simple approach: start from inception cash, replay trades chronologically.
    """
    from backend.services.market_service import get_stock_price
    from backend.config import settings

    portfolio = get_portfolio(user_id, "shadow")
    if not portfolio:
        return []

    # Get all trades sorted chronologically
    trades = list(
        get_trade_logs_col()
        .find({"portfolio_type": "shadow"}, {"_id": 0})
        .sort("timestamp", 1)
    )

    if not trades:
        # No trades yet — return current value as single point
        return [{
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "total_value": portfolio.get("total_value", settings.shadow_portfolio_cash),
            "cash_balance": portfolio.get("cash_balance", settings.shadow_portfolio_cash),
            "holdings_count": len(portfolio.get("holdings", [])),
        }]

    # Group trades by date
    daily_snapshots = []
    current_cash = settings.shadow_portfolio_cash
    current_holdings = {}  # {ticker: {"shares": x, "avg_cost": y}}

    seen_dates = set()
    for trade in trades:
        ts = trade.get("timestamp")
        if not ts:
            continue
        date_str = ts.strftime("%Y-%m-%d") if isinstance(ts, datetime) else str(ts)[:10]
        ticker = trade.get("ticker", "")
        action = trade.get("action", "")
        shares = trade.get("shares", 0)
        price = trade.get("price_at_execution", 0)
        value = shares * price

        if action == "BUY":
            current_cash -= value
            if ticker in current_holdings:
                old = current_holdings[ticker]
                new_shares = old["shares"] + shares
                old_cost_total = old["shares"] * old["avg_cost"]
                current_holdings[ticker] = {
                    "shares": new_shares,
                    "avg_cost": (old_cost_total + value) / new_shares,
                }
            else:
                current_holdings[ticker] = {"shares": shares, "avg_cost": price}
        elif action == "SELL":
            current_cash += value
            if ticker in current_holdings:
                current_holdings[ticker]["shares"] -= shares
                if current_holdings[ticker]["shares"] <= 0:
                    del current_holdings[ticker]

        if date_str not in seen_dates:
            seen_dates.add(date_str)
            # Estimate total: cash + holdings at trade price (rough)
            holdings_value = sum(
                h["shares"] * h["avg_cost"] for h in current_holdings.values()
            )
            daily_snapshots.append({
                "date": date_str,
                "total_value": round(current_cash + holdings_value, 2),
                "cash_balance": round(current_cash, 2),
                "holdings_count": len(current_holdings),
            })

    # Add current state as latest point
    if portfolio.get("holdings"):
        daily_snapshots.append({
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "total_value": round(portfolio.get("total_value", 0), 2),
            "cash_balance": round(portfolio.get("cash_balance", 0), 2),
            "holdings_count": len(portfolio.get("holdings", [])),
        })

    return daily_snapshots[-days:]  # Last N days
