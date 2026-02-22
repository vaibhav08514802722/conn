"""
EXECUTOR NODE
==============
Fourth node in the graph. Executes trades on the shadow portfolio.

This is a PAPER TRADING engine — no real money, no broker API.
It updates MongoDB positions and logs every trade with its rationale.

Input:  state["trade_decisions"], state["portfolio_snapshot"], state["market_data"]
Output: state["execution_results"]
"""
from datetime import datetime
from uuid import uuid4

from backend.schemas.agent_state import AgentState
from backend.deps import get_portfolios_col, get_trade_logs_col
from backend.config import settings


def executor_node(state: AgentState) -> dict:
    """
    Execute each trade decision against the shadow portfolio.
    Updates MongoDB portfolio + writes trade logs.
    """
    trade_decisions = state.get("trade_decisions", [])
    market_data = state.get("market_data", {})
    portfolio_snapshot = state.get("portfolio_snapshot", {})

    if not trade_decisions:
        return {
            "execution_results": [],
            "messages": [{"role": "assistant", "content": "No trades to execute."}],
        }

    print(f"[Executor] Executing {len(trade_decisions)} trades...")

    execution_results = []

    for td in trade_decisions:
        ticker = td.get("ticker", "")
        action = td.get("action", "").upper()
        shares = td.get("shares", 0)
        rationale = td.get("rationale", {})

        # Get current price from market data
        price_data = market_data.get(ticker, {})
        current_price = price_data.get("current_price", 0)

        if not current_price:
            result = {
                "trade_id": str(uuid4()),
                "ticker": ticker,
                "action": action,
                "status": "FAILED",
                "message": f"No price data available for {ticker}",
            }
            execution_results.append(result)
            print(f"  [Executor] SKIP {action} {ticker}: no price data")
            continue

        # Validate the trade against portfolio constraints
        validation_error = _validate_trade(action, ticker, shares, current_price, portfolio_snapshot)
        if validation_error:
            result = {
                "trade_id": str(uuid4()),
                "ticker": ticker,
                "action": action,
                "status": "REJECTED",
                "message": validation_error,
            }
            execution_results.append(result)
            print(f"  [Executor] REJECT {action} {shares} {ticker}: {validation_error}")
            continue

        # Execute the trade
        trade_id = str(uuid4())
        trade_value = shares * current_price

        if action == "BUY":
            _execute_buy(ticker, shares, current_price, portfolio_snapshot)
            msg = f"Bought {shares} {ticker} @ ${current_price:.2f} (${trade_value:,.2f})"
        elif action == "SELL":
            _execute_sell(ticker, shares, current_price, portfolio_snapshot)
            msg = f"Sold {shares} {ticker} @ ${current_price:.2f} (${trade_value:,.2f})"
        else:
            result = {
                "trade_id": trade_id,
                "ticker": ticker,
                "action": action,
                "status": "FAILED",
                "message": f"Unknown action: {action}",
            }
            execution_results.append(result)
            continue

        # Log the trade to MongoDB
        _log_trade(trade_id, ticker, action, shares, current_price, rationale)

        result = {
            "trade_id": trade_id,
            "ticker": ticker,
            "action": action,
            "shares": shares,
            "price": current_price,
            "value": trade_value,
            "status": "EXECUTED",
            "message": msg,
        }
        execution_results.append(result)
        print(f"  [Executor] ✅ {msg}")

    # Persist updated portfolio to MongoDB
    _save_portfolio(portfolio_snapshot)

    # Build summary message
    executed = [r for r in execution_results if r["status"] == "EXECUTED"]
    rejected = [r for r in execution_results if r["status"] in ("REJECTED", "FAILED")]

    summary_lines = [f"**Trade Execution Complete** 💼 ({len(executed)} executed, {len(rejected)} skipped)"]
    for r in executed:
        summary_lines.append(f"- ✅ {r['message']}")
    for r in rejected:
        summary_lines.append(f"- ❌ {r['ticker']}: {r['message']}")

    summary = "\n".join(summary_lines)

    return {
        "execution_results": execution_results,
        "messages": [{"role": "assistant", "content": summary}],
    }


# ─────────────────────── Trade Validation ───────────────────────────────────

def _validate_trade(
    action: str, ticker: str, shares: float,
    price: float, portfolio: dict
) -> str | None:
    """
    Validate a trade against portfolio rules.
    Returns None if valid, or an error string if rejected.
    """
    cash = portfolio.get("cash_balance", 0)
    total_value = portfolio.get("total_value", 0) or settings.shadow_portfolio_cash
    holdings = portfolio.get("holdings", [])
    trade_value = shares * price

    if action == "BUY":
        # Rule 1: Must have enough cash
        if trade_value > cash:
            return f"Insufficient cash: need ${trade_value:,.2f} but only ${cash:,.2f} available"

        # Rule 2: Single trade can't exceed 5% of portfolio
        max_trade = total_value * 0.05
        if trade_value > max_trade:
            return f"Trade ${trade_value:,.2f} exceeds 5% limit (${max_trade:,.2f})"

        # Rule 3: Must keep 10% cash reserve
        cash_after = cash - trade_value
        min_cash = total_value * 0.10
        if cash_after < min_cash:
            return f"Would breach 10% cash reserve (${cash_after:,.2f} < ${min_cash:,.2f})"

        # Rule 4: Total position can't exceed 10% of portfolio
        existing_shares = 0
        for h in holdings:
            if h.get("ticker") == ticker:
                existing_shares = h.get("shares", 0)
                break
        total_position_value = (existing_shares + shares) * price
        max_position = total_value * 0.10
        if total_position_value > max_position:
            return f"Position ${total_position_value:,.2f} would exceed 10% limit (${max_position:,.2f})"

    elif action == "SELL":
        # Must own enough shares
        owned = 0
        for h in holdings:
            if h.get("ticker") == ticker:
                owned = h.get("shares", 0)
                break
        if shares > owned:
            return f"Can't sell {shares} shares, only own {owned}"

    return None


# ─────────────────────── Portfolio Mutations ────────────────────────────────

def _execute_buy(ticker: str, shares: float, price: float, portfolio: dict) -> None:
    """Update portfolio dict in-memory for a BUY."""
    holdings = portfolio.get("holdings", [])
    trade_value = shares * price

    # Deduct cash
    portfolio["cash_balance"] = portfolio.get("cash_balance", 0) - trade_value

    # Update or add holding
    found = False
    for h in holdings:
        if h.get("ticker") == ticker:
            old_shares = h.get("shares", 0)
            old_cost = h.get("avg_cost", 0)
            # Weighted average cost
            new_total_shares = old_shares + shares
            h["avg_cost"] = ((old_shares * old_cost) + (shares * price)) / new_total_shares
            h["shares"] = new_total_shares
            h["current_price"] = price
            found = True
            break

    if not found:
        holdings.append({
            "ticker": ticker,
            "shares": shares,
            "avg_cost": price,
            "current_price": price,
        })
        portfolio["holdings"] = holdings

    # Recalculate total
    _recalculate_total(portfolio)


def _execute_sell(ticker: str, shares: float, price: float, portfolio: dict) -> None:
    """Update portfolio dict in-memory for a SELL."""
    holdings = portfolio.get("holdings", [])
    trade_value = shares * price

    # Add cash from sale
    portfolio["cash_balance"] = portfolio.get("cash_balance", 0) + trade_value

    # Reduce holding
    for h in holdings:
        if h.get("ticker") == ticker:
            h["shares"] = h.get("shares", 0) - shares
            h["current_price"] = price
            # Remove if zero shares
            if h["shares"] <= 0:
                holdings.remove(h)
            break

    portfolio["holdings"] = holdings
    _recalculate_total(portfolio)


def _recalculate_total(portfolio: dict) -> None:
    """Recompute total_value from holdings + cash."""
    holdings_value = sum(
        h.get("shares", 0) * h.get("current_price", 0)
        for h in portfolio.get("holdings", [])
    )
    portfolio["total_value"] = holdings_value + portfolio.get("cash_balance", 0)


# ─────────────────────── Persistence ────────────────────────────────────────

def _save_portfolio(portfolio: dict) -> None:
    """Persist the updated portfolio back to MongoDB."""
    try:
        get_portfolios_col().update_one(
            {"user_id": "finvibe-agent", "portfolio_type": "shadow"},
            {"$set": {
                "holdings": portfolio.get("holdings", []),
                "cash_balance": portfolio.get("cash_balance", 0),
                "total_value": portfolio.get("total_value", 0),
                "updated_at": datetime.utcnow(),
            }},
            upsert=True,
        )
        print(f"  [Executor] Portfolio saved: ${portfolio.get('total_value', 0):,.2f}")
    except Exception as e:
        print(f"  [Executor] Failed to save portfolio: {e}")


def _log_trade(
    trade_id: str, ticker: str, action: str,
    shares: float, price: float, rationale: dict
) -> None:
    """Write a trade log document to MongoDB."""
    try:
        doc = {
            "trade_id": trade_id,
            "portfolio_type": "shadow",
            "ticker": ticker,
            "action": action,
            "shares": shares,
            "price_at_execution": price,
            "timestamp": datetime.utcnow(),
            "rationale": {
                "signal": rationale.get("signal", ""),
                "prediction": rationale.get("prediction", ""),
                "target_pct": rationale.get("target_pct", 0),
                "horizon_days": rationale.get("horizon_days", 5),
                "confidence": rationale.get("confidence", 0),
            },
            "outcome": None,  # Filled later by the Evaluator
        }
        get_trade_logs_col().insert_one(doc)
        print(f"  [Executor] Logged trade: {trade_id[:8]}... {action} {shares} {ticker}")
    except Exception as e:
        print(f"  [Executor] Failed to log trade: {e}")
