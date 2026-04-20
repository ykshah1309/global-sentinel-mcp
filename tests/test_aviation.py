"""Tests for the aviation module (converter + client)."""

from __future__ import annotations

import pytest
import respx

from global_sentinel_mcp.aviation.client import (
    _state_cache,
    get_state_by_icao,
    lookup_aircraft,
)
from global_sentinel_mcp.aviation.converter import icao_to_nnumber, nnumber_to_icao
from global_sentinel_mcp.aviation.models import AircraftState, AviationError


@pytest.fixture(autouse=True)
async def _clear_state_cache():
    await _state_cache.clear()


# ---------- converter tests ----------


def test_nnumber_to_icao_n12345():
    """N12345 → known-correct ICAO24 hex."""
    result = nnumber_to_icao("N12345")
    assert result is not None
    back = icao_to_nnumber(result)
    assert back == "N12345"


def test_nnumber_roundtrip_samples():
    """Roundtrip a variety of N-Number formats."""
    samples = ["N1", "N9", "N10", "N1A", "N12AB", "N123", "N1234A", "N99999"]
    for nn in samples:
        icao = nnumber_to_icao(nn)
        assert icao is not None, f"nnumber_to_icao({nn!r}) returned None"
        back = icao_to_nnumber(icao)
        assert back == nn, f"Roundtrip failed: {nn} → {icao} → {back}"


def test_nnumber_to_icao_invalid():
    """Invalid inputs return None, not raise."""
    assert nnumber_to_icao("") is None
    assert nnumber_to_icao("N0") is None
    assert nnumber_to_icao("NABCDE") is None
    assert nnumber_to_icao("N123456") is None


# ---------- client tests ----------


def _state_payload(icao: str = "a061d9") -> dict:
    return {
        "time": 1700000000,
        "states": [
            [
                icao,
                "UAL123 ",
                "United States",
                1700000000,
                1700000000,
                -73.78,
                40.64,
                10000.0,
                False,
                250.0,
                180.0,
                0.0,
                None,
                10200.0,
                "1234",
                False,
                0,
            ]
        ],
    }


async def test_get_state_happy_path(opensky_mock: respx.MockRouter, monkeypatch):
    """Mocked 200 → parsed AircraftState (anonymous path)."""
    monkeypatch.delenv("OPENSKY_CLIENT_ID", raising=False)
    monkeypatch.delenv("OPENSKY_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("OPENSKY_USERNAME", raising=False)
    monkeypatch.delenv("OPENSKY_PASSWORD", raising=False)

    opensky_mock.get("/api/states/all").respond(200, json=_state_payload())

    result = await get_state_by_icao("a061d9")
    assert isinstance(result, AircraftState)
    assert result.icao24 == "a061d9"
    assert result.callsign == "UAL123"
    assert result.on_ground is False
    assert result.velocity_ms == pytest.approx(250.0)


async def test_get_state_rate_limited(opensky_mock: respx.MockRouter, monkeypatch):
    """Mocked 429 → returns AviationError with retry info."""
    monkeypatch.delenv("OPENSKY_CLIENT_ID", raising=False)
    monkeypatch.delenv("OPENSKY_CLIENT_SECRET", raising=False)

    opensky_mock.get("/api/states/all").respond(429)

    result = await get_state_by_icao("a061d9")
    assert isinstance(result, AviationError)
    assert result.error == "rate_limited"
    assert result.retry_after_seconds == 60


async def test_get_state_not_found(opensky_mock: respx.MockRouter, monkeypatch):
    """OpenSky returns states=None → AviationError 'not_found'."""
    monkeypatch.delenv("OPENSKY_CLIENT_ID", raising=False)

    opensky_mock.get("/api/states/all").respond(
        200, json={"time": 1700000000, "states": None}
    )

    result = await get_state_by_icao("deadbe")
    assert isinstance(result, AviationError)
    assert result.error == "not_found"


async def test_lookup_aircraft_resolves_nnumber(
    opensky_mock: respx.MockRouter, monkeypatch
):
    """lookup_aircraft('N12345') → N-Number math resolves ICAO24, then fetches state."""
    monkeypatch.delenv("OPENSKY_CLIENT_ID", raising=False)
    monkeypatch.delenv("OPENSKY_USERNAME", raising=False)

    expected_icao = nnumber_to_icao("N12345")
    assert expected_icao is not None

    route = opensky_mock.get("/api/states/all").respond(
        200, json=_state_payload(expected_icao)
    )

    result = await lookup_aircraft("N12345")
    assert isinstance(result, AircraftState)
    assert result.icao24 == expected_icao
    # Verify the icao24 was actually sent as a query param.
    assert route.called
    called_url = str(route.calls.last.request.url)
    assert f"icao24={expected_icao}" in called_url


async def test_lookup_aircraft_accepts_raw_icao(
    opensky_mock: respx.MockRouter, monkeypatch
):
    """A 6-hex input bypasses the converter and queries directly."""
    monkeypatch.delenv("OPENSKY_CLIENT_ID", raising=False)

    opensky_mock.get("/api/states/all").respond(200, json=_state_payload("a061d9"))

    result = await lookup_aircraft("A061D9")
    assert isinstance(result, AircraftState)
    assert result.icao24 == "a061d9"
