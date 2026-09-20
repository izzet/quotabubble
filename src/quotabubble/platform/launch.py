from __future__ import annotations

import sys


def launch_arguments() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, "-m", "quotabubble"]


def launch_command() -> str:
    return " ".join(f'"{argument}"' for argument in launch_arguments())
