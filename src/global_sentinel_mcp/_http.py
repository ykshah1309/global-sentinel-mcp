"""Shared httpx.AsyncClient factory with transport-level retries.

Every data-source client calls `build_client()` to get a pre-configured
AsyncClient. Using a shared factory means retry policy and User-Agent stay
consistent, and we can add tracing or metrics in exactly one place later.
"""

from __future__ import annotations

import httpx

from . import __version__

USER_AGENT = f"global-sentinel-mcp/{__version__} (+https://github.com/ykshah1309/global-sentinel-mcp)"


def build_client(
    *,
    timeout: float = 15.0,
    auth: httpx.Auth | tuple[str, str] | None = None,
    headers: dict[str, str] | None = None,
    retries: int = 3,
) -> httpx.AsyncClient:
    """Construct an AsyncClient with exponential-backoff retries on connection errors.

    httpx's transport-level ``retries`` only retries on connection-layer failures
    (DNS, connect timeout, reset). Application-level retries for 429/5xx live in
    each client where the semantics are source-specific.
    """
    merged_headers = {"User-Agent": USER_AGENT}
    if headers:
        merged_headers.update(headers)

    transport = httpx.AsyncHTTPTransport(retries=retries)
    return httpx.AsyncClient(
        timeout=timeout,
        auth=auth,
        headers=merged_headers,
        transport=transport,
        follow_redirects=True,
    )
