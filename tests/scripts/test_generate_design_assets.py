from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).parents[2] / "scripts" / "generate_design_assets.py"
spec = importlib.util.spec_from_file_location("generate_design_assets", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_alpha_color_renders_alpha_first_for_qt():
    token = {"$type": "color", "$value": "#ffffff", "$alpha": 34}
    assert module._render_value(token, alpha_first=True) == "#22ffffff"


def test_alpha_color_renders_alpha_last_for_web():
    token = {"$type": "color", "$value": "#ffffff", "$alpha": 34}
    assert module._render_value(token, alpha_first=False) == "#ffffff22"


def test_opaque_color_is_unaffected_by_alpha_first():
    token = {"$type": "color", "$value": "#5ec584"}
    assert module._render_value(token, alpha_first=True) == "#5ec584"
    assert module._render_value(token, alpha_first=False) == "#5ec584"


def test_non_color_value_passes_through_unchanged():
    token = {"$type": "number", "$value": 14}
    assert module._render_value(token, alpha_first=True) == 14


def test_render_walks_nested_groups():
    source = {
        "color": {
            "track": {"$type": "color", "$value": "#ffffff", "$alpha": 34},
            "ok": {"$type": "color", "$value": "#5ec584"},
        }
    }
    result = module._render(source, alpha_first=True)
    assert result == {"color": {"track": "#22ffffff", "ok": "#5ec584"}}


def test_qt_parses_rendered_color_with_intended_alpha(qapp):
    from PySide6.QtGui import QColor

    token = {"$type": "color", "$value": "#ffffff", "$alpha": 34}
    color = QColor(module._render_value(token, alpha_first=True))
    assert (color.red(), color.green(), color.blue(), color.alpha()) == (255, 255, 255, 34)
