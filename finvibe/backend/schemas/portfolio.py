"""
Portfolio & Holding schemas.
Used for both the user's real portfolio and the $1M shadow portfolio.
"""
from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field


class Holding(BaseModel):
    """A single stock position within a portfolio."""
    ticker: str = Field(..., example="AAPL", description="Stock ticker symbol")
    shares: float = Field(..., ge=0, description="Number of shares held")
    avg_cost: float = Field(..., ge=0, description="Average cost basis per share")
    current_price: float = Field(0.0, ge=0, description="Latest market price per share")

    @property
    def market_value(self) -> float:
        return self.shares * self.current_price

    @property
    def unrealized_pnl(self) -> float:
        return (self.current_price - self.avg_cost) * self.shares


class Portfolio(BaseModel):
    """
    A portfolio document stored in MongoDB.
    portfolio_type='shadow' => the agent's own $1M paper-trading fund.
    portfolio_type='user'   => tracks the user's actual holdings.
    """
    user_id: str = Field(..., description="Owner identifier")
    portfolio_type: Literal["user", "shadow"] = Field(..., description="Portfolio category")
    holdings: list[Holding] = Field(default_factory=list)
    cash_balance: float = Field(0.0, ge=0, description="Uninvested cash")
    total_value: float = Field(0.0, ge=0, description="Cash + sum of all holdings market value")
    inception_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def recalculate_total(self) -> None:
        """Recompute total_value from holdings + cash."""
        holdings_value = sum(h.shares * h.current_price for h in self.holdings)
        self.total_value = holdings_value + self.cash_balance
        self.updated_at = datetime.now(timezone.utc)
