# Data Sources

`global-sentinel-mcp` aggregates four public alternative-data streams. This
document covers each upstream API, what data it provides, and relevant links.

---

## 1. Polymarket (Gamma API)

**What:** Crowd-sourced probability data from prediction markets. Each market
represents a question (e.g. "Will X happen by 2026?") with token prices that
reflect crowd-estimated probabilities.

**Endpoint:** `https://gamma-api.polymarket.com`

**Data points:** Event title, probability (Yes-token price × 100), trading
volume (USD), end date.

**Docs:** https://docs.polymarket.com/

---

## 2. GDELT 2.0 (Global Database of Events, Language, and Tone)

**What:** The world's largest open-access global news event database, refreshed
every 15 minutes. Each record encodes a geopolitical event extracted from news
articles worldwide, with actor codes, event types, Goldstein conflict/cooperation
scale, geographic coordinates, and source URLs.

**Endpoint:** `http://data.gdeltproject.org/gdeltv2/lastupdate.txt` → links to
the latest 15-minute export (tab-separated, 61 columns, headerless).

**Data points:** Global event ID, date, actor countries, Goldstein scale,
article count, source URL.

**Schema:** 61 columns per the authoritative header list from
[linwoodc3/gdelt2HeaderRows](https://github.com/linwoodc3/gdelt2HeaderRows).

**Docs:** https://www.gdeltproject.org/data.html

---

## 3. OpenSky Network

**What:** Public ADS-B aviation state-vector API. The same transponder data
that flight-status apps use, provided by a network of volunteer receivers.

**Endpoint:** `https://opensky-network.org/api/states/all`

**Data points:** ICAO24 hex, callsign, origin country, position (lat/lon),
barometric altitude, ground speed, heading, on-ground status, last contact
timestamp.

**Auth:** Free tier requires Basic Auth (username + password). Register at
https://opensky-network.org.

**Docs:** https://openskynetwork.github.io/opensky-api/

---

## 4. Cloudflare Radar

**What:** Public internet-infrastructure telemetry from Cloudflare's global
network. Covers BGP routing anomalies (hijacks, leaks) and regional traffic
anomalies (outages, government-directed shutdowns).

**Endpoint:** `https://api.cloudflare.com/client/v4/radar`

**Data points:** BGP hijack events (prefix, ASN, timestamps), traffic anomaly
events (country, type, start/end dates).

**Auth:** Requires a free Cloudflare API token with Radar read permissions.

**Docs:** https://developers.cloudflare.com/radar/
