"""
EVALUATOR — Cron-style job that checks past trade predictions.

Run manually:  cd finvibe && python -m jobs.evaluator
Run on schedule: use APScheduler, cron, or a task queue.

What it does:
1. Finds all trade logs where outcome is None AND horizon has passed
2. Fetches the current price for each ticker
3. Compares actual vs predicted movement
4. Marks success/failure and generates a lesson
5. Stores the lesson in Qdrant (reflection_memory)
6. Updates the trade log in MongoDB with the outcome
"""
from datetime import datetime, timedelta, timezone

from backend.deps import get_trade_logs_col
from backend.services.market_service import get_stock_price
from backend.services.vector_service import store_reflection_lesson


def evaluate_pending_trades():
    """
    Find and evaluate all trade predictions whose horizon has passed.
    """
    print("\n" + "=" * 60)
    print("  📊 FinVibe Evaluator — Checking Past Predictions...")
    print("=" * 60)

    trade_logs = get_trade_logs_col()

    # Find trades with no outcome yet
    pending = list(trade_logs.find({"outcome": None}))
    print(f"  Found {len(pending)} pending trades")

    evaluated = 0
    successes = 0
    failures = 0

    for trade in pending:
        trade_id = trade.get("trade_id", "")
        ticker = trade.get("ticker", "")
        action = trade.get("action", "")
        price_at_execution = trade.get("price_at_execution", 0)
        timestamp = trade.get("timestamp")
        rationale = trade.get("rationale", {})

        horizon_days = rationale.get("horizon_days", 5)
        target_pct = rationale.get("target_pct", 0)

        # Check if enough time has passed
        if timestamp and isinstance(timestamp, datetime):
            deadline = timestamp + timedelta(days=horizon_days)
            if datetime.now(timezone.utc) < deadline:
                remaining = (deadline - datetime.now(timezone.utc)).days
                print(f"  [{ticker}] {trade_id[:8]}... — {remaining}d remaining, skipping")
                continue

        # Fetch current price
        current_data = get_stock_price(ticker)
        if "error" in current_data:
            print(f"  [{ticker}] {trade_id[:8]}... — can't fetch price, skipping")
            continue

        current_price = current_data.get("current_price", 0)
        if not current_price or not price_at_execution:
            continue

        # Calculate actual percentage change
        actual_pct = ((current_price - price_at_execution) / price_at_execution) * 100

        # Determine success:
        # BUY is successful if price went UP (or at least in the predicted direction)
        # SELL is successful if price went DOWN after selling
        if action == "BUY":
            success = actual_pct > 0 if target_pct > 0 else actual_pct < 0
        elif action == "SELL":
            success = actual_pct < 0  # Sold before it dropped = good
        else:
            success = False

        if success:
            successes += 1
        else:
            failures += 1

        # Generate lesson
        lesson = _generate_evaluation_lesson(
            ticker, action, price_at_execution, current_price,
            actual_pct, target_pct, success, rationale
        )

        # Update trade log with outcome
        outcome = {
            "actual_pct": round(actual_pct, 2),
            "evaluated_at": datetime.now(timezone.utc),
            "success": success,
            "lesson_learned": lesson,
        }

        trade_logs.update_one(
            {"trade_id": trade_id},
            {"$set": {"outcome": outcome}}
        )

        # Store lesson in Qdrant reflection_memory
        metadata = {
            "ticker": ticker,
            "trade_id": trade_id,
            "action": action,
            "success": success,
            "failure_type": "" if success else _classify_failure(actual_pct, target_pct, action),
            "created_at": datetime.utcnow().isoformat(),
        }
        store_reflection_lesson(lesson, metadata)

        status_emoji = "✅" if success else "❌"
        print(
            f"  {status_emoji} [{ticker}] {action} @ ${price_at_execution:.2f} "
            f"→ ${current_price:.2f} ({actual_pct:+.1f}%) "
            f"target was {target_pct:+.1f}%"
        )

        evaluated += 1

    print(f"\n  Evaluated: {evaluated} | Success: {successes} | Failed: {failures}")
    print("=" * 60 + "\n")

    return {"evaluated": evaluated, "successes": successes, "failures": failures}


def _generate_evaluation_lesson(
    ticker: str, action: str,
    entry_price: float, current_price: float,
    actual_pct: float, target_pct: float,
    success: bool, rationale: dict
) -> str:
    """Generate a detailed lesson from the trade outcome."""
    signal = rationale.get("signal", "unknown")
    prediction = rationale.get("prediction", "unknown")
    confidence = rationale.get("confidence", 0)
    horizon = rationale.get("horizon_days", "?")

    if success:
        lesson = (
            f"SUCCESS: {action} {ticker} worked. Entry ${entry_price:.2f} → "
            f"${current_price:.2f} ({actual_pct:+.1f}%, target was {target_pct:+.1f}%). "
            f"Signal '{signal}' with {confidence:.0%} confidence was correct. "
            f"Lesson: Trust this signal type when conditions match — "
            f"{prediction}."
        )
    else:
        failure_type = _classify_failure(actual_pct, target_pct, action)
        lesson = (
            f"FAILURE ({failure_type}): {action} {ticker} went wrong. "
            f"Entry ${entry_price:.2f} → ${current_price:.2f} ({actual_pct:+.1f}%, "
            f"target was {target_pct:+.1f}%). "
            f"Signal '{signal}' with {confidence:.0%} confidence was WRONG. "
            f"Lesson: Be cautious with this signal type — {prediction} did not materialize. "
            f"Consider requiring higher confidence or additional confirmation next time."
        )

    return lesson


def _classify_failure(actual_pct: float, target_pct: float, action: str) -> str:
    """Classify what kind of failure this was."""
    if action == "BUY" and actual_pct < -5:
        return "major_loss"
    elif action == "BUY" and actual_pct < 0:
        return "minor_loss"
    elif action == "BUY" and actual_pct > 0 and actual_pct < target_pct * 0.5:
        return "underperformance"
    elif action == "SELL" and actual_pct > 5:
        return "premature_exit"
    elif action == "SELL" and actual_pct > 0:
        return "wrong_direction"
    else:
        return "miscalculation"


if __name__ == "__main__":
    evaluate_pending_trades()
