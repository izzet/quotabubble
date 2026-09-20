# QuotaBubble

[![ci](https://github.com/izzet/quotabubble/actions/workflows/ci.yml/badge.svg)](https://github.com/izzet/quotabubble/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/izzet/quotabubble/graph/badge.svg)](https://codecov.io/gh/izzet/quotabubble)
[![PyPI](https://img.shields.io/pypi/v/quotabubble)](https://pypi.org/project/quotabubble/)
[![Python versions](https://img.shields.io/pypi/pyversions/quotabubble)](https://pypi.org/project/quotabubble/)
[![License](https://img.shields.io/github/license/izzet/quotabubble)](LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

**Your AI usage limits, always in sight.**

QuotaBubble is a small, frameless desktop widget that keeps the usage limits for your AI coding tools visible without opening a dashboard, terminal, or browser. It floats above your windows, fades to almost nothing when idle, and expands into a compact detail panel when you click it.

<p align="center">
  <img src="https://izzet.github.io/quotabubble/screenshot-compact.png?v=2" width="260" alt="Idle bubble">
  <img src="https://izzet.github.io/quotabubble/screenshot-expanded.png?v=2" width="300" alt="Expanded detail">
</p>

## Features

- **Frameless floating bubble** — translucent, rounded, always on top, and it never steals keyboard focus.
- **Fades away when idle** — a configurable low opacity keeps it unobtrusive; hover to bring it back.
- **Click to expand** — see each usage window, the percentage used, and a live reset countdown.
- **Drag anywhere** — move it across monitors; the position is remembered.
- **Tray icon** — show/hide, settings, open logs, and quit.
- **Resilient** — refreshes every 5 minutes, caches the last good values, and keeps showing them (dimmed) through transient network or rate-limit errors.
- **Local only** — it reuses the credentials your tools already store and talks straight to the providers. No telemetry, no QuotaBubble server.

## Supported providers

| Provider | Authentication |
| --- | --- |
| Claude Code | macOS Keychain or `~/.claude/.credentials.json` |
| Codex | `~/.codex/auth.json` |
| Google Antigravity | Windows Credential Manager or macOS Keychain |
| GitHub Copilot | Windows Credential Manager or macOS Keychain |
| Cursor | Cursor IDE `state.vscdb` / `auth.json` (`CURSOR_SESSION_TOKEN` override) |
| OpenCode | `~/.local/share/opencode/auth.json` / `opencode.jsonc` (`OPENCODE_API_KEY` override) or API key |
| DeepSeek | API key |
| OpenRouter | API key |

Providers are detected automatically. Enable or disable them in Settings; API keys are entered there and validated inline with a **Test** button. Antigravity and Copilot reuse their existing Windows Credential Manager or macOS Keychain sign-ins. Cursor reuses the IDE session token from `state.vscdb` or `auth.json` (or `CURSOR_SESSION_TOKEN`).

## Install

### Windows

With [winget](https://learn.microsoft.com/windows/package-manager/winget/):

```powershell
winget install Izzet.QuotaBubble
```

Or with [Chocolatey](https://community.chocolatey.org/packages/quotabubble):

```powershell
choco install quotabubble
```

Or download the latest `QuotaBubble-windows-x64.zip` from the [Releases page](https://github.com/izzet/quotabubble/releases), unzip it, and run `QuotaBubble.exe`.

> The binary is not code-signed yet, so Windows SmartScreen may warn you. Choose **More info → Run anyway**.

### macOS

Download the matching disk image from the [Releases page](https://github.com/izzet/quotabubble/releases):

- `QuotaBubble-macos-arm64.dmg` for Apple Silicon Macs.
- `QuotaBubble-macos-x64.dmg` for Intel Macs.

Install or upgrade with Homebrew after adding the first-party tap:

```bash
brew install --cask izzet/tap/quotabubble
```

Open the disk image and drag **QuotaBubble** to **Applications**. The initial macOS builds are not
yet Developer ID signed or notarized; Control-click the app, choose **Open**, then confirm the
first-launch dialog. Signing and notarization will be added in a later release.

### Linux

Linux is currently supported from source on X11 desktop sessions. Native Linux release artifacts
are not available yet; use the source-install instructions below.

Wayland compositors control top-level window placement and stacking, which prevents QuotaBubble
from reliably staying above other windows or being dragged by the app. GNOME Wayland is therefore
not a supported session yet. Use an X11 session for the floating-widget experience.

### From source (Python 3.11+)

```bash
git clone https://github.com/izzet/quotabubble.git
cd quotabubble
uv tool install --editable .
quotabubble
```

You can also install it as a standalone command with [pipx](https://pipx.pypa.io/): `pipx install quotabubble`.

## Usage

- **Idle** — a faint bubble; hover to make it fully visible.
- **Click** — expand the detail panel; click again to collapse.
- **Drag** — grab and move it anywhere, including across monitors.
- **Right-click / tray** — Settings, Open logs, Show/Hide, Quit.
- **Launch at login** — enable it in Settings.

## Settings

Idle opacity, fade delay, refresh interval (default 5 minutes), show percentage used vs. remaining, launch at login, and which providers are visible.

## Where things live

On Windows:

| Path | Purpose |
| --- | --- |
| `%LOCALAPPDATA%\quotabubble\settings.json` | Settings |
| `%LOCALAPPDATA%\quotabubble\Cache\last_good.json` | Last-good snapshots |
| `%LOCALAPPDATA%\quotabubble\Logs\quotabubble.log` | Rotating log |

On macOS and Linux these map to the standard platform directories.

## Development

```bash
uv sync
uv run ruff check src tests
uv run pytest -q
uv run pytest -q --cov=src/quotabubble --cov-report=term-missing  # with coverage
```

CI gates on coverage (currently 80% minimum, see `[tool.coverage.report]` in `pyproject.toml`) and uploads results to Codecov.

See [AGENTS.md](AGENTS.md) for architecture and contribution conventions. The provider layer (`src/quotabubble/providers/`) is pure Python behind a `Provider` protocol, and platform specifics live in `src/quotabubble/platform/`.

## Status

Windows and macOS have native release artifacts. Linux currently supports X11 source installs;
Wayland support is limited because its window-management model does not provide the floating-widget
behavior QuotaBubble needs. Claude, Codex, Cursor, OpenCode, DeepSeek, and OpenRouter work
anywhere. Antigravity and Copilot support Windows Credential Manager and macOS Keychain; Linux
credential support is still to come. API keys entered in Settings are stored in the OS credential
store (Windows Credential Manager, macOS Keychain, Linux Secret Service) via
[`keyring`](https://pypi.org/project/keyring/); if no OS keyring backend is available, they fall
back to the local settings file.

## License

[MIT](LICENSE)
