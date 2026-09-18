# QuotaBubble — agent guidelines

## Workflow

- **Never commit directly to `main`.** Create a branch per item: `feat/…`, `fix/…`, `chore/…`, `docs/…`.
- Push the branch and **open a pull request** describing the change.
- **Wait for review.** Address review comments by pushing follow-up commits to the same branch.
- Merge **only after explicit approval**, and **never squash-merge** — use a merge commit (default).

## Development

- Package manager: `uv`.
- Lint: `uv run ruff check src tests`.
- Test: `uv run pytest -q`.
- Coverage: `uv run pytest -q --cov=src/quotabubble --cov-report=term-missing`. CI gates at `fail_under` in `pyproject.toml` `[tool.coverage.report]` (78%, ratchet up as coverage improves) and uploads to Codecov.
- Providers live in `src/quotabubble/providers/` behind the `Provider` protocol; they must not import Qt.
- Platform-specific behavior (window flags, credential stores, autostart) lives in `src/quotabubble/platform/`.
- The UI (`src/quotabubble/ui/`) renders `UsageSnapshot` objects and must not perform I/O or HTTP itself.

## Runtime notes

- Config: `%LOCALAPPDATA%\quotabubble\settings.json`.
- Last-good cache: `%LOCALAPPDATA%\quotabubble\Cache\last_good.json`.
- Logs: `%LOCALAPPDATA%\quotabubble\Logs\quotabubble.log` (rotating).
- Only one instance runs; a second launch re-shows the first.
- Poll interval defaults to 5 minutes; transient errors fall back to the last-good snapshot.

## Distribution

- **Windows binary:** `release.yml` runs on a `v*` tag, builds with PyInstaller, and attaches `QuotaBubble-windows-x64.zip` to the GitHub Release.
- **PyPI:** `publish.yml` (manual dispatch) runs `uv build` and `uv publish` via Trusted Publishing; it defaults to TestPyPI and can target PyPI. Bump the version in `pyproject.toml` per release.
- **winget:** the manifest for a version lives in `packaging/winget/<version>/` and is validated with `winget validate --manifest <dir>`. On a `v*` tag, the `winget` job in `release.yml` runs `komac update Izzet.QuotaBubble` to open a PR against `microsoft/winget-pkgs`.
  - Needs a repository secret `WINGET_TOKEN`: a classic personal access token with `public_repo` (the default `GITHUB_TOKEN` cannot open PRs on another repository). Without it the job is skipped.
  - First submission is manual: `komac submit packaging/winget/<version> --yes --token <PAT>`.
  - Committing to `microsoft/winget-pkgs` requires signing the Microsoft CLA once by commenting `@microsoft-github-policy-service agree` on the PR.
- In a winget multi-file manifest the default-locale file must declare `ManifestType: defaultLocale` (not `locale`), and each file should start with a `# yaml-language-server: $schema=...` header.
