# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x | ✅ |

## Reporting a vulnerability

**Do not open a public issue for security vulnerabilities.**

Instead, use [GitHub's private vulnerability advisory](https://github.com/ykshah1309/global-sentinel-mcp/security/advisories/new)
to report the issue confidentially.

### Response SLA

- **Acknowledgement:** within 72 hours
- **Remediation or mitigation:** within 7 calendar days

## Scope

### In scope

- `src/` — all server and client code
- `tests/` — test infrastructure
- `.github/workflows/` — CI/CD pipelines

### Out of scope

- Vulnerabilities in upstream APIs (Polymarket, GDELT, OpenSky, Cloudflare)
- Issues in third-party dependencies (report those upstream)

## Credential safety

- Never commit `.env` files or API tokens. The `.gitignore` enforces this.
- Environment variables (`OPENSKY_USERNAME`, `OPENSKY_PASSWORD`,
  `CLOUDFLARE_API_TOKEN`) must be set at runtime, never hardcoded.
- If credentials are accidentally committed:
  1. **Rotate the credentials immediately.**
  2. Report via the private advisory link above.
  3. Force-push to remove the commit from history (owner only).
