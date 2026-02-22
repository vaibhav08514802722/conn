"""
Portfolio routes — view and manage user & shadow portfolios.
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional

from backend.services.portfolio_service import (
    get_portfolio,
    get_all_portfolios,
    add_or_update_holding,
    remove_holding,
    get_trade_logs,
    get_portfolio_value_history,
)

router = APIRouter(prefix="/api/portfolio", tags=["Portfolio"])


# ─────────────────────── Request Models ─────────────────────────────────────

class HoldingUpdate(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol")
    shares: float = Field(..., gt=0, description="Number of shares")
    avg_cost: float = Field(..., gt=0, description="Average cost per share")
    current_price: float = Field(0, ge=0, description="Latest price (optional)")


class UpdateHoldingsRequest(BaseModel):
    user_id: str = Field(default="demo")
    portfolio_type: str = Field(default="user", description="'user' or 'shadow'")
    holding: HoldingUpdate


class RemoveHoldingRequest(BaseModel):
    user_id: str = Field(default="demo")
    portfolio_type: str = Field(default="user")
    ticker: str


# ─────────────────────── Endpoints ──────────────────────────────────────────

@router.get("/{user_id}")
def get_user_portfolios(user_id: str):
    """
    Get all portfolios for a user (both user and shadow).
    """
    try:
        portfolios = get_all_portfolios(user_id)
        return {"status": "ok", "user_id": user_id, "portfolios": portfolios}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{user_id}/{portfolio_type}")
def get_specific_portfolio(user_id: str, portfolio_type: str):
    """
    Get a specific portfolio (user or shadow) for a user.
    """
    if portfolio_type not in ("user", "shadow"):
        raise HTTPException(status_code=400, detail="portfolio_type must be 'user' or 'shadow'")

    portfolio = get_portfolio(user_id, portfolio_type)
    if not portfolio:
        raise HTTPException(status_code=404, detail=f"No {portfolio_type} portfolio found for {user_id}")

    return {"status": "ok", "portfolio": portfolio}


@router.get("/shadow/history")
def get_shadow_history(days: int = Query(30, ge=1, le=365)):
    """
    Get daily value history for the shadow portfolio.
    Used by the frontend portfolio chart.
    """
    try:
        history = get_portfolio_value_history("finvibe-agent", days)
        return {"status": "ok", "history": history, "count": len(history)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/holdings")
def update_portfolio_holding(request: UpdateHoldingsRequest):
    """
    Add or update a single holding within a portfolio.
    """
    success = add_or_update_holding(
        user_id=request.user_id,
        portfolio_type=request.portfolio_type,
        ticker=request.holding.ticker.upper(),
        shares=request.holding.shares,
        avg_cost=request.holding.avg_cost,
        current_price=request.holding.current_price,
    )

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Portfolio not found for user={request.user_id}, type={request.portfolio_type}"
        )

    return {"status": "ok", "message": f"Updated {request.holding.ticker.upper()} in portfolio"}


@router.delete("/holdings")
def delete_portfolio_holding(request: RemoveHoldingRequest):
    """
    Remove a holding entirely from a portfolio.
    """
    success = remove_holding(
        user_id=request.user_id,
        portfolio_type=request.portfolio_type,
        ticker=request.ticker.upper(),
    )

    if not success:
        raise HTTPException(status_code=404, detail="Portfolio or holding not found")

    return {"status": "ok", "message": f"Removed {request.ticker.upper()} from portfolio"}


@router.get("/trades/history")
def get_trade_history(
    portfolio_type: str = Query("shadow"),
    ticker: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """
    Get recent trade logs, optionally filtered by ticker.
    """
    try:
        trades = get_trade_logs(portfolio_type, limit, ticker)
        return {"status": "ok", "trades": trades, "count": len(trades)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
