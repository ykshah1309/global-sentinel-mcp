"""Pydantic v2 models for Cloudflare Radar infrastructure data."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class BGPEvent(BaseModel):
    """A single BGP hijack or route-leak event from Cloudflare Radar."""

    id: str | int | None = None
    event_type: str | None = Field(None, description="'hijack' or 'route_leak'")
    detected_ts: str | None = None
    prefix: str | None = None
    origin_asn: int | None = None
    hijacker_asn: int | None = None
    confidence: str | None = None


class BGPAnomalyReport(BaseModel):
    scope: str
    kind: str = Field(..., description="'hijacks' or 'leaks'")
    anomalies: list[BGPEvent]
    fetched_at: datetime


class OutageAnnotation(BaseModel):
    """A regional internet outage annotation from Cloudflare Radar."""

    id: str | int | None = None
    locations: list[str] = Field(default_factory=list)
    asns: list[int] = Field(default_factory=list)
    event_type: str | None = None
    outage_cause: str | None = None
    outage_type: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None
    linked_url: str | None = None
    scope: str | None = None


class TrafficAnomalyReport(BaseModel):
    country: str
    anomalies: list[OutageAnnotation]
    fetched_at: datetime


class InfraError(BaseModel):
    error: str
    detail: str | None = None
