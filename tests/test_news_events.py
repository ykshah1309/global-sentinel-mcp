"""Tests for the news_events (GDELT) module."""

from __future__ import annotations

import pytest
import respx

from global_sentinel_mcp.news_events.client import _cache, fetch_latest_events
from global_sentinel_mcp.news_events.models import GdeltError, GdeltEventBatch


@pytest.fixture(autouse=True)
async def _clear_cache():
    await _cache.clear()


async def test_fetch_latest_events_happy_path(gdelt_mock: respx.MockRouter):
    """Mocked GDELT export → parsed GdeltEventBatch with correct fields."""
    result = await fetch_latest_events("US", min_goldstein=5.0, limit=5)
    assert isinstance(result, GdeltEventBatch)
    assert result.country_code == "US"
    assert len(result.events) >= 1
    # The test fixture has GoldsteinScale 7.0, 6.0, 5.0 — all ≥ 5.0
    for event in result.events:
        assert event.goldstein_scale >= 5.0
        assert event.source_url.startswith("https://example.com/")
    # Should be sorted descending
    scales = [e.goldstein_scale for e in result.events]
    assert scales == sorted(scales, reverse=True)


async def test_fetch_latest_events_http_error():
    """Mocked 500 → returns GdeltError, not an exception."""
    with respx.mock as mock:
        mock.get("http://data.gdeltproject.org/gdeltv2/lastupdate.txt").respond(500)
        result = await fetch_latest_events("US")
    assert isinstance(result, GdeltError)
    assert "500" in result.error
