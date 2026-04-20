"""Async client for the OpenSky Network API with N-Number conversion.

Auth flows supported (picked in this priority order):

1. OAuth2 client-credentials: set ``OPENSKY_CLIENT_ID`` + ``OPENSKY_CLIENT_SECRET``.
   The current first-class path per OpenSky's 2025 migration. We fetch a bearer
   token from the Keycloak endpoint and cache it until expiry.
2. Basic Auth: set ``OPENSKY_USERNAME`` + ``OPENSKY_PASSWORD``. Legacy but still
   honored for accounts created before the OAuth2 migration.
3. Unauthenticated (anonymous). Allowed but strictly rate-limited by OpenSky.
"""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Any

import httpx

from .._cache import OPENSKY_TTL, TTLCache
from .._http import build_client
from .converter import nnumber_to_icao
from .models import AircraftState, AviationError

logger = logging.getLogger(__name__)

OPENSKY_BASE = "https://opensky-network.org/api"
OPENSKY_TOKEN_URL = (
    "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
)
FAA_REGISTRY_URL = "https://registry.faa.gov/aircraftinquiry/Search/NNumberResult"

_state_cache = TTLCache(ttl=OPENSKY_TTL)

# Token cache: (access_token, expires_at_monotonic)
_oauth_token: tuple[str, float] | None = None


async def _get_oauth_token() -> str | None:
    """Return a cached bearer token, refreshing via client-credentials as needed."""
    global _oauth_token

    client_id = os.environ.get("OPENSKY_CLIENT_ID")
    client_secret = os.environ.get("OPENSKY_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None

    now = time.monotonic()
    if _oauth_token is not None and _oauth_token[1] - 30 > now:
        return _oauth_token[0]

    try:
        async with build_client(timeout=10.0) as client:
            resp = await client.post(
                OPENSKY_TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        logger.warning("opensky oauth token fetch failed: %s", exc)
        return None

    token = data.get("access_token")
    expires_in = float(data.get("expires_in") or 300)
    if not token:
        return None
    _oauth_token = (token, now + expires_in)
    return token


def _basic_auth() -> tuple[str, str] | None:
    user = os.environ.get("OPENSKY_USERNAME")
    pwd = os.environ.get("OPENSKY_PASSWORD")
    if user and pwd:
        return (user, pwd)
    return None


async def _opensky_client() -> httpx.AsyncClient:
    """Build an httpx client with OAuth2 token if available, else Basic Auth, else anonymous."""
    token = await _get_oauth_token()
    if token:
        return build_client(
            timeout=15.0,
            headers={"Authorization": f"Bearer {token}"},
        )
    basic = _basic_auth()
    if basic:
        return build_client(timeout=15.0, auth=basic)
    return build_client(timeout=15.0)


# FAA Mode S Code is labelled a few different ways across the registry page
# across refreshes; match the most permissive safe pattern.
_FAA_MODES_PATTERNS = [
    re.compile(
        r"Mode\s+S\s+Code\s*\(\s*base\s*16\s*\)\s*</[^>]+>\s*<[^>]+>\s*([0-9A-Fa-f]{6})",
        re.IGNORECASE,
    ),
    re.compile(r"Mode\s+S\s+Code[^<]*</[^>]+>\s*<[^>]+>\s*([0-9A-Fa-f]{6})", re.IGNORECASE),
    re.compile(r">\s*([0-9A-Fa-f]{6})\s*<[^>]*>\s*Mode\s+S", re.IGNORECASE),
]


async def _faa_registry_lookup(tail: str) -> str | None:
    """Fallback: scrape the FAA registry for the Mode S (ICAO24 hex) of a tail number."""
    try:
        async with build_client(timeout=15.0) as client:
            resp = await client.get(
                FAA_REGISTRY_URL,
                params={"NNumberTxt": tail.upper().lstrip("N")},
            )
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.debug("FAA registry lookup failed for %s: %s", tail, exc)
        return None

    html = resp.text
    for pattern in _FAA_MODES_PATTERNS:
        match = pattern.search(html)
        if match:
            return match.group(1).lower()
    return None


async def _resolve_icao24(tail_or_icao: str) -> str | AviationError:
    """Resolve a tail number or ICAO24 hex to a lowercase 6-char hex string."""
    value = tail_or_icao.strip()
    if not value:
        return AviationError(error="invalid_input", detail="empty identifier")

    if re.fullmatch(r"[0-9a-fA-F]{6}", value):
        return value.lower()

    icao = nnumber_to_icao(value)
    if icao is not None:
        return icao

    faa_result = await _faa_registry_lookup(value)
    if faa_result is not None:
        return faa_result

    return AviationError(
        error="unresolvable_tail",
        detail=f"Could not resolve '{value}' via N-Number math or FAA registry",
    )


def _parse_state_vector(sv: list[Any]) -> AircraftState:
    """Parse a single OpenSky state-vector array into a typed model."""
    return AircraftState(
        icao24=sv[0] or "",
        callsign=(sv[1] or "").strip() or None,
        origin_country=sv[2] or "",
        longitude=sv[5],
        latitude=sv[6],
        baro_altitude_m=sv[7],
        on_ground=bool(sv[8]),
        velocity_ms=sv[9],
        heading=sv[10],
        last_contact=sv[4] or 0,
    )


async def get_state_by_icao(icao24: str) -> AircraftState | AviationError:
    """Get the latest state vector for a single ICAO24 address."""
    icao = icao24.lower()
    cached = await _state_cache.get(f"state:{icao}")
    if cached is not None:
        return cached

    try:
        async with await _opensky_client() as client:
            resp = await client.get(
                f"{OPENSKY_BASE}/states/all",
                params={"icao24": icao},
            )
            if resp.status_code == 429:
                return AviationError(error="rate_limited", retry_after_seconds=60)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        return AviationError(error=f"http_{exc.response.status_code}", detail=str(exc))
    except httpx.HTTPError as exc:
        return AviationError(error="request_failed", detail=str(exc))

    states = data.get("states")
    if not states:
        return AviationError(
            error="not_found",
            detail=f"No state vector found for ICAO24 {icao}",
        )

    state = _parse_state_vector(states[0])
    await _state_cache.set(f"state:{icao}", state)
    return state


async def get_states_in_bbox(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
) -> list[AircraftState] | AviationError:
    """Get all state vectors within a geographic bounding box."""
    try:
        async with await _opensky_client() as client:
            resp = await client.get(
                f"{OPENSKY_BASE}/states/all",
                params={
                    "lamin": lat_min,
                    "lamax": lat_max,
                    "lomin": lon_min,
                    "lomax": lon_max,
                },
            )
            if resp.status_code == 429:
                return AviationError(error="rate_limited", retry_after_seconds=60)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        return AviationError(error=f"http_{exc.response.status_code}", detail=str(exc))
    except httpx.HTTPError as exc:
        return AviationError(error="request_failed", detail=str(exc))

    states = data.get("states") or []
    return [_parse_state_vector(sv) for sv in states]


async def lookup_aircraft(tail_or_icao: str) -> AircraftState | AviationError:
    """Resolve a tail number or ICAO24 hex, then look up the aircraft state."""
    resolved = await _resolve_icao24(tail_or_icao)
    if isinstance(resolved, AviationError):
        return resolved
    return await get_state_by_icao(resolved)
