"""
Trade logging schemas.
Every shadow-portfolio trade is logged with its rationale and (later) its outcome.
"""
from datetime import datetime, timezone
from typing import Literal, Optional
from uuid import uuid4
from pydantic import BaseModel, Field


class TradeRationale(BaseModel):
    """Why the agent decided to make this trade."""
    signal: str = Field(..., description="Primary signal that triggered the trade")
    prediction: str = Field(..., description="Natural-language prediction, e.g. 'AAPL +5% in 3 days'")
    target_pct: float = Field(..., description="Expected % move")
    horizon_days: int = Field(..., ge=1, description="Days until prediction should be evaluated")
    confidence: float = Field(..., ge=0, le=1, description="Agent's confidence 0-1")


class TradeOutcome(BaseModel):
    """Filled by the Evaluator cron after horizon_days have passed."""
    actual_pct: float = Field(..., description="Actual % change observed")
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    success: bool = Field(..., description="Did the price move in the predicted direction?")
    lesson_learned: Optional[str] = Field(None, description="Reflection generated on failure")


class TradeLog(BaseModel):
    """
    A single trade record in the shadow portfolio.
    Written by the Executor node; outcome is filled later by the Evaluator.
    """
    trade_id: str = Field(default_factory=lambda: str(uuid4()))
    portfolio_type: Literal["shadow"] = "shadow"
    ticker: str
    action: Literal["BUY", "SELL"]
    shares: float = Field(..., gt=0)
    price_at_execution: float = Field(..., gt=0)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    rationale: TradeRationale
    outcome: Optional[TradeOutcome] = None
