from __future__ import annotations

import os

from quotabubble.app.settings import Settings
from quotabubble.credentials import get_secret
from quotabubble.providers.antigravity import AntigravityProvider
from quotabubble.providers.base import Provider, ProviderStatus, UsageSnapshot
from quotabubble.providers.claude import ClaudeProvider
from quotabubble.providers.codex import CodexProvider
from quotabubble.providers.copilot import CopilotProvider
from quotabubble.providers.cursor import CursorProvider
from quotabubble.providers.deepseek import DeepSeekProvider
from quotabubble.providers.opencode import OpenCodeProvider
from quotabubble.providers.openrouter import OpenRouterProvider


def resolve_api_key(settings: Settings, provider_id: str) -> str | None:
    stored = get_secret(provider_id)
    if stored:
        return stored
    stored = settings.api_keys.get(provider_id)
    if stored:
        return stored
    return os.environ.get(f"{provider_id.upper()}_API_KEY")


def build_providers(settings: Settings) -> list[Provider]:
    return [
        ClaudeProvider(),
        CodexProvider(),
        AntigravityProvider(),
        CopilotProvider(),
        CursorProvider(),
        OpenCodeProvider(api_key=resolve_api_key(settings, "opencode")),
        DeepSeekProvider(api_key=resolve_api_key(settings, "deepseek")),
        OpenRouterProvider(api_key=resolve_api_key(settings, "openrouter")),
    ]


def select_providers(providers: list[Provider], settings: Settings) -> list[Provider]:
    if settings.enabled_providers is not None:
        enabled = set(settings.enabled_providers)
        selected = [provider for provider in providers if provider.id in enabled]
        # Explicit selection keeps a provider visible even when it is signed
        # out, but still gives it an opportunity to initialise credentials on
        # the UI thread before polling begins.
        for provider in selected:
            provider.detect()
        return selected
    return [provider for provider in providers if provider.detect()]


def loading_snapshot(provider: Provider) -> UsageSnapshot:
    return UsageSnapshot(
        provider=provider.id,
        display_name=provider.display_name,
        status=ProviderStatus.LOADING,
    )


def merge_selected_snapshots(
    selected: list[Provider],
    current: list[UsageSnapshot],
    cached: dict[str, UsageSnapshot],
) -> list[UsageSnapshot]:
    """Build the snapshot list for `selected`: keep whatever's already
    displayed for providers still selected (so re-detecting, e.g. on
    refresh, doesn't flash live numbers back to stale), seed a placeholder
    (last-good cache marked stale, or a loading snapshot) for newly
    selected providers, and drop anything no longer selected."""
    current_by_id = {snapshot.provider: snapshot for snapshot in current}
    snapshots = []
    for provider in selected:
        if provider.id in current_by_id:
            snapshots.append(current_by_id[provider.id])
            continue
        previous = cached.get(provider.id)
        if previous is not None:
            snapshots.append(previous.model_copy(update={"stale": True}))
        else:
            snapshots.append(loading_snapshot(provider))
    return snapshots
