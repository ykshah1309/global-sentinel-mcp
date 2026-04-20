"""Async client for Cloudflare Radar — BGP events + internet outage annotations.

Endpoint paths verified against Cloudflare's API reference (April 2026):

* ``/radar/bgp/hijacks/events`` — detected BGP hijacks
* ``/radar/bgp/leaks/events``   — detected BGP route leaks
* ``/radar/annotations/outages`` — regional internet outage annotations
  (formerly "traffic anomalies", renamed by Cloudflare in 2024).

All three return ``{"result": {"events"|"annotations": [...]}}``.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx

from .._cache import CLOUDFLARE_TTL, TTLCache
from .._http import build_client
from .models import (
    BGPAnomalyReport,
    BGPEvent,
    InfraError,
    OutageAnnotation,
    TrafficAnomalyReport,
)

logger = logging.getLogger(__name__)

CF_BASE = "https://api.cloudflare.com/client/v4/radar"

_cache = TTLCache(ttl=CLOUDFLARE_TTL)


def _auth_headers() -> dict[str, str] | None:
    token = os.environ.get("CLOUDFLARE_API_TOKEN")
    if not token:
        return None
    return {"Authorization": f"Bearer {token}"}


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_bgp_event(raw: dict, kind: str) -> BGPEvent:
    return BGPEvent(
        id=raw.get("id") or raw.get("event_id"),
        event_type=kind,
        detected_ts=raw.get("detected_ts") or raw.get("event_time"),
        prefix=raw.get("prefix") or raw.get("hijacker_prefix"),
        origin_asn=_as_int(raw.get("origin_asn") or raw.get("leaker_asn")),
        hijacker_asn=_as_int(raw.get("hijacker_asn")),
        confidence=raw.get("confidence") or raw.get("confidence_score"),
    )


def _parse_outage(raw: dict) -> OutageAnnotation:
    outage = raw.get("outage") or {}
    locations = raw.get("locations") or []
    asns = [_as_int(a) for a in (raw.get("asns") or [])]
    return OutageAnnotation(
        id=raw.get("id"),
        locations=[str(loc) for loc in locations],
        asns=[a for a in asns if a is not None],
        event_type=raw.get("eventType"),
        outage_cause=outage.get("outageCause"),
        outage_type=outage.get("outageType"),
        start_date=raw.get("startDate"),
        end_date=raw.get("endDate"),
        description=raw.get("description"),
        linked_url=raw.get("linkedUrl"),
        scope=raw.get("scope"),
    )


async def _get_bgp(
    kind: str,
    *,
    asn: str | None = None,
    country: str | None = None,
) -> BGPAnomalyReport | InfraError:
    """Fetch BGP events of a given kind ('hijacks' or 'leaks')."""
    if kind not in ("hijacks", "leaks"):
        return InfraError(error="invalid_kind", detail=f"kind must be hijacks or leaks, got {kind}")

    headers = _auth_headers()
    if headers is None:
        return InfraError(
            error="credentials_missing",
            detail="Set CLOUDFLARE_API_TOKEN in the environment",
        )

    params: dict[str, str] = {}
    scope = "global"
    if asn:
        normalized = asn.upper().removeprefix("AS")
        params["involvedAsn"] = normalized
        scope = f"ASN {asn.upper()}"
    if country:
        params["location"] = country.upper()
        scope = f"country {country.upper()}"

    cache_key = f"bgp:{kind}:{scope}"
    cached = await _cache.get(cache_key)
    if cached is not None:
        logger.debug("cloudflare cache hit: %s", cache_key)
        return cached

    try:
        async with build_client(timeout=15.0, headers=headers) as client:
            resp = await client.get(f"{CF_BASE}/bgp/{kind}/events", params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        return InfraError(error=f"http_{exc.response.status_code}", detail=str(exc))
    except httpx.HTTPError as exc:
        return InfraError(error="request_failed", detail=str(exc))

    events_raw = (data.get("result") or {}).get("events") or []
    report = BGPAnomalyReport(
        scope=scope,
        kind=kind,
        anomalies=[_parse_bgp_event(e, kind) for e in events_raw],
        fetched_at=datetime.now(timezone.utc),
    )
    await _cache.set(cache_key, report)
    return report


async def get_bgp_anomalies(
    asn: str | None = None,
    country: str | None = None,
) -> BGPAnomalyReport | InfraError:
    """Fetch BGP hijack events. Use get_bgp_leaks for route-leak events."""
    return await _get_bgp("hijacks", asn=asn, country=country)


async def get_bgp_leaks(
    asn: str | None = None,
    country: str | None = None,
) -> BGPAnomalyReport | InfraError:
    """Fetch BGP route-leak events from Cloudflare Radar."""
    return await _get_bgp("leaks", asn=asn, country=country)


async def get_traffic_anomalies(
    country: str,
) -> TrafficAnomalyReport | InfraError:
    """Fetch regional internet outage annotations for a country.

    Cloudflare renamed "traffic anomalies" to "outage annotations" in 2024;
    this function queries ``/radar/annotations/outages``.
    """
    headers = _auth_headers()
    if headers is None:
        return InfraError(
            error="credentials_missing",
            detail="Set CLOUDFLARE_API_TOKEN in the environment",
        )
    if not country:
        return InfraError(
            error="invalid_input",
            detail="country is required for traffic anomaly queries",
        )

    country_upper = country.upper()
    cache_key = f"outages:{country_upper}"
    cached = await _cache.get(cache_key)
    if cached is not None:
        logger.debug("cloudflare cache hit: %s", cache_key)
        return cached

    try:
        async with build_client(timeout=15.0, headers=headers) as client:
            resp = await client.get(
                f"{CF_BASE}/annotations/outages",
                params={"location": country_upper},
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        return InfraError(error=f"http_{exc.response.status_code}", detail=str(exc))
    except httpx.HTTPError as exc:
        return InfraError(error="request_failed", detail=str(exc))

    annotations_raw = (data.get("result") or {}).get("annotations") or []
    report = TrafficAnomalyReport(
        country=country_upper,
        anomalies=[_parse_outage(a) for a in annotations_raw],
        fetched_at=datetime.now(timezone.utc),
    )
    await _cache.set(cache_key, report)
    return report
