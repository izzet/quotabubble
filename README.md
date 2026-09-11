# QuotaBubble

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
| Claude Code | `~/.claude/.credentials.json` |
| Codex | `~/.codex/auth.json` |
| Google Antigravity | Windows Credential Manager (`gemini:antigravity`) |
| GitHub Copilot | Windows Credential Manager (`…copilot-cli`) |
| DeepSeek | API key |
| OpenRouter | API key |

Providers are detected automatically. Enable or disable them in Settings; API keys are entered there and validated inline with a **Test** button. On Windows, Antigravity and Copilot read their existing sign-ins from Credential Manager.

## Install

### Windows

Download the latest `QuotaBubble-windows-x64.zip` from the [Releases page](https://github.com/izzet/quotabubble/releases), unzip it, and run `QuotaBubble.exe`.

> The binary is not code-signed yet, so Windows SmartScreen may warn you. Choose **More info → Run anyway**.

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
```

See [AGENTS.md](AGENTS.md) for architecture and contribution conventions. The provider layer (`src/quotabubble/providers/`) is pure Python behind a `Provider` protocol, and platform specifics live in `src/quotabubble/platform/`.

## Status

Windows is the primary, fully supported platform. Claude, Codex, DeepSeek, and OpenRouter work anywhere; Antigravity and Copilot currently use the Windows credential store and need macOS/Linux implementations. API keys are stored in the local settings file for now — moving them to the OS keyring is tracked in [#3](https://github.com/izzet/quotabubble/issues/3).

## License

[MIT](LICENSE)
