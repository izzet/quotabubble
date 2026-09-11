from __future__ import annotations

import os

from quotabubble.app.settings import Settings
from quotabubble.providers.antigravity import AntigravityProvider
from quotabubble.providers.base import Provider, ProviderStatus, UsageSnapshot
from quotabubble.providers.claude import ClaudeProvider
from quotabubble.providers.codex import CodexProvider
from quotabubble.providers.deepseek import DeepSeekProvider


def resolve_api_key(settings: Settings, provider_id: str) -> str | None:
    stored = settings.api_keys.get(provider_id)
    if stored:
        return stored
    return os.environ.get(f"{provider_id.upper()}_API_KEY")


def build_providers(settings: Settings) -> list[Provider]:
    return [
        ClaudeProvider(),
        CodexProvider(),
        AntigravityProvider(),
        DeepSeekProvider(api_key=resolve_api_key(settings, "deepseek")),
    ]


def select_providers(providers: list[Provider], settings: Settings) -> list[Provider]:
    if settings.enabled_providers is not None:
        enabled = set(settings.enabled_providers)
        return [provider for provider in providers if provider.id in enabled]
    return [provider for provider in providers if provider.detect()]


def loading_snapshot(provider: Provider) -> UsageSnapshot:
    return UsageSnapshot(
        provider=provider.id,
        display_name=provider.display_name,
        status=ProviderStatus.LOADING,
    )
