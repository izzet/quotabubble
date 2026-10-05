"""Keep the provider list in the README, the website, and the vendored icons in sync.

The website renders its "Works with your tools" grid from
``website/src/data/providers.json``. The README mirrors the same list as a table.
These tests fail if the two drift apart, a vendor icon goes missing, or the
provider order changes in only one place.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROVIDERS_JSON = ROOT / "website" / "src" / "data" / "providers.json"
AGENTS_DIR = ROOT / "website" / "public" / "agents"
README = ROOT / "README.md"

SECTION_HEADING = "## Works with your tools"


def _providers() -> list[dict]:
    return json.loads(PROVIDERS_JSON.read_text(encoding="utf-8"))["providers"]


def _strip_emphasis(text: str) -> str:
    return text.replace("`", "").strip()


def _readme_rows() -> list[tuple[str, str]]:
    text = README.read_text(encoding="utf-8")
    heading = re.search(rf"^{re.escape(SECTION_HEADING)}\s*$", text, re.MULTILINE)
    assert heading, f"README is missing the {SECTION_HEADING!r} section"

    section = text[heading.end() :]
    next_heading = re.search(r"^## ", section, re.MULTILINE)
    if next_heading:
        section = section[: next_heading.start()]

    rows: list[tuple[str, str]] = []
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 2 or cells[0] in {"Tool", "Provider"}:
            continue
        if set(cells[0]) <= set("-: "):
            continue
        rows.append((cells[0], cells[1]))
    return rows


def test_readme_lists_the_same_providers_in_the_same_order() -> None:
    providers = _providers()
    rows = _readme_rows()
    assert [provider["name"] for provider in providers] == [name for name, _ in rows]


def test_readme_documents_every_credential_source() -> None:
    documented = "\n".join(_strip_emphasis(cell) for _, cell in _readme_rows())
    for provider in _providers():
        assert provider["credential"] in documented, (
            f"{provider['name']} credential source is not documented in the README"
        )


def test_every_provider_icon_is_vendored() -> None:
    for provider in _providers():
        icon = provider["icon"]
        if icon is None:
            continue
        assert (AGENTS_DIR / f"{icon}.svg").is_file(), (
            f"missing vendored icon for {provider['name']}: {icon}.svg"
        )
