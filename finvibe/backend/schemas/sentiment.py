"""
Market sentiment & vibe-check schemas.
Produced by the Vibe Analyst node after analyzing news + audio.
"""
from datetime import datetime, timezone
from typing import Literal, Optional
from pydantic import BaseModel, Field


class VibeScore(BaseModel):
    """Structured sentiment output for a single ticker."""
    ticker: str
    sentiment_score: float = Field(..., ge=-1.0, le=1.0, description="-1 (bearish) to +1 (bullish)")
    anxiety_score: float = Field(..., ge=0.0, le=10.0, description="0 (calm) to 10 (panic)")
    vibe_label: Literal["euphoric", "bullish", "neutral", "anxious", "panic"]
    key_driver: str = Field(..., description="One-line reason for this vibe")


class MarketSentiment(BaseModel):
    """
    A sentiment document stored in MongoDB.
    One per (ticker, source, timestamp) analysis.
    """
    ticker: str
    source: Literal["news", "earnings_call", "social"]
    content_summary: str = Field(..., description="Brief summary of analyzed content")
    sentiment_score: float = Field(..., ge=-1.0, le=1.0)
    anxiety_score: float = Field(..., ge=0.0, le=10.0)
    vibe_label: Literal["euphoric", "bullish", "neutral", "anxious", "panic"]
    raw_text: Optional[str] = None
    audio_url: Optional[str] = None
    analyzed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AnxietyAlert(BaseModel):
    """Emitted when anxiety breaches the threshold and user portfolio is at risk."""
    user_id: str
    affected_tickers: list[str]
    max_anxiety_score: float
    portfolio_impact_pct: float = Field(..., description="Estimated % loss on user portfolio")
    alert_reason: str
    suggested_actions: list[str]
    triggered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
