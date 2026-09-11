from __future__ import annotations

from quotabubble.app.settings import Settings
from quotabubble.providers.base import Provider, ProviderStatus, UsageSnapshot


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
