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
- **PyPI:** the `pypi` job in `release.yml` runs `uv build`, a smoke test of the built wheel (installs it into a throwaway venv and imports a non-Qt module — not the full pytest suite, since PySide6 needs system libraries this runner doesn't have and the commit already passed the full suite via `ci.yml` before merge), then `uv publish --trusted-publishing always` on a `v*` tag. No separate manual step or token; auth is via PyPI Trusted Publishing (OIDC), scoped on pypi.org to this exact repo + workflow filename (`release.yml`) + `pypi` environment. If that job's auth fails, the Trusted Publisher config on pypi.org almost certainly still points at the old `publish.yml` (which this replaced) and needs updating to `release.yml`. Bump the version in `pyproject.toml` per release.
  - Deliberately has no `needs:` on `windows` (or any future per-OS build job): the wheel is `py3-none-any` (pure Python, no compiled extensions), identical regardless of which OS built it, so it must never depend on an unrelated platform-specific binary build succeeding.
- **winget:** the manifest for a version lives in `packaging/winget/<version>/` and is validated with `winget validate --manifest <dir>`. On a `v*` tag, the `winget` job in `release.yml` runs `komac update Izzet.QuotaBubble` to open a PR against `microsoft/winget-pkgs`.
  - Needs a repository secret `WINGET_TOKEN`: a classic personal access token with `public_repo` (the default `GITHUB_TOKEN` cannot open PRs on another repository). Without it the job is skipped.
  - First submission is manual: `komac submit packaging/winget/<version> --yes --token <PAT>`.
  - Committing to `microsoft/winget-pkgs` requires signing the Microsoft CLA once by commenting `@microsoft-github-policy-service agree` on the PR.
- In a winget multi-file manifest the default-locale file must declare `ManifestType: defaultLocale` (not `locale`), and each file should start with a `# yaml-language-server: $schema=...` header.
- **Chocolatey:** the package lives in `packaging/chocolatey/` (`quotabubble.nuspec`, `tools/chocolateyinstall.ps1`). On a `v*` tag, the `chocolatey` job in `release.yml` downloads that version's release zip, computes its SHA256, substitutes the `__URL__`/`__CHECKSUM__` placeholders in `chocolateyinstall.ps1`, then runs `choco pack` and `choco push`.
  - Needs a repository secret `CHOCOLATEY_API_KEY` (from a chocolatey.org account). Without it the job is skipped.
  - Unlike winget, there's no separate "first submission" step — `choco push` creates the package on first use. New packages go through Chocolatey's moderation queue before showing up in default search/`choco install` from the community feed.

**When macOS/Linux binaries are added** (#37 and beyond), `release.yml` should restructure the binary side into a fan-in shape, not just add more independent per-OS jobs:
- A matrix `build` job (`windows-latest`, `macos-latest`, `ubuntu-latest`) that tests, builds with PyInstaller, packages, and uploads each OS's archive as a CI artifact — none of them publish anything themselves.
- One `github-release` job, `needs: [build]` (the whole matrix), that downloads every artifact and creates a single GitHub Release with all of them attached at once. This replaces the "Publish release" step that currently lives inside `windows` — that only works today because there's exactly one platform; it stops being correct the moment a second one exists.
- `winget`, `chocolatey`, and any future macOS/Linux package-manager jobs (Homebrew tap, AUR, Flatpak, ...) each depend on `github-release` (not on the raw per-OS build jobs), and each only cares about its own OS's asset URL from that release.
- `pypi` stays exactly as it is — outside this whole chain, no `needs:` on any of it, for the reason above.
