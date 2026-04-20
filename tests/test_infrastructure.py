"""Tests for the infrastructure (Cloudflare Radar) module."""

from __future__ import annotations

import pytest
import respx

from global_sentinel_mcp.infrastructure.client import (
    _cache,
    get_bgp_anomalies,
    get_bgp_leaks,
    get_traffic_anomalies,
)
from global_sentinel_mcp.infrastructure.models import (
    BGPAnomalyReport,
    InfraError,
    TrafficAnomalyReport,
)


@pytest.fixture(autouse=True)
async def _clear_cache():
    await _cache.clear()


async def test_get_bgp_anomalies_happy_path(
    cloudflare_mock: respx.MockRouter, monkeypatch
):
    """Mocked /bgp/hijacks/events → typed BGPAnomalyReport."""
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "test-token")

    cloudflare_mock.get("/client/v4/radar/bgp/hijacks/events").respond(
        200,
        json={
            "result": {
                "events": [
                    {
                        "id": "hij-1",
                        "detected_ts": "2026-04-17T00:00:00Z",
                        "hijacker_prefix": "1.2.3.0/24",
                        "hijacker_asn": 64512,
                        "confidence_score": "HIGH",
                    }
                ]
            }
        },
    )

    result = await get_bgp_anomalies(country="US")
    assert isinstance(result, BGPAnomalyReport)
    assert result.kind == "hijacks"
    assert result.scope == "country US"
    assert len(result.anomalies) == 1
    event = result.anomalies[0]
    assert event.id == "hij-1"
    assert event.event_type == "hijacks"
    assert event.prefix == "1.2.3.0/24"
    assert event.hijacker_asn == 64512
    assert event.confidence == "HIGH"


async def test_get_bgp_leaks_happy_path(
    cloudflare_mock: respx.MockRouter, monkeypatch
):
    """Mocked /bgp/leaks/events → BGPAnomalyReport with kind='leaks'."""
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "test-token")

    cloudflare_mock.get("/client/v4/radar/bgp/leaks/events").respond(
        200,
        json={
            "result": {
                "events": [
                    {
                        "id": "leak-1",
                        "event_time": "2026-04-17T12:00:00Z",
                        "prefix": "10.0.0.0/8",
                        "leaker_asn": 65001,
                    }
                ]
            }
        },
    )

    result = await get_bgp_leaks(asn="AS65001")
    assert isinstance(result, BGPAnomalyReport)
    assert result.kind == "leaks"
    assert result.scope == "ASN AS65001"
    assert len(result.anomalies) == 1
    assert result.anomalies[0].origin_asn == 65001


async def test_get_bgp_anomalies_missing_token(monkeypatch):
    """Missing CLOUDFLARE_API_TOKEN → InfraError."""
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)

    result = await get_bgp_anomalies(country="US")
    assert isinstance(result, InfraError)
    assert result.error == "credentials_missing"


async def test_get_traffic_anomalies_happy_path(
    cloudflare_mock: respx.MockRouter, monkeypatch
):
    """Mocked /annotations/outages → TrafficAnomalyReport with typed OutageAnnotation."""
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "test-token")

    cloudflare_mock.get("/client/v4/radar/annotations/outages").respond(
        200,
        json={
            "result": {
                "annotations": [
                    {
                        "id": "out-1",
                        "locations": ["US"],
                        "asns": [7018],
                        "eventType": "OUTAGE",
                        "startDate": "2026-04-17T00:00:00Z",
                        "endDate": "2026-04-17T02:00:00Z",
                        "outage": {
                            "outageCause": "CABLE_CUT",
                            "outageType": "PARTIAL",
                        },
                        "description": "Submarine cable cut",
                        "scope": "REGIONAL",
                    }
                ]
            }
        },
    )

    result = await get_traffic_anomalies("US")
    assert isinstance(result, TrafficAnomalyReport)
    assert result.country == "US"
    assert len(result.anomalies) == 1
    outage = result.anomalies[0]
    assert outage.id == "out-1"
    assert outage.locations == ["US"]
    assert outage.asns == [7018]
    assert outage.event_type == "OUTAGE"
    assert outage.outage_cause == "CABLE_CUT"
    assert outage.outage_type == "PARTIAL"
    assert outage.scope == "REGIONAL"


async def test_get_traffic_anomalies_http_error(
    cloudflare_mock: respx.MockRouter, monkeypatch
):
    """Mocked 500 → InfraError."""
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "test-token")

    cloudflare_mock.get("/client/v4/radar/annotations/outages").respond(500)

    result = await get_traffic_anomalies("US")
    assert isinstance(result, InfraError)
    assert "500" in result.error
