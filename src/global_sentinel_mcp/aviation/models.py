"""Pydantic v2 models for OpenSky aviation state data."""

from __future__ import annotations

from pydantic import BaseModel


class AircraftState(BaseModel):
    icao24: str
    callsign: str | None = None
    origin_country: str
    longitude: float | None = None
    latitude: float | None = None
    baro_altitude_m: float | None = None
    on_ground: bool
    velocity_ms: float | None = None
    heading: float | None = None
    last_contact: int


class AviationError(BaseModel):
    error: str
    detail: str | None = None
    retry_after_seconds: int | None = None
