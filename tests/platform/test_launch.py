from __future__ import annotations

import sys

from quotabubble.platform import launch


def test_launch_command_for_python_module(monkeypatch) -> None:
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setattr(sys, "executable", "/Applications/Python 3/bin/python")

    assert launch.launch_command() == '"/Applications/Python 3/bin/python" "-m" "quotabubble"'


def test_launch_arguments_for_frozen_application(monkeypatch) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    executable = "/Applications/QuotaBubble.app/Contents/MacOS/QuotaBubble"
    monkeypatch.setattr(sys, "executable", executable)

    assert launch.launch_arguments() == [executable]
