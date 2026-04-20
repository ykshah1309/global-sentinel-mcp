"""Async client for GDELT 2.0 event data.

Perf note: every 15 minutes GDELT publishes one ~5 MB export zip. We cache the
**parsed DataFrame** keyed by its export URL, so concurrent queries for
different countries within the same 5-minute window pay the download+parse cost
exactly once.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx
import pandas as pd

from .._cache import GDELT_TTL, TTLCache
from .._http import build_client
from .models import GdeltError, GdeltEvent, GdeltEventBatch
from .parser import parse_export_zip

logger = logging.getLogger(__name__)

LASTUPDATE_URL = "http://data.gdeltproject.org/gdeltv2/lastupdate.txt"

# Two caches: one for raw parsed frames (shared across all country queries),
# one for final filtered batches (keyed by country + threshold + limit).
_frame_cache = TTLCache(ttl=GDELT_TTL)
_batch_cache = TTLCache(ttl=GDELT_TTL)


async def _latest_export_url(client: httpx.AsyncClient) -> str | None:
    resp = await client.get(LASTUPDATE_URL)
    resp.raise_for_status()
    for line in resp.text.strip().splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[2].endswith(".export.CSV.zip"):
            return parts[2]
    return None


async def _load_frame() -> pd.DataFrame | GdeltError:
    """Return the current GDELT export as a DataFrame, using a shared TTL cache."""
    try:
        async with build_client(timeout=30.0) as client:
            export_url = await _latest_export_url(client)
            if export_url is None:
                return GdeltError(
                    error="no_export_url",
                    detail="Could not find .export.CSV.zip in lastupdate.txt",
                )

            cached = await _frame_cache.get(export_url)
            if cached is not None:
                logger.debug("gdelt frame cache hit: %s", export_url)
                return cached

            zip_resp = await client.get(export_url)
            zip_resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        return GdeltError(error=f"http_{exc.response.status_code}", detail=str(exc))
    except httpx.HTTPError as exc:
        return GdeltError(error="request_failed", detail=str(exc))

    df = parse_export_zip(zip_resp.content)
    await _frame_cache.set(export_url, df)
    return df


async def fetch_latest_events(
    country_code: str,
    min_goldstein: float = 5.0,
    limit: int = 5,
) -> GdeltEventBatch | GdeltError:
    """Fetch the latest GDELT 2.0 events for a country, sorted by Goldstein scale descending."""
    country_upper = country_code.upper()
    cache_key = f"gdelt:{country_upper}:{min_goldstein}:{limit}"
    cached = await _batch_cache.get(cache_key)
    if cached is not None:
        return cached

    frame_or_err = await _load_frame()
    if isinstance(frame_or_err, GdeltError):
        return frame_or_err
    df = frame_or_err

    if df.empty:
        batch = GdeltEventBatch(
            country_code=country_upper,
            events=[],
            fetched_at=datetime.now(timezone.utc),
        )
        await _batch_cache.set(cache_key, batch)
        return batch

    mask = (df["Actor1CountryCode"] == country_upper) | (
        df["Actor2CountryCode"] == country_upper
    )
    filtered = df[mask]
    filtered = filtered[filtered["GoldsteinScale"].notna()]
    filtered = filtered[filtered["GoldsteinScale"] >= min_goldstein]
    filtered = filtered.sort_values("GoldsteinScale", ascending=False).head(limit)

    events: list[GdeltEvent] = []
    for _, row in filtered.iterrows():
        events.append(
            GdeltEvent(
                global_event_id=str(row.get("GLOBALEVENTID", "")),
                event_date=str(row.get("SQLDATE", "")),
                actor1_country=row.get("Actor1CountryCode") or None,
                actor2_country=row.get("Actor2CountryCode") or None,
                goldstein_scale=float(row["GoldsteinScale"]),
                num_articles=int(row.get("NumArticles", 0)),
                source_url=str(row.get("SOURCEURL", "")),
            )
        )

    batch = GdeltEventBatch(
        country_code=country_upper,
        events=events,
        fetched_at=datetime.now(timezone.utc),
    )
    await _batch_cache.set(cache_key, batch)
    return batch


# Backwards-compatible alias used by tests that clear the cache between runs.
_cache = _batch_cache
