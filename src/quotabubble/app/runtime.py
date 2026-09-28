from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime

from quotabubble.app.cache import load_snapshots, save_snapshots
from quotabubble.providers.base import Provider, ProviderStatus, UsageSnapshot

ERROR_BACKOFF_SECONDS = 300.0
MAX_BACKOFF_SECONDS = 3600.0
logger = logging.getLogger(__name__)


class PollingRuntime:
    """Qt-free provider polling, cache, and retry state."""

    def __init__(
        self,
        providers: list[Provider],
        *,
        last_good: dict[str, UsageSnapshot] | None = None,
        save_last_good: Callable[[dict[str, UsageSnapshot]], None] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._providers = list(providers)
        self._last_good = dict(load_snapshots() if last_good is None else last_good)
        self._save_last_good = save_snapshots if save_last_good is None else save_last_good
        self._monotonic = monotonic
        self._now = now
        self._failures: dict[str, int] = {}
        self._retry_at: dict[str, float] = {}

    def poll(self, *, force: bool = False) -> list[UsageSnapshot]:
        if force:
            self._retry_at.clear()
        now = self._monotonic()
        snapshots = []
        for provider in self._providers:
            if not force and now < self._retry_at.get(provider.id, 0.0):
                continue
            try:
                fresh = provider.fetch()
            except Exception:
                logger.exception("provider '%s' raised during fetch", provider.id)
                fresh = UsageSnapshot(
                    provider=provider.id,
                    display_name=provider.display_name,
                    status=ProviderStatus.ERROR,
                    message="unexpected error",
                )
            snapshots.append(self._process(fresh))
        return snapshots

    def set_providers(self, providers: list[Provider]) -> bool:
        changed = [provider.id for provider in providers] != [
            provider.id for provider in self._providers
        ]
        self._providers = list(providers)
        return changed

    @property
    def last_good(self) -> dict[str, UsageSnapshot]:
        return dict(self._last_good)

    def _process(self, fresh: UsageSnapshot) -> UsageSnapshot:
        provider_id = fresh.provider
        if fresh.status is ProviderStatus.OK:
            if fresh.fetched_at is None:
                fresh = fresh.model_copy(update={"fetched_at": self._now()})
            self._failures.pop(provider_id, None)
            self._retry_at.pop(provider_id, None)
            self._last_good[provider_id] = fresh
            self._save_last_good(self._last_good)
            logger.info("provider '%s' ok (%d windows)", provider_id, len(fresh.windows))
            return fresh
        if fresh.status is ProviderStatus.ERROR:
            failures = self._failures.get(provider_id, 0) + 1
            self._failures[provider_id] = failures
            if fresh.retry_after:
                delay = min(max(fresh.retry_after, ERROR_BACKOFF_SECONDS), MAX_BACKOFF_SECONDS)
            else:
                delay = min(ERROR_BACKOFF_SECONDS * 2 ** (failures - 1), MAX_BACKOFF_SECONDS)
            self._retry_at[provider_id] = self._monotonic() + delay
            previous = self._last_good.get(provider_id)
            if previous is not None:
                logger.warning(
                    "provider '%s' error (%s); keeping last-good, retry in %.0fs",
                    provider_id,
                    fresh.message,
                    delay,
                )
                return previous.model_copy(update={"stale": True})
            logger.warning("provider '%s' error (%s)", provider_id, fresh.message)
            return fresh
        self._failures.pop(provider_id, None)
        self._retry_at.pop(provider_id, None)
        logger.warning("provider '%s' %s (%s)", provider_id, fresh.status, fresh.message)
        return fresh
