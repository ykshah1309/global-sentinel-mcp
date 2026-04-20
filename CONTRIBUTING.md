# Contributing to global-sentinel-mcp

Thanks for your interest in contributing! This document covers everything you
need to know to get started.

## Setup

This project uses **`uv`** exclusively. Do not use `pip`, `poetry`, or
`conda`.

```bash
# Clone and install
git clone https://github.com/ykshah1309/global-sentinel-mcp.git
cd global-sentinel-mcp
uv sync --dev
```

## Branch naming

All work happens on feature branches. Never push directly to `main`.

| Prefix | Purpose |
|---|---|
| `feat/` | New features or tools |
| `fix/` | Bug fixes |
| `docs/` | Documentation only |
| `chore/` | Maintenance, deps, CI |
| `refactor/` | Code restructuring (no behavior change) |
| `test/` | Test additions or fixes |

## Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(aviation): add bounding-box state lookup
fix(gdelt): handle empty export zip gracefully
docs: update quickstart for Cursor
```

## The golden rule

**Never push directly to `main`.** All changes go through a pull request with
at least one approving review.

## Testing

Every client module must have `pytest-asyncio` + `respx` tests covering:

1. **Happy path** — mocked 200 → assert parsed Pydantic model fields
2. **Error path** — mocked 429 / missing env var → assert typed error model returned

Run the full suite:

```bash
uv run pytest tests/ -v
```

## The stdout rule

**Any `print()` statement in `src/` is an immediate rejection.**

`sys.stdout` is reserved for MCP JSON-RPC transport. All diagnostics must use
the `logging` module configured to write to `sys.stderr`.

## Code style

- Python 3.11+ — use modern type hints (`str | None`, not `Optional[str]`)
- `httpx.AsyncClient` for all HTTP calls — no `requests`, `urllib`, or `aiohttp`
- Pydantic v2 for all public inputs and outputs — no bare dicts across module boundaries
- Full type annotations on all public functions
- Typed error returns — never raise bare exceptions from tool handlers
- No `asyncio.run()` inside handlers — use `await` directly

## Adding a new data source

1. Create `src/global_sentinel_mcp/<source_name>/` with:
   - `__init__.py`
   - `models.py` — Pydantic v2 models for responses and errors
   - `client.py` — async client using `httpx.AsyncClient`
   - (optional) `parser.py`, `cache.py`, `converter.py` as needed
2. Register tool(s) in `server.py`
3. Add tests in `tests/test_<source_name>.py`
4. Update `CHANGELOG.md`

## Linting

```bash
uv run ruff check src/
uv run mypy src/ --ignore-missing-imports
```

## Release flow

Releases are owner-only. The publish workflow uses PyPI OIDC trusted
publishing — no API tokens are stored in secrets.

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Create a GitHub Release with a tag like `v0.1.0`
4. The `publish.yml` workflow handles the rest
