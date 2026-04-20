# Branch Protection Rules for `main`

These settings must be configured in the GitHub UI under
**Settings → Branches → Branch protection rules → `main`**.

## Required settings

| Setting | Value |
|---|---|
| Require a pull request before merging | ✅ Enabled |
| Required approving reviews | **1** (owner only) |
| Require status checks to pass before merging | ✅ Enabled |
| Required status checks | `test` (from `ci.yml`) |
| Require branches to be up to date before merging | ✅ Enabled |
| Require conversation resolution before merging | ✅ Enabled |
| Require linear history | ✅ Enabled |
| Restrict who can push to matching branches | `@ykshah1309` only |
| Do not allow bypassing the above settings | ✅ Enabled (applies to admins) |
| Allow force pushes | ❌ Disabled |
| Allow deletions | ❌ Disabled |

## Notes

- The `test` job is defined in `.github/workflows/ci.yml` and runs
  `pytest`, `ruff check`, and `mypy` on every PR and push to `main`.
- No one — including admins — may bypass these rules.
- All merges to `main` must go through a pull request.
