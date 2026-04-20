"""Async-safe TTL cache shared across all data-source clients."""

from __future__ import annotations

import asyncio
import time
from typing import Any

# Per-source TTL defaults — exported so clients can import one symbol.
POLYMARKET_TTL = 60      # seconds; Polymarket prices move fast
GDELT_TTL = 300          # seconds; GDELT publishes every 15 min, 5-min cache is safe
OPENSKY_TTL = 10         # seconds; ADS-B is real-time, cache briefly to absorb bursts
CLOUDFLARE_TTL = 120     # seconds; Radar data is aggregated, 2-min cache is fine


class TTLCache:
    """Simple async-safe TTL cache backed by a dict of (value, monotonic_ts) tuples."""

    __slots__ = ("_ttl", "_store", "_lock")

    def __init__(self, ttl: int) -> None:
        self._ttl = ttl
        self._store: dict[str, tuple[Any, float]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Any | None:
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, ts = entry
            if time.monotonic() - ts > self._ttl:
                del self._store[key]
                return None
            return value

    async def set(self, key: str, value: Any) -> None:
        async with self._lock:
            self._store[key] = (value, time.monotonic())

    async def clear(self) -> None:
        async with self._lock:
            self._store.clear()
