from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QSystemTrayIcon

from quotabubble.app.notifications import (
    NotificationManager,
    NotificationState,
    WindowNotificationState,
    load_notification_state,
    save_notification_state,
)
from quotabubble.app.settings import Settings
from quotabubble.providers.base import Credits, ProviderStatus, UsageSnapshot, UsageWindow


def test_send_test_notification(qapp: object, tmp_path: Path) -> None:
    settings = Settings()
    mgr = NotificationManager(settings, state_path=tmp_path / "notifications.json")

    notifications: list[tuple[str, str, object]] = []
    mgr.notify.connect(lambda title, msg, icon: notifications.append((title, msg, icon)))

    mgr.send_test_notification()

    assert len(notifications) == 1
    title, msg, icon = notifications[0]
    assert title == "QuotaBubble"
    assert "Test notification" in msg
    assert icon == QSystemTrayIcon.MessageIcon.Information


def test_threshold_crossing_and_deduplication(qapp: object, tmp_path: Path) -> None:
    settings = Settings(thresholds=[75, 90])
    mgr = NotificationManager(settings, state_path=tmp_path / "notifications.json")

    notifications: list[tuple[str, str, object]] = []
    mgr.notify.connect(lambda title, msg, icon: notifications.append((title, msg, icon)))

    # Below threshold: no notification
    mgr.process_snapshot(
        UsageSnapshot(
            provider="claude",
            display_name="Claude",
            windows=[UsageWindow(label="5h", key="5h", used_pct=50.0)],
        )
    )
    assert len(notifications) == 0

    # Cross 75% threshold: info notification
    mgr.process_snapshot(
        UsageSnapshot(
            provider="claude",
            display_name="Claude",
            windows=[UsageWindow(label="5h", key="5h", used_pct=76.0)],
        )
    )
    assert len(notifications) == 1
    assert "Claude (5h): 76% quota used" in notifications[0][1]
    assert notifications[0][2] == QSystemTrayIcon.MessageIcon.Information

    # Still above 75%, below 90%: no duplicate notification
    mgr.process_snapshot(
        UsageSnapshot(
            provider="claude",
            display_name="Claude",
            windows=[UsageWindow(label="5h", key="5h", used_pct=78.0)],
        )
    )
    assert len(notifications) == 1

    # Cross 90% threshold: warning notification
    mgr.process_snapshot(
        UsageSnapshot(
            provider="claude",
            display_name="Claude",
            windows=[UsageWindow(label="5h", key="5h", used_pct=92.0)],
        )
    )
    assert len(notifications) == 2
    assert "Claude (5h): 92% quota used" in notifications[1][1]
    assert notifications[1][2] == QSystemTrayIcon.MessageIcon.Warning


def test_threshold_jump_fires_highest(qapp: object, tmp_path: Path) -> None:
    settings = Settings(thresholds=[75, 90])
    mgr = NotificationManager(settings, state_path=tmp_path / "notifications.json")

    notifications: list[tuple[str, str, object]] = []
    mgr.notify.connect(lambda title, msg, icon: notifications.append((title, msg, icon)))

    # Directly jump to 95%
    mgr.process_snapshot(
        UsageSnapshot(
            provider="claude",
            display_name="Claude",
            windows=[UsageWindow(label="5h", key="5h", used_pct=95.0)],
        )
    )
    # Should only emit one notification for the highest crossed threshold (90)
    assert len(notifications) == 1
    assert "Claude (5h): 95% quota used" in notifications[0][1]
    assert notifications[0][2] == QSystemTrayIcon.MessageIcon.Warning


def test_depletion_and_recovery_window(qapp: object, tmp_path: Path) -> None:
    settings = Settings(thresholds=[75, 90])
    mgr = NotificationManager(settings, state_path=tmp_path / "notifications.json")

    notifications: list[tuple[str, str, object]] = []
    mgr.notify.connect(lambda title, msg, icon: notifications.append((title, msg, icon)))

    # Depleted at 100%
    mgr.process_snapshot(
        UsageSnapshot(
            provider="copilot",
            display_name="Copilot",
            windows=[UsageWindow(label="Monthly", key="monthly", used_pct=100.0)],
        )
    )
    assert len(notifications) == 1
    assert "Copilot (Monthly): quota depleted (100% used)" in notifications[0][1]
    assert notifications[0][2] == QSystemTrayIcon.MessageIcon.Warning

    # Subsequent 100% does not re-notify
    mgr.process_snapshot(
        UsageSnapshot(
            provider="copilot",
            display_name="Copilot",
            windows=[UsageWindow(label="Monthly", key="monthly", used_pct=100.0)],
        )
    )
    assert len(notifications) == 1

    # Recovers below 100%
    mgr.process_snapshot(
        UsageSnapshot(
            provider="copilot",
            display_name="Copilot",
            windows=[UsageWindow(label="Monthly", key="monthly", used_pct=25.0)],
        )
    )
    assert len(notifications) == 2
    assert "Copilot (Monthly): quota recovered (25% used)" in notifications[1][1]
    assert notifications[1][2] == QSystemTrayIcon.MessageIcon.Information

    # Can fire 75% threshold again after recovery
    mgr.process_snapshot(
        UsageSnapshot(
            provider="copilot",
            display_name="Copilot",
            windows=[UsageWindow(label="Monthly", key="monthly", used_pct=78.0)],
        )
    )
    assert len(notifications) == 3
    assert "Copilot (Monthly): 78% quota used" in notifications[2][1]


def test_quota_zeroed_out_notification(qapp: object, tmp_path: Path) -> None:
    settings = Settings(thresholds=[75, 90])
    mgr = NotificationManager(settings, state_path=tmp_path / "notifications.json")

    notifications: list[tuple[str, str, object]] = []
    mgr.notify.connect(lambda title, msg, icon: notifications.append((title, msg, icon)))

    # Usage reaches 80% (fires 75% threshold)
    mgr.process_snapshot(
        UsageSnapshot(
            provider="claude",
            display_name="Claude",
            windows=[UsageWindow(label="5h", key="5h", used_pct=80.0)],
        )
    )
    assert len(notifications) == 1
    assert "Claude (5h): 80% quota used" in notifications[0][1]

    # Usage zeroes out (drops to 0% from >0%) -> fires quota reset alert!
    mgr.process_snapshot(
        UsageSnapshot(
            provider="claude",
            display_name="Claude",
            windows=[UsageWindow(label="5h", key="5h", used_pct=0.0)],
        )
    )
    assert len(notifications) == 2
    assert "Claude (5h): quota reset (0% used)" in notifications[1][1]
    assert notifications[1][2] == QSystemTrayIcon.MessageIcon.Information

    # Stays at 0% -> does not repeat reset alert
    mgr.process_snapshot(
        UsageSnapshot(
            provider="claude",
            display_name="Claude",
            windows=[UsageWindow(label="5h", key="5h", used_pct=0.0)],
        )
    )
    assert len(notifications) == 2

    # Climbs back up and crosses 75% again -> fires for the new cycle!
    mgr.process_snapshot(
        UsageSnapshot(
            provider="claude",
            display_name="Claude",
            windows=[UsageWindow(label="5h", key="5h", used_pct=78.0)],
        )
    )
    assert len(notifications) == 3
    assert "Claude (5h): 78% quota used" in notifications[2][1]


def test_usage_staying_at_same_threshold_never_refires(
    qapp: object, tmp_path: Path
) -> None:
    settings = Settings(thresholds=[75, 90])
    mgr = NotificationManager(settings, state_path=tmp_path / "notifications.json")

    notifications: list[tuple[str, str, object]] = []
    mgr.notify.connect(lambda title, msg, icon: notifications.append((title, msg, icon)))

    # Reaches 78% (fires 75% once)
    mgr.process_snapshot(
        UsageSnapshot(
            provider="claude",
            display_name="Claude",
            windows=[UsageWindow(label="Weekly", key="weekly", used_pct=78.0)],
        )
    )
    assert len(notifications) == 1

    # Usage moves to 80.0% (between 75% and 90%) -> MUST NOT fire again
    for _ in range(5):
        mgr.process_snapshot(
            UsageSnapshot(
                provider="claude",
                display_name="Claude",
                windows=[UsageWindow(label="Weekly", key="weekly", used_pct=80.0)],
            )
        )
    assert len(notifications) == 1


def test_usage_climbing_between_thresholds_never_refires(
    qapp: object, tmp_path: Path
) -> None:
    settings = Settings(thresholds=[75, 90])
    mgr = NotificationManager(settings, state_path=tmp_path / "notifications.json")

    notifications: list[tuple[str, str, object]] = []
    mgr.notify.connect(lambda title, msg, icon: notifications.append((title, msg, icon)))

    # 50% -> below threshold
    mgr.process_snapshot(
        UsageSnapshot(
            provider="claude",
            display_name="Claude",
            windows=[UsageWindow(label="Weekly", key="weekly", used_pct=50.0)],
        )
    )
    assert len(notifications) == 0

    # Crosses 75% at 78% -> 1 notification
    mgr.process_snapshot(
        UsageSnapshot(
            provider="claude",
            display_name="Claude",
            windows=[UsageWindow(label="Weekly", key="weekly", used_pct=78.0)],
        )
    )
    assert len(notifications) == 1

    # Usage steadily climbs between 75% and 90% -> MUST NOT fire any notifications
    for pct in [79.0, 80.0, 81.5, 83.0, 85.0, 87.2, 89.9]:
        mgr.process_snapshot(
            UsageSnapshot(
                provider="claude",
                display_name="Claude",
                windows=[UsageWindow(label="Weekly", key="weekly", used_pct=pct)],
            )
        )
        assert len(notifications) == 1

    # Reaches 90% -> fires 90% alert!
    mgr.process_snapshot(
        UsageSnapshot(
            provider="claude",
            display_name="Claude",
            windows=[UsageWindow(label="Weekly", key="weekly", used_pct=90.0)],
        )
    )
    assert len(notifications) == 2
    assert "90% quota used" in notifications[1][1]

    # Climbs further above 90% (92%, 95%) -> MUST NOT fire again
    for pct in [92.0, 95.0, 98.0]:
        mgr.process_snapshot(
            UsageSnapshot(
                provider="claude",
                display_name="Claude",
                windows=[UsageWindow(label="Weekly", key="weekly", used_pct=pct)],
            )
        )
        assert len(notifications) == 2


def test_usage_fluctuating_above_threshold_never_refires(
    qapp: object, tmp_path: Path
) -> None:
    settings = Settings(thresholds=[75, 90])
    mgr = NotificationManager(settings, state_path=tmp_path / "notifications.json")

    notifications: list[tuple[str, str, object]] = []
    mgr.notify.connect(lambda title, msg, icon: notifications.append((title, msg, icon)))

    # Crosses 75% at 78%
    mgr.process_snapshot(
        UsageSnapshot(
            provider="claude",
            display_name="Claude",
            windows=[UsageWindow(label="Weekly", key="weekly", used_pct=78.0)],
        )
    )
    assert len(notifications) == 1

    # Fluctuates up and down without falling below 75% -> MUST NOT fire
    for pct in [76.0, 77.5, 80.0, 79.2, 75.5, 82.0, 76.8]:
        mgr.process_snapshot(
            UsageSnapshot(
                provider="claude",
                display_name="Claude",
                windows=[UsageWindow(label="Weekly", key="weekly", used_pct=pct)],
            )
        )
        assert len(notifications) == 1


def test_startup_at_zero_percent_does_not_fire_reset(
    qapp: object, tmp_path: Path
) -> None:
    settings = Settings()
    mgr = NotificationManager(settings, state_path=tmp_path / "notifications.json")

    notifications: list[tuple[str, str, object]] = []
    mgr.notify.connect(lambda title, msg, icon: notifications.append((title, msg, icon)))

    # Initial snapshot at 0%
    mgr.process_snapshot(
        UsageSnapshot(
            provider="claude",
            display_name="Claude",
            windows=[UsageWindow(label="5h", key="5h", used_pct=0.0)],
        )
    )
    # Subsequent polls at 0%
    for _ in range(5):
        mgr.process_snapshot(
            UsageSnapshot(
                provider="claude",
                display_name="Claude",
                windows=[UsageWindow(label="5h", key="5h", used_pct=0.0)],
            )
        )
    # Must never fire reset on startup
    assert len(notifications) == 0


def test_depletion_straight_to_zero_percent(qapp: object, tmp_path: Path) -> None:
    settings = Settings()
    mgr = NotificationManager(settings, state_path=tmp_path / "notifications.json")

    notifications: list[tuple[str, str, object]] = []
    mgr.notify.connect(lambda title, msg, icon: notifications.append((title, msg, icon)))

    # Depleted at 100%
    mgr.process_snapshot(
        UsageSnapshot(
            provider="claude",
            display_name="Claude",
            windows=[UsageWindow(label="Weekly", key="weekly", used_pct=100.0)],
        )
    )
    assert len(notifications) == 1
    assert "quota depleted (100% used)" in notifications[0][1]

    # Drops straight to 0% -> only sends reset alert, not duplicate recovered alert
    mgr.process_snapshot(
        UsageSnapshot(
            provider="claude",
            display_name="Claude",
            windows=[UsageWindow(label="Weekly", key="weekly", used_pct=0.0)],
        )
    )
    assert len(notifications) == 2
    assert "quota reset (0% used)" in notifications[1][1]


def test_independent_windows_do_not_interfere(qapp: object, tmp_path: Path) -> None:
    settings = Settings(thresholds=[75, 90])
    mgr = NotificationManager(settings, state_path=tmp_path / "notifications.json")

    notifications: list[tuple[str, str, object]] = []
    mgr.notify.connect(lambda title, msg, icon: notifications.append((title, msg, icon)))

    # 5h window crosses 75%, Weekly is at 20%
    mgr.process_snapshot(
        UsageSnapshot(
            provider="claude",
            display_name="Claude",
            windows=[
                UsageWindow(label="5h", key="5h", used_pct=78.0),
                UsageWindow(label="Weekly", key="weekly", used_pct=20.0),
            ],
        )
    )
    assert len(notifications) == 1
    assert "Claude (5h): 78% quota used" in notifications[0][1]

    # 5h moves to 80% (silent), Weekly crosses 75% at 76% (alerts)
    mgr.process_snapshot(
        UsageSnapshot(
            provider="claude",
            display_name="Claude",
            windows=[
                UsageWindow(label="5h", key="5h", used_pct=80.0),
                UsageWindow(label="Weekly", key="weekly", used_pct=76.0),
            ],
        )
    )
    assert len(notifications) == 2
    assert "Claude (Weekly): 76% quota used" in notifications[1][1]


def test_usage_drop_below_threshold_rearms(qapp: object, tmp_path: Path) -> None:
    settings = Settings(thresholds=[75, 90])
    mgr = NotificationManager(settings, state_path=tmp_path / "notifications.json")

    notifications: list[tuple[str, str, object]] = []
    mgr.notify.connect(lambda title, msg, icon: notifications.append((title, msg, icon)))

    # Cross 75%
    mgr.process_snapshot(
        UsageSnapshot(
            provider="cursor",
            display_name="Cursor",
            windows=[UsageWindow(label="Pro", key="pro", used_pct=78.0)],
        )
    )
    assert len(notifications) == 1

    # Drop below 75% (to 70%) -> re-arms 75
    mgr.process_snapshot(
        UsageSnapshot(
            provider="cursor",
            display_name="Cursor",
            windows=[UsageWindow(label="Pro", key="pro", used_pct=70.0)],
        )
    )
    assert len(notifications) == 1

    # Cross 75% again -> fires again
    mgr.process_snapshot(
        UsageSnapshot(
            provider="cursor",
            display_name="Cursor",
            windows=[UsageWindow(label="Pro", key="pro", used_pct=77.0)],
        )
    )
    assert len(notifications) == 2


def test_provider_status_expired_and_recovery(qapp: object, tmp_path: Path) -> None:
    settings = Settings()
    mgr = NotificationManager(settings, state_path=tmp_path / "notifications.json")

    notifications: list[tuple[str, str, object]] = []
    mgr.notify.connect(lambda title, msg, icon: notifications.append((title, msg, icon)))

    # Expired status
    mgr.process_snapshot(
        UsageSnapshot(
            provider="deepseek",
            display_name="DeepSeek",
            status=ProviderStatus.EXPIRED,
        )
    )
    assert len(notifications) == 1
    assert "DeepSeek: quota depleted or rate limited" in notifications[0][1]
    assert notifications[0][2] == QSystemTrayIcon.MessageIcon.Warning

    # Expired again -> no duplicate
    mgr.process_snapshot(
        UsageSnapshot(
            provider="deepseek",
            display_name="DeepSeek",
            status=ProviderStatus.EXPIRED,
        )
    )
    assert len(notifications) == 1

    # Recovered to OK
    mgr.process_snapshot(
        UsageSnapshot(
            provider="deepseek",
            display_name="DeepSeek",
            status=ProviderStatus.OK,
        )
    )
    assert len(notifications) == 2
    assert "DeepSeek: service recovered" in notifications[1][1]
    assert notifications[1][2] == QSystemTrayIcon.MessageIcon.Information


def test_toggles_disabled(qapp: object, tmp_path: Path) -> None:
    settings = Settings(notify_usage=False, notify_status=False)
    mgr = NotificationManager(settings, state_path=tmp_path / "notifications.json")

    notifications: list[tuple[str, str, object]] = []
    mgr.notify.connect(lambda title, msg, icon: notifications.append((title, msg, icon)))

    # Usage threshold crossing ignored
    mgr.process_snapshot(
        UsageSnapshot(
            provider="claude",
            display_name="Claude",
            windows=[UsageWindow(label="5h", key="5h", used_pct=85.0)],
        )
    )
    # Depletion ignored
    mgr.process_snapshot(
        UsageSnapshot(
            provider="claude",
            display_name="Claude",
            windows=[UsageWindow(label="5h", key="5h", used_pct=100.0)],
        )
    )
    # Status expired ignored
    mgr.process_snapshot(
        UsageSnapshot(
            provider="claude",
            display_name="Claude",
            status=ProviderStatus.EXPIRED,
        )
    )
    assert len(notifications) == 0


def test_provider_threshold_overrides(qapp: object, tmp_path: Path) -> None:
    settings = Settings(
        thresholds=[75, 90],
        provider_thresholds={"copilot": [80, 95]},
    )
    mgr = NotificationManager(settings, state_path=tmp_path / "notifications.json")

    notifications: list[tuple[str, str, object]] = []
    mgr.notify.connect(lambda title, msg, icon: notifications.append((title, msg, icon)))

    # Copilot at 78% -> does not fire because Copilot override starts at 80%
    mgr.process_snapshot(
        UsageSnapshot(
            provider="copilot",
            display_name="Copilot",
            windows=[UsageWindow(label="Premium", key="premium", used_pct=78.0)],
        )
    )
    assert len(notifications) == 0

    # Copilot at 82% -> fires override threshold 80%
    mgr.process_snapshot(
        UsageSnapshot(
            provider="copilot",
            display_name="Copilot",
            windows=[UsageWindow(label="Premium", key="premium", used_pct=82.0)],
        )
    )
    assert len(notifications) == 1
    assert "Copilot (Premium): 82% quota used" in notifications[0][1]


def test_credits_fallback_window(qapp: object, tmp_path: Path) -> None:
    settings = Settings(thresholds=[75, 90])
    mgr = NotificationManager(settings, state_path=tmp_path / "notifications.json")

    notifications: list[tuple[str, str, object]] = []
    mgr.notify.connect(lambda title, msg, icon: notifications.append((title, msg, icon)))

    # Provider with only credits
    mgr.process_snapshot(
        UsageSnapshot(
            provider="openrouter",
            display_name="OpenRouter",
            windows=[],
            credits=Credits(display="$5.00", used_pct=82.0),
        )
    )
    assert len(notifications) == 1
    assert "OpenRouter (Credits): 82% quota used" in notifications[0][1]


def test_stale_and_loading_snapshots_ignored(qapp: object, tmp_path: Path) -> None:
    settings = Settings()
    mgr = NotificationManager(settings, state_path=tmp_path / "notifications.json")

    notifications: list[tuple[str, str, object]] = []
    mgr.notify.connect(lambda title, msg, icon: notifications.append((title, msg, icon)))

    # Stale snapshot
    mgr.process_snapshot(
        UsageSnapshot(
            provider="claude",
            display_name="Claude",
            stale=True,
            windows=[UsageWindow(label="5h", key="5h", used_pct=90.0)],
        )
    )
    # Loading snapshot
    mgr.process_snapshot(
        UsageSnapshot(
            provider="claude",
            display_name="Claude",
            status=ProviderStatus.LOADING,
            windows=[UsageWindow(label="5h", key="5h", used_pct=90.0)],
        )
    )
    assert len(notifications) == 0


def test_persistence_across_instances(qapp: object, tmp_path: Path) -> None:
    state_file = tmp_path / "notifications.json"
    settings = Settings(thresholds=[75, 90])

    # Instance 1 fires 75%
    mgr1 = NotificationManager(settings, state_path=state_file)
    mgr1.process_snapshot(
        UsageSnapshot(
            provider="claude",
            display_name="Claude",
            windows=[UsageWindow(label="5h", key="5h", used_pct=78.0)],
        )
    )

    # State file should exist and contain fired threshold
    loaded_state = load_notification_state(state_file)
    assert "claude:5h" in loaded_state.windows
    assert loaded_state.windows["claude:5h"].fired_thresholds == [75]

    # Instance 2 starts with existing state
    mgr2 = NotificationManager(settings, state_path=state_file)
    notifications: list[tuple[str, str, object]] = []
    mgr2.notify.connect(lambda title, msg, icon: notifications.append((title, msg, icon)))

    # Same usage does not re-fire
    mgr2.process_snapshot(
        UsageSnapshot(
            provider="claude",
            display_name="Claude",
            windows=[UsageWindow(label="5h", key="5h", used_pct=80.0)],
        )
    )
    assert len(notifications) == 0


def test_save_and_load_notification_state_corrupt_fallback(tmp_path: Path) -> None:
    file = tmp_path / "notifications.json"
    state = NotificationState(
        windows={"claude:5h": WindowNotificationState(fired_thresholds=[75, 90])},
        provider_expired={"deepseek": True},
    )
    save_notification_state(state, file)

    loaded = load_notification_state(file)
    assert loaded.windows["claude:5h"].fired_thresholds == [75, 90]
    assert loaded.provider_expired["deepseek"] is True

    # Corrupt file falls back to empty state
    file.write_text("{corrupt json", encoding="utf-8")
    assert load_notification_state(file).windows == {}
