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
- Providers live in `src/quotabubble/providers/` behind the `Provider` protocol; they must not import Qt.
- Platform-specific behavior (window flags, credential stores, autostart) lives in `src/quotabubble/platform/`.
- The UI (`src/quotabubble/ui/`) renders `UsageSnapshot` objects and must not perform I/O or HTTP itself.

## Runtime notes

- Config: `%LOCALAPPDATA%\quotabubble\settings.json`.
- Last-good cache: `%LOCALAPPDATA%\quotabubble\Cache\last_good.json`.
- Logs: `%LOCALAPPDATA%\quotabubble\Logs\quotabubble.log` (rotating).
- Only one instance runs; a second launch re-shows the first.
- Poll interval defaults to 5 minutes; transient errors fall back to the last-good snapshot.
