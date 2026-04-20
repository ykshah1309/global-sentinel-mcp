"""Pydantic v2 models for Polymarket prediction market data."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MarketOdds(BaseModel):
    event_id: str = Field(..., description="Polymarket event id")
    slug: str | None = Field(None, description="URL-safe event identifier")
    title: str
    probability_pct: float = Field(
        ..., description="Implied probability of the 'Yes' outcome, 0-100"
    )
    volume_usd: float = Field(
        ..., description="Cumulative trading volume across the event's markets (USDC)"
    )
    end_date: datetime | None = None


class PredictionSearchResult(BaseModel):
    query: str
    results: list[MarketOdds]
    fetched_at: datetime


class PredictionError(BaseModel):
    error: str
    detail: str | None = None
