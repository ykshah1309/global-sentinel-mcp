"""Pydantic v2 models for GDELT 2.0 event data."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class GdeltEvent(BaseModel):
    global_event_id: str
    event_date: str
    actor1_country: str | None = None
    actor2_country: str | None = None
    goldstein_scale: float
    num_articles: int
    source_url: str


class GdeltEventBatch(BaseModel):
    country_code: str
    events: list[GdeltEvent]
    fetched_at: datetime


class GdeltError(BaseModel):
    error: str
    detail: str | None = None
