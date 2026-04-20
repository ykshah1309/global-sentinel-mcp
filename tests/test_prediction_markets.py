"""Tests for the prediction_markets module."""

from __future__ import annotations

import pytest
import respx

from global_sentinel_mcp.prediction_markets.client import (
    _cache,
    get_event_probability,
    search_events,
)
from global_sentinel_mcp.prediction_markets.models import (
    MarketOdds,
    PredictionError,
    PredictionSearchResult,
)


@pytest.fixture(autouse=True)
async def _clear_cache():
    """Clear the TTL cache between tests."""
    await _cache.clear()


def _event_payload(event_id: str = "evt-1") -> dict:
    """Shape of a Polymarket Gamma event as actually served (April 2026)."""
    return {
        "id": event_id,
        "slug": "will-x-happen-2026",
        "title": "Will X happen?",
        "endDate": "2026-12-31T00:00:00Z",
        "volume": 50000,
        "markets": [
            {
                # Gamma serves these as JSON-encoded strings, not arrays.
                "outcomes": "[\"Yes\", \"No\"]",
                "outcomePrices": "[\"0.73\", \"0.27\"]",
            }
        ],
    }


async def test_search_events_happy_path(polymarket_mock: respx.MockRouter):
    """Mocked 200 → parsed PredictionSearchResult with real Gamma shape."""
    polymarket_mock.get("/events").respond(200, json=[_event_payload()])

    result = await search_events("X happen", limit=5)
    assert isinstance(result, PredictionSearchResult)
    assert result.query == "X happen"
    assert len(result.results) == 1
    odds = result.results[0]
    assert odds.event_id == "evt-1"
    assert odds.slug == "will-x-happen-2026"
    assert odds.probability_pct == pytest.approx(73.0)
    assert odds.volume_usd == pytest.approx(50000.0)


async def test_search_events_picks_yes_not_first(polymarket_mock: respx.MockRouter):
    """If 'Yes' is not index 0, the parser still picks its price."""
    event = _event_payload()
    event["markets"][0]["outcomes"] = "[\"No\", \"Yes\"]"
    event["markets"][0]["outcomePrices"] = "[\"0.40\", \"0.60\"]"
    polymarket_mock.get("/events").respond(200, json=[event])

    result = await search_events("x", limit=1)
    assert isinstance(result, PredictionSearchResult)
    assert result.results[0].probability_pct == pytest.approx(60.0)


async def test_search_events_error_429(polymarket_mock: respx.MockRouter):
    """Mocked 429 → returns PredictionError, not an exception."""
    polymarket_mock.get("/events").respond(429)

    result = await search_events("anything")
    assert isinstance(result, PredictionError)
    assert "429" in result.error


async def test_get_event_probability_happy_path(polymarket_mock: respx.MockRouter):
    """GET /events/{id} → MarketOdds."""
    polymarket_mock.get("/events/evt-42").respond(200, json=_event_payload("evt-42"))

    result = await get_event_probability("evt-42")
    assert isinstance(result, MarketOdds)
    assert result.event_id == "evt-42"
    assert result.probability_pct == pytest.approx(73.0)
