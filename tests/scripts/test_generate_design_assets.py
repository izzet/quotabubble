from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).parents[2] / "scripts" / "generate_design_assets.py"
spec = importlib.util.spec_from_file_location("generate_design_assets", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_alpha_hex_moves_alpha_to_front_for_qt():
    assert module._to_qt_alpha_order("#ffffff22") == "#22ffffff"
    assert module._to_qt_alpha_order("#ffffff28") == "#28ffffff"


def test_opaque_hex_is_left_unchanged():
    assert module._to_qt_alpha_order("#5ec584") == "#5ec584"


def test_non_color_values_are_left_unchanged():
    assert module._to_qt_alpha_order(14) == 14
    assert module._to_qt_alpha_order(None) is None


def test_nested_dicts_are_converted_recursively():
    result = module._to_qt_alpha_order({"track": "#ffffff22", "ok": "#5ec584"})
    assert result == {"track": "#22ffffff", "ok": "#5ec584"}


def test_qt_parses_converted_colors_with_intended_alpha(qapp):
    from PySide6.QtGui import QColor

    color = QColor(module._to_qt_alpha_order("#ffffff22"))
    assert (color.red(), color.green(), color.blue(), color.alpha()) == (255, 255, 255, 34)
