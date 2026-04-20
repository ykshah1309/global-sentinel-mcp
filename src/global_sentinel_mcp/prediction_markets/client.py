"""Async client for the Polymarket Gamma API.

Gamma API quirks (confirmed against live responses, April 2026):

* ``/events`` returns events whose ``markets[]`` elements hold ``outcomes`` and
  ``outcomePrices`` as **JSON-encoded strings** (not real arrays), e.g.
  ``"outcomes": "[\\"Yes\\", \\"No\\"]"``.
* Event-level ``volume`` is a plain number (USDC units).
* Dates are ISO 8601 with trailing ``Z``.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import httpx

from .._cache import POLYMARKET_TTL, TTLCache
from .._http import build_client
from .models import MarketOdds, PredictionError, PredictionSearchResult

logger = logging.getLogger(__name__)

GAMMA_BASE = "https://gamma-api.polymarket.com"

_cache = TTLCache(ttl=POLYMARKET_TTL)


def _parse_probability(outcomes_raw: str | None, prices_raw: str | None) -> float:
    """Pick the 'Yes' price from Gamma's JSON-encoded outcome/price strings.

    Falls back to the first-listed outcome's price if no 'Yes' label is present
    (e.g. multi-outcome markets). Returns 0.0 on any parse failure.
    """
    if not outcomes_raw or not prices_raw:
        return 0.0
    try:
        outcomes = json.loads(outcomes_raw)
        prices = json.loads(prices_raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return 0.0
    if not isinstance(outcomes, list) or not isinstance(prices, list):
        return 0.0
    if len(outcomes) != len(prices):
        return 0.0

    yes_idx = next(
        (i for i, o in enumerate(outcomes) if isinstance(o, str) and o.strip().lower() == "yes"),
        0,
    )
    try:
        return float(prices[yes_idx]) * 100.0
    except (TypeError, ValueError, IndexError):
        return 0.0


def _parse_end_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _event_to_odds(event: dict) -> MarketOdds:
    """Flatten an event + its primary market into a MarketOdds record."""
    markets = event.get("markets") or []
    probability = 0.0
    if markets:
        primary = markets[0]
        probability = _parse_probability(
            primary.get("outcomes"), primary.get("outcomePrices")
        )

    # Polymarket reports ``volume`` in USDC (1 USDC = 1 USD). Event-level
    # volume is already aggregated across the event's markets.
    try:
        volume = float(event.get("volume") or 0.0)
    except (TypeError, ValueError):
        volume = 0.0

    return MarketOdds(
        event_id=str(event.get("id", "")),
        slug=event.get("slug"),
        title=event.get("title", ""),
        probability_pct=round(probability, 2),
        volume_usd=volume,
        end_date=_parse_end_date(event.get("endDate")),
    )


async def search_events(
    query: str, limit: int = 10
) -> PredictionSearchResult | PredictionError:
    """Search Polymarket for active events matching ``query``."""
    cache_key = f"search:{query}:{limit}"
    cached = await _cache.get(cache_key)
    if cached is not None:
        logger.debug("polymarket cache hit: %s", cache_key)
        return cached

    try:
        async with build_client(timeout=10.0) as client:
            resp = await client.get(
                f"{GAMMA_BASE}/events",
                params={"title": query, "active": "true", "limit": limit},
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        return PredictionError(
            error=f"http_{exc.response.status_code}", detail=str(exc)
        )
    except httpx.HTTPError as exc:
        return PredictionError(error="request_failed", detail=str(exc))

    if not isinstance(data, list):
        return PredictionError(
            error="unexpected_response",
            detail=f"Expected list from /events, got {type(data).__name__}",
        )

    result = PredictionSearchResult(
        query=query,
        results=[_event_to_odds(e) for e in data],
        fetched_at=datetime.now(timezone.utc),
    )
    await _cache.set(cache_key, result)
    return result


async def get_event_probability(
    event_id: str,
) -> MarketOdds | PredictionError:
    """Fetch odds for a specific Polymarket event by id or slug."""
    cache_key = f"event:{event_id}"
    cached = await _cache.get(cache_key)
    if cached is not None:
        logger.debug("polymarket cache hit: %s", cache_key)
        return cached

    try:
        async with build_client(timeout=10.0) as client:
            resp = await client.get(f"{GAMMA_BASE}/events/{event_id}")
            resp.raise_for_status()
            event = resp.json()
    except httpx.HTTPStatusError as exc:
        return PredictionError(
            error=f"http_{exc.response.status_code}", detail=str(exc)
        )
    except httpx.HTTPError as exc:
        return PredictionError(error="request_failed", detail=str(exc))

    if not isinstance(event, dict):
        return PredictionError(
            error="unexpected_response",
            detail=f"Expected dict from /events/{event_id}, got {type(event).__name__}",
        )

    result = _event_to_odds(event)
    await _cache.set(cache_key, result)
    return result
