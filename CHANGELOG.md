# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2026-04-20

### Added

- `mcp-name` marker in README for MCP registry PyPI-ownership validation.

### Changed

- CI: install `dev` extra explicitly so pytest/ruff/mypy reach the runner env.
- Bumped `actions/checkout` (4 → 6) and `astral-sh/setup-uv` (3 → 7).

## [0.1.0] - 2026-04-19

Initial public release.

### Added

- **Seven MCP tools** over four public data feeds:
  - `get_prediction_odds` — Polymarket event search, ranked by volume.
  - `get_prediction_event_by_id` — single-event lookup by id or slug.
  - `lookup_aircraft_state` — OpenSky state vector by N-Number or ICAO24 hex.
  - `convert_nnumber` — offline FAA N-Number ↔ ICAO24 hex conversion.
  - `get_global_events` — GDELT 2.0 events for a country, ranked by Goldstein scale.
  - `check_network_anomalies` — Cloudflare Radar BGP hijacks, leaks, and regional outage annotations.
  - `get_macro_alert` — composite convergence signal combining GDELT events and Cloudflare outages.
- Fully async architecture: `httpx.AsyncClient` with `AsyncHTTPTransport(retries=3)`
  and a shared client factory that stamps a consistent `User-Agent`.
- Pydantic v2 models for every input, output, and typed error; typed
  `BGPEvent` and `OutageAnnotation` for Cloudflare data.
- Shared TTL cache with `asyncio.Lock`, tuned per source (Polymarket 60s, GDELT
  300s, OpenSky 10s, Cloudflare 120s).
- Two-layer GDELT cache: one entry for the parsed 5 MB export frame (shared
  across countries) and one for the per-query filtered result.
- OpenSky authentication: OAuth2 client-credentials (post-2025 migration) with
  automatic token refresh, plus Basic Auth fallback for legacy accounts and
  anonymous access for public endpoints.
- Pure-Python FAA N-Number ↔ ICAO24 converter with FAA registry scrape fallback
  (three progressively-permissive regex patterns).
- Graceful degradation in `get_macro_alert` via `asyncio.gather(..., return_exceptions=True)`,
  composite score weighting Goldstein × `log1p(articles)`, and human-readable
  explanation string.
- `LOG_LEVEL` environment variable support for structured stderr logging.
- PEP 561 `py.typed` marker — downstream consumers get full type information.
- CI pipeline with pytest (19 tests, respx-mocked), ruff, and mypy on a
  Python 3.11 / 3.12 / 3.13 matrix.
- PyPI OIDC trusted-publishing workflow (no long-lived tokens).
- MCP registry `server.json` manifest and example `claude_desktop_config.example.json`.
