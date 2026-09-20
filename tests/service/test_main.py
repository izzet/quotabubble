from __future__ import annotations

from quotabubble.service import main


def test_main_constructs_and_runs_service(monkeypatch) -> None:
    calls: list[object] = []
    settings = object()
    runtime = object()

    class _Settings:
        @classmethod
        def load(cls) -> object:
            return settings

    class _Runtime:
        def __new__(cls, received_settings: object) -> object:
            calls.append(received_settings)
            return runtime

    class _Service:
        def __init__(self, received_runtime: object) -> None:
            calls.append(received_runtime)

        async def run(self) -> None:
            calls.append("run")

    monkeypatch.setattr(main, "setup_logging", lambda: calls.append("logging"))
    monkeypatch.setattr(main, "Settings", _Settings)
    monkeypatch.setattr(main, "ServiceRuntime", _Runtime)
    monkeypatch.setattr(main, "DbusService", _Service)

    main.main()

    assert calls == ["logging", settings, runtime, "run"]
