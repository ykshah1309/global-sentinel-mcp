# global-sentinel-mcp

<!-- mcp-name: io.github.ykshah1309/global-sentinel-mcp -->

An async MCP server unifying **prediction markets, global news events, aviation state,
and internet-infrastructure telemetry** into one alternative-data layer for macro and
financial analysis.

[![PyPI version](https://img.shields.io/pypi/v/global-sentinel-mcp)](https://pypi.org/project/global-sentinel-mcp/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://python.org)
[![MIT License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![CI](https://github.com/ykshah1309/global-sentinel-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/ykshah1309/global-sentinel-mcp/actions/workflows/ci.yml)
[![Publish](https://github.com/ykshah1309/global-sentinel-mcp/actions/workflows/publish.yml/badge.svg)](https://github.com/ykshah1309/global-sentinel-mcp/actions/workflows/publish.yml)

Status: **Beta** — ready for production use; public API may still shift before 1.0.

---

## Why this exists

Alternative data — prediction-market odds, real-time geopolitical event streams,
live aviation transponder data, and internet-infrastructure telemetry — is
increasingly central to macro and financial analysis. Each source has its own
API shape, authentication model, and update cadence, making it tedious to wire
them together for every new project.

`global-sentinel-mcp` closes that gap by wrapping four public data feeds behind
a single Model Context Protocol (MCP) interface. An LLM agent can ask
probability, event, aviation-state, and internet-telemetry questions in one
place, without knowing the upstream API details. It also exposes a composite
**macro alert** tool that fuses news events and outage annotations into one
convergence signal with a human-readable explanation.

The server is fully async (`httpx.AsyncClient` with retry transport), returns
typed Pydantic v2 models for every response and error, ships a TTL cache per
source to stay within upstream rate limits, and installs in one command over
stdio — no web server required.

---

## Available Tools

| Tool | Data Source | What it returns |
|---|---|---|
| `get_prediction_odds` | Polymarket | Ranked event odds (probability %, volume, end date) for a query |
| `get_prediction_event_by_id` | Polymarket | Odds for a specific event id or slug |
| `lookup_aircraft_state` | OpenSky Network | Latest ADS-B state for a tail number (N-Number) or ICAO24 hex |
| `convert_nnumber` | — (offline) | Pure-Python FAA N-Number ↔ ICAO24 conversion, no network needed |
| `get_global_events` | GDELT 2.0 | High-impact events for a country, ranked by Goldstein scale |
| `check_network_anomalies` | Cloudflare Radar | BGP hijacks + leaks and regional outage annotations |
| `get_macro_alert` | GDELT + Cloudflare | Composite convergence signal with explanation string |

---

## Quickstart

### 1. Install

```bash
uvx global-sentinel-mcp
```

Or install from PyPI:

```bash
pip install global-sentinel-mcp
```

### 2. Set environment variables (all optional — unset tools degrade gracefully)

```bash
# OpenSky — OAuth2 preferred (post-2025 migration), Basic Auth for legacy accounts.
export OPENSKY_CLIENT_ID="your_opensky_client_id"
export OPENSKY_CLIENT_SECRET="your_opensky_client_secret"
# Cloudflare Radar — required for BGP and outage tools.
export CLOUDFLARE_API_TOKEN="your_cf_token"
# Optional.
export LOG_LEVEL="INFO"
```

### 3. Run

```bash
global-sentinel-mcp
```

The server speaks MCP JSON-RPC over stdio.

### Local development

```bash
git clone https://github.com/ykshah1309/global-sentinel-mcp
cd global-sentinel-mcp
uv sync --dev
uv run global-sentinel-mcp        # run the server
uv run pytest tests/ -v           # run the test suite
uv run ruff check src/ tests/     # lint
uv run mypy src/                  # type-check
```

---

## Claude Desktop configuration

Add to `claude_desktop_config.json` (see [claude_desktop_config.example.json](claude_desktop_config.example.json)):

```json
{
  "mcpServers": {
    "global-sentinel": {
      "command": "uvx",
      "args": ["global-sentinel-mcp"],
      "env": {
        "OPENSKY_CLIENT_ID": "your_opensky_client_id",
        "OPENSKY_CLIENT_SECRET": "your_opensky_client_secret",
        "CLOUDFLARE_API_TOKEN": "your_cf_token"
      }
    }
  }
}
```

## Cursor configuration

Add to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "global-sentinel": {
      "command": "uvx",
      "args": ["global-sentinel-mcp"],
      "env": {
        "OPENSKY_CLIENT_ID": "your_opensky_client_id",
        "OPENSKY_CLIENT_SECRET": "your_opensky_client_secret",
        "CLOUDFLARE_API_TOKEN": "your_cf_token"
      }
    }
  }
}
```

---

## Environment Variables

| Variable | Required for | Description |
|---|---|---|
| `OPENSKY_CLIENT_ID` | aviation (OAuth2, preferred) | OpenSky OAuth2 client id — [register free](https://opensky-network.org) |
| `OPENSKY_CLIENT_SECRET` | aviation (OAuth2, preferred) | OpenSky OAuth2 client secret |
| `OPENSKY_USERNAME` | aviation (legacy) | OpenSky Basic Auth username (pre-2025 accounts) |
| `OPENSKY_PASSWORD` | aviation (legacy) | OpenSky Basic Auth password |
| `CLOUDFLARE_API_TOKEN` | BGP + outages | Cloudflare API token with Radar read permissions |
| `LOG_LEVEL` | — | Python log level (DEBUG / INFO / WARNING / ERROR). Default `INFO`. |

Polymarket and GDELT tools require no authentication. Anonymous OpenSky is
allowed but heavily rate-limited.

---

## Data Sources

### Polymarket (Gamma API)

Crowd-sourced prediction market data. Token prices reflect the crowd's
estimated probability of future events. No API key required. Events expose
`outcomes` and `outcomePrices` as JSON-encoded strings — the client parses the
"Yes" leg and returns it as `probability_pct`.
[Docs](https://docs.polymarket.com/)

### GDELT 2.0

The world's largest open-access global news event database, updated every 15
minutes. Events are coded with actors, event types, Goldstein
conflict/cooperation scores, and geographic coordinates. Per publish cycle the
server downloads and parses the 5 MB export zip exactly once, then answers all
country queries from an in-memory DataFrame cache.
[Docs](https://www.gdeltproject.org/data.html)

### OpenSky Network

Public ADS-B flight tracking from a global network of volunteer receivers.
Returns real-time position, altitude, velocity, and on-ground status for any
aircraft with a Mode S transponder. Post-2025 the service moved to OAuth2
client-credentials; this server handles token refresh automatically and falls
back to Basic Auth (legacy) or anonymous if credentials are absent.
[Docs](https://openskynetwork.github.io/opensky-api/)

### Cloudflare Radar

Internet-infrastructure telemetry from Cloudflare's global network. Covers BGP
routing anomalies (`/bgp/hijacks/events`, `/bgp/leaks/events`) and regional
outage annotations (`/annotations/outages`, formerly "traffic anomalies",
renamed by Cloudflare in 2024). Requires a free Cloudflare API token.
[Docs](https://developers.cloudflare.com/radar/)

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup instructions, branch naming
conventions, testing requirements, and code style guidelines.

---

## License

[MIT](LICENSE) — Copyright (c) 2026 ykshah1309
