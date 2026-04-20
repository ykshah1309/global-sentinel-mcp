"""Shared test fixtures — all network calls are mocked via respx."""

from __future__ import annotations

import io
import zipfile

import pytest
import respx


@pytest.fixture()
def polymarket_mock():
    """Mock the Polymarket Gamma API."""
    with respx.mock(base_url="https://gamma-api.polymarket.com") as mock:
        yield mock


@pytest.fixture()
def opensky_mock():
    """Mock the OpenSky Network API."""
    with respx.mock(base_url="https://opensky-network.org") as mock:
        yield mock


@pytest.fixture()
def gdelt_mock():
    """Mock GDELT data endpoints with a 3-row in-memory TSV zip."""
    rows = []
    for i in range(3):
        row = [""] * 61
        row[0] = str(1000 + i)               # GLOBALEVENTID
        row[1] = "20260417"                   # SQLDATE
        row[7] = "US"                         # Actor1CountryCode
        row[17] = "CN"                        # Actor2CountryCode
        row[30] = str(7.0 - i)               # GoldsteinScale: 7.0, 6.0, 5.0
        row[33] = str(10 + i)                # NumArticles
        row[60] = f"https://example.com/{i}"  # SOURCEURL
        rows.append("\t".join(row))

    tsv_content = "\n".join(rows).encode("utf-8")

    # Build an in-memory zip
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("test.export.CSV", tsv_content)
    zip_bytes = buf.getvalue()

    with respx.mock as mock:
        mock.get("http://data.gdeltproject.org/gdeltv2/lastupdate.txt").respond(
            200,
            text=(
                "999 abc123 http://data.gdeltproject.org/gdeltv2/20260417.export.CSV.zip\n"
                "999 abc123 http://data.gdeltproject.org/gdeltv2/20260417.mentions.CSV.zip\n"
            ),
        )
        mock.get(
            "http://data.gdeltproject.org/gdeltv2/20260417.export.CSV.zip"
        ).respond(200, content=zip_bytes)
        yield mock


@pytest.fixture()
def cloudflare_mock():
    """Mock the Cloudflare Radar API."""
    with respx.mock(base_url="https://api.cloudflare.com") as mock:
        yield mock
