"""Global Sentinel MCP server.

Exposes seven tools unifying four alt-data streams for macro analysis:

* Polymarket prediction markets
* GDELT 2.0 global news events
* OpenSky Network aviation state
* Cloudflare Radar internet infrastructure
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any

from mcp.server.fastmcp import FastMCP

from .aviation.client import lookup_aircraft
from .aviation.converter import icao_to_nnumber, nnumber_to_icao
from .aviation.models import AviationError
from .infrastructure.client import (
    get_bgp_anomalies,
    get_bgp_leaks,
    get_traffic_anomalies,
)
from .infrastructure.models import BGPAnomalyReport, InfraError, TrafficAnomalyReport
from .news_events.client import fetch_latest_events
from .news_events.models import GdeltError, GdeltEventBatch
from .prediction_markets.client import get_event_probability, search_events
from .prediction_markets.models import PredictionError

# stdout is MCP JSON-RPC only — diagnostics go to stderr.
_log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    stream=sys.stderr,
    level=getattr(logging, _log_level, logging.INFO),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("global_sentinel_mcp")

mcp = FastMCP("GlobalSentinel")


def _as_dict(value: Any) -> dict:
    """Coerce a Pydantic model (or already-dict) to a JSON-safe dict."""
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return value
    return {"value": value}


# --------------------------------------------------------------------------
# Prediction markets
# --------------------------------------------------------------------------


@mcp.tool()
async def get_prediction_odds(query: str, limit: int = 5) -> dict:
    """Search Polymarket for crowd-sourced probability estimates.

    Use this tool when the user asks "what are the odds of X?" for any
    macro-relevant event — Fed rate decisions, elections, geopolitical
    outcomes, commodities. Returns up to ``limit`` active markets matching
    the query, each with implied probability (0-100), USDC volume, and end
    date. Polymarket data is crowd-sourced, not an official forecast.

    Example: ``get_prediction_odds("fed rate cut december", limit=3)``
    """
    try:
        result = await search_events(query, limit=limit)
        return _as_dict(result)
    except Exception as exc:  # safety net — FastMCP should never see a raw exception
        logger.exception("get_prediction_odds failed")
        return PredictionError(error="unhandled", detail=str(exc)).model_dump()


@mcp.tool()
async def get_prediction_event_by_id(event_id: str) -> dict:
    """Fetch a single Polymarket event's implied probability by id or slug.

    Useful when you already have a Polymarket event identifier (from a prior
    search, a URL, or an external reference) and want the current odds
    without re-searching.
    """
    try:
        result = await get_event_probability(event_id)
        return _as_dict(result)
    except Exception as exc:
        logger.exception("get_prediction_event_by_id failed")
        return PredictionError(error="unhandled", detail=str(exc)).model_dump()


# --------------------------------------------------------------------------
# Aviation
# --------------------------------------------------------------------------


@mcp.tool()
async def lookup_aircraft_state(tail_or_icao: str) -> dict:
    """Return the latest public ADS-B state vector for a registered aircraft.

    Accepts either an FAA N-Number (e.g. ``N12345``, ``N123AB``) or a 6-char
    ICAO24 hex (e.g. ``a061d9``). N-Numbers are converted in-process first;
    on failure the FAA public registry is consulted as a fallback.

    Returns position (lat/lon), barometric altitude (m), ground speed (m/s),
    heading (°), on-ground flag, and last-contact timestamp. Requires
    ``OPENSKY_CLIENT_ID`` + ``OPENSKY_CLIENT_SECRET`` (OAuth2, preferred) or
    ``OPENSKY_USERNAME`` + ``OPENSKY_PASSWORD`` (Basic Auth, legacy).
    """
    try:
        result = await lookup_aircraft(tail_or_icao)
        return _as_dict(result)
    except Exception as exc:
        logger.exception("lookup_aircraft_state failed")
        return AviationError(error="unhandled", detail=str(exc)).model_dump()


@mcp.tool()
async def convert_nnumber(identifier: str) -> dict:
    """Convert between an FAA N-Number and its ICAO24 hex address.

    Input detection is automatic: a leading ``N`` followed by digits/letters is
    treated as an N-Number; a 6-character hex string as an ICAO24. Returns
    both forms plus ``mode`` = ``"n_to_icao"`` or ``"icao_to_n"``. Useful for
    cross-referencing aviation data sources that use different identifiers.
    """
    value = identifier.strip()
    if not value:
        return {"error": "invalid_input", "detail": "empty identifier"}

    # Heuristic: 6-char pure hex with no leading N → ICAO24.
    if len(value) == 6 and all(c in "0123456789abcdefABCDEF" for c in value):
        n = icao_to_nnumber(value.lower())
        if n is None:
            return {
                "error": "out_of_range",
                "detail": f"ICAO24 {value} is outside the US civil range (a00001–adf7c7)",
            }
        return {"mode": "icao_to_n", "icao24": value.lower(), "nnumber": n}

    icao = nnumber_to_icao(value)
    if icao is None:
        return {
            "error": "invalid_nnumber",
            "detail": f"'{value}' is not a valid US N-Number (N1–N99999 with up to 2 alpha suffix)",
        }
    return {"mode": "n_to_icao", "nnumber": value.upper(), "icao24": icao}


# --------------------------------------------------------------------------
# News events
# --------------------------------------------------------------------------


@mcp.tool()
async def get_global_events(
    country_code: str,
    min_goldstein_scale: float = 5.0,
    limit: int = 5,
) -> dict:
    """Fetch recent high-impact GDELT 2.0 events for a country.

    GDELT publishes a new global event export every 15 minutes. Events are
    coded with a Goldstein scale from -10 (destabilizing) to +10 (stabilizing).
    Pass a 3-letter GDELT country code (e.g. ``USA``, ``CHN``, ``RUS``) or
    2-letter FIPS code depending on dataset version.

    Results are sorted by Goldstein scale descending and capped at ``limit``.
    Each event returns actor country codes, Goldstein score, article count,
    and a source URL.
    """
    try:
        result = await fetch_latest_events(
            country_code, min_goldstein=min_goldstein_scale, limit=limit
        )
        return _as_dict(result)
    except Exception as exc:
        logger.exception("get_global_events failed")
        return GdeltError(error="unhandled", detail=str(exc)).model_dump()


# --------------------------------------------------------------------------
# Infrastructure
# --------------------------------------------------------------------------


@mcp.tool()
async def check_network_anomalies(country_or_asn: str) -> dict:
    """Check Cloudflare Radar for BGP and internet-outage anomalies.

    Input formats:

    * 2-letter country code (``US``, ``CN``, ``IR``) → checks BGP hijacks,
      BGP route leaks, and regional outage annotations for that country.
    * ASN string (``AS15169``, ``AS13335``) → checks BGP hijacks and route
      leaks involving that ASN. Outage annotations require a country and are
      omitted for ASN-scoped queries.

    Requires ``CLOUDFLARE_API_TOKEN`` with Radar read permission.
    """
    value = country_or_asn.strip().upper()
    is_asn = value.startswith("AS") and value[2:].isdigit()

    if is_asn:
        hijacks_task = get_bgp_anomalies(asn=value)
        leaks_task = get_bgp_leaks(asn=value)
        hijacks, leaks = await asyncio.gather(hijacks_task, leaks_task)
        return {
            "scope": value,
            "bgp_hijacks": _as_dict(hijacks),
            "bgp_leaks": _as_dict(leaks),
            "outages": None,  # not applicable for ASN scope
        }

    hijacks_task = get_bgp_anomalies(country=value)
    leaks_task = get_bgp_leaks(country=value)
    traffic_task = get_traffic_anomalies(country=value)
    hijacks, leaks, traffic = await asyncio.gather(
        hijacks_task, leaks_task, traffic_task
    )
    return {
        "scope": value,
        "bgp_hijacks": _as_dict(hijacks),
        "bgp_leaks": _as_dict(leaks),
        "outages": _as_dict(traffic),
    }


# --------------------------------------------------------------------------
# Convergence
# --------------------------------------------------------------------------


def _event_weight(event: dict) -> float:
    """Score weighting for a single GDELT event.

    Magnitude of Goldstein × log(1 + article count). Destabilizing events
    (negative Goldstein) contribute positively to the signal.
    """
    import math

    g = abs(float(event.get("goldstein_scale", 0)))
    articles = max(int(event.get("num_articles", 0)), 0)
    return g * math.log1p(articles)


def _outage_weight(outage: dict) -> float:
    """Score weighting for a single outage annotation."""
    cause = (outage.get("outage_cause") or "").lower()
    otype = (outage.get("outage_type") or "").lower()
    if "government" in cause or "directed" in cause or "shutdown" in otype:
        return 5.0  # state-directed shutdowns are a much stronger macro signal
    if "cable" in cause or "power" in cause:
        return 2.5
    return 1.5


@mcp.tool()
async def get_macro_alert(region: str) -> dict:
    """Composite macro-inflection signal for a region.

    Runs three queries concurrently (GDELT events, BGP hijacks, outages) and
    emits a single ``signal_score`` with a one-line ``explanation`` of how the
    number was built. Partial failures are tolerated — if one source errors,
    the tool still returns the others and records the failure under ``errors``.

    Score weighting: ``|Goldstein| × log(1 + article_count)`` for each event;
    outages weighted by cause (government shutdowns dominate). Zero indicates
    a quiet region — the absence of signal is also information.
    """
    region_upper = region.upper()
    events_task = fetch_latest_events(region_upper, min_goldstein=5.0, limit=5)
    bgp_task = get_bgp_anomalies(country=region_upper)
    traffic_task = get_traffic_anomalies(country=region_upper)

    events_result, bgp_result, traffic_result = await asyncio.gather(
        events_task, bgp_task, traffic_task, return_exceptions=True
    )

    errors: dict[str, str] = {}
    event_score = 0.0
    bgp_count = 0
    outage_score = 0.0
    event_payload: dict = {}
    bgp_payload: dict = {}
    traffic_payload: dict = {}
    event_count = 0
    traffic_count = 0

    if isinstance(events_result, BaseException):
        errors["events"] = str(events_result)
    elif isinstance(events_result, GdeltError):
        errors["events"] = events_result.error
        event_payload = events_result.model_dump()
    elif isinstance(events_result, GdeltEventBatch):
        event_payload = events_result.model_dump()
        for ev in event_payload["events"]:
            event_score += _event_weight(ev)
        event_count = len(event_payload["events"])

    if isinstance(bgp_result, BaseException):
        errors["bgp"] = str(bgp_result)
    elif isinstance(bgp_result, InfraError):
        errors["bgp"] = bgp_result.error
        bgp_payload = bgp_result.model_dump()
    elif isinstance(bgp_result, BGPAnomalyReport):
        bgp_payload = bgp_result.model_dump()
        bgp_count = len(bgp_payload["anomalies"])

    if isinstance(traffic_result, BaseException):
        errors["traffic"] = str(traffic_result)
    elif isinstance(traffic_result, InfraError):
        errors["traffic"] = traffic_result.error
        traffic_payload = traffic_result.model_dump()
    elif isinstance(traffic_result, TrafficAnomalyReport):
        traffic_payload = traffic_result.model_dump()
        for out in traffic_payload["anomalies"]:
            outage_score += _outage_weight(out)
        traffic_count = len(traffic_payload["anomalies"])

    signal_score = round(event_score + bgp_count * 1.0 + outage_score, 2)

    explanation_parts = []
    if event_count:
        explanation_parts.append(
            f"{event_count} GDELT events (weighted score {event_score:.1f})"
        )
    if bgp_count:
        explanation_parts.append(f"{bgp_count} BGP hijack(s)")
    if traffic_count:
        explanation_parts.append(
            f"{traffic_count} outage annotation(s) (weighted score {outage_score:.1f})"
        )
    if not explanation_parts:
        explanation = "No macro signal detected — all sources quiet or unavailable"
    else:
        explanation = "Signal from " + " + ".join(explanation_parts)

    return {
        "region": region_upper,
        "signal_score": signal_score,
        "explanation": explanation,
        "event_count": event_count,
        "bgp_anomaly_count": bgp_count,
        "outage_count": traffic_count,
        "events": event_payload,
        "bgp": bgp_payload,
        "outages": traffic_payload,
        "errors": errors,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> None:
    """Entry point for the MCP server (stdio transport)."""
    logger.info("Starting Global Sentinel MCP server")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
