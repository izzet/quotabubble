from __future__ import annotations

from quotabubble.ui.icon import app_icon


def test_app_icon_includes_a_high_resolution_variant(qapp: object) -> None:
    sizes = {size.width() for size in app_icon().availableSizes()}

    assert 256 in sizes
