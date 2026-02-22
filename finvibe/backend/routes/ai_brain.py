"""
AI Brain routes — autonomous trading endpoints.

Trigger the AI brain to scan markets, analyze stocks, and execute trades.
"""
from fastapi import APIRouter, Query

from backend.services.ai_brain import (
    run_brain_cycle,
    get_brain_history,
    get_brain_stats,
    scan_market,
    analyze_candidate,
)

router = APIRouter(prefix="/api/brain", tags=["AI Brain"])


@router.post("/run")
def trigger_brain_cycle():
    """
    Trigger one full autonomous investment cycle.
    The AI brain will:
    1. Scan global markets for opportunities
    2. Deep-analyze promising candidates
    3. Review existing holdings
    4. Execute trades (buy/sell) autonomously
    Returns full activity log with every decision explained.
    """
    log = run_brain_cycle()
    return {"status": "ok", "log": log}


@router.get("/history")
def brain_history(limit: int = Query(10, ge=1, le=50)):
    """Get history of past brain cycles."""
    logs = get_brain_history(limit)
    return {"status": "ok", "logs": logs, "count": len(logs)}


@router.get("/stats")
def brain_stats():
    """Get brain performance statistics."""
    stats = get_brain_stats()
    return {"status": "ok", "stats": stats}


@router.post("/scan")
def trigger_scan():
    """Run only the SCAN step — discover promising candidates without trading."""
    candidates = scan_market()
    return {"status": "ok", "candidates": candidates, "count": len(candidates)}


@router.post("/analyze/{ticker}")
def trigger_analyze(ticker: str):
    """Deep-analyze a single stock — returns full AI verdict without trading."""
    result = analyze_candidate(ticker.upper().strip())
    return {"status": "ok", "analysis": result}
