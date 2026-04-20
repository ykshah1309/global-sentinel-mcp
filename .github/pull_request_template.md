## Pull Request

### Description

<!-- Briefly describe your changes -->

### Checklist

- [ ] I have read [CONTRIBUTING.md](../CONTRIBUTING.md)
- [ ] Code follows the async / Pydantic pattern used by existing modules
- [ ] Tests added (happy path + error path, `pytest-asyncio` + `respx`)
- [ ] No hardcoded credentials or API keys
- [ ] Zero `print()` statements in `src/` (all diagnostics use `logging` to `sys.stderr`)
- [ ] No `asyncio.run()` inside tool handlers
- [ ] `ruff check src/` passes with no errors
- [ ] `mypy src/ --ignore-missing-imports` passes
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
