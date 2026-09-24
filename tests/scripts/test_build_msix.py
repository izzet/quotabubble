from __future__ import annotations

import importlib.util
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parents[2] / "scripts"
spec = importlib.util.spec_from_file_location("build_msix", SCRIPTS / "build_msix.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

NS = {"m": "http://schemas.microsoft.com/appx/manifest/foundation/windows10"}


def _template() -> str:
    return module.MANIFEST_TEMPLATE.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("version", "expected"),
    [("0.2.5", "0.2.5.0"), ("1.10.3", "1.10.3.0"), ("0.3.1rc1", "0.3.1.0")],
)
def test_msix_version_is_four_part_with_a_zero_revision(version: str, expected: str) -> None:
    assert module.msix_version(version) == expected


@pytest.mark.parametrize("version", ["", "abc", "1.2", "v1.2.3"])
def test_msix_version_rejects_versions_it_cannot_map(version: str) -> None:
    with pytest.raises(ValueError):
        module.msix_version(version)


def test_project_version_matches_a_mappable_semver() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+\.0", module.msix_version(module.project_version()))


def test_manifest_template_is_well_formed_and_carries_the_store_identity() -> None:
    root = ET.fromstring(module.render_manifest(_template(), version="0.2.5.0"))
    identity = root.find("m:Identity", NS)

    assert identity.get("Name") == "IzzetYildirim.QuotaBubble"
    assert identity.get("Publisher") == "CN=E1463893-3649-4A22-A89E-F87D3AB31299"
    assert identity.get("Version") == "0.2.5.0"
    assert root.find("m:Properties/m:PublisherDisplayName", NS).text == "Izzet Yildirim"


def test_manifest_placeholder_is_replaced_everywhere() -> None:
    assert "__VERSION__" in _template()
    assert "__VERSION__" not in module.render_manifest(_template(), version="1.2.3.0")


def test_every_asset_the_manifest_references_is_generated() -> None:
    referenced = {
        Path(name.replace("\\", "/")).name for name in re.findall(r"Assets\\[\w.\-]+", _template())
    }
    generated = set(module.logo_files())

    assert referenced
    assert referenced <= generated


def test_logo_variants_scale_and_target_sizes_are_consistent() -> None:
    files = module.logo_files()

    assert files["Square150x150Logo.png"] == 150
    assert files["Square150x150Logo.scale-200.png"] == 300
    assert files["StoreLogo.scale-200.png"] == 100
    assert files["Square44x44Logo.targetsize-256_altform-unplated.png"] == 256


def test_find_makeappx_prefers_path_then_the_newest_sdk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for version in ("10.0.17134.0", "10.0.26100.0", "10.0.9999.0"):
        tool = tmp_path / "Windows Kits" / "10" / "bin" / version / "x64" / "makeappx.exe"
        tool.parent.mkdir(parents=True)
        tool.touch()

    monkeypatch.setattr(module.shutil, "which", lambda name: None)
    assert "10.0.26100.0" in str(module.find_makeappx((tmp_path,)))

    monkeypatch.setattr(module.shutil, "which", lambda name: "C:/tools/makeappx.exe")
    assert module.find_makeappx((tmp_path,)) == Path("C:/tools/makeappx.exe")


def test_find_makeappx_reports_a_missing_sdk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(module.shutil, "which", lambda name: None)

    with pytest.raises(FileNotFoundError, match="Windows SDK"):
        module.find_makeappx((tmp_path,))


def _fake_build(tmp_path: Path) -> Path:
    source = tmp_path / "dist" / "QuotaBubble"
    (source / "_internal").mkdir(parents=True)
    (source / "QuotaBubble.exe").write_bytes(b"exe")
    (source / "_internal" / "lib.dll").write_bytes(b"dll")
    return source


def test_stage_copies_the_build_and_adds_manifest_and_assets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(module, "write_assets", lambda directory: directory.mkdir(parents=True))
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "stale.txt").write_text("left over")

    module.stage(_fake_build(tmp_path), staging, version="0.2.5.0")

    assert (staging / "QuotaBubble.exe").read_bytes() == b"exe"
    assert (staging / "_internal" / "lib.dll").is_file()
    assert (staging / "Assets").is_dir()
    assert 'Version="0.2.5.0"' in (staging / "AppxManifest.xml").read_text(encoding="utf-8")
    assert not (staging / "stale.txt").exists()


def test_stage_rejects_a_source_without_the_executable(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()

    with pytest.raises(FileNotFoundError, match=r"QuotaBubble\.exe"):
        module.stage(empty, tmp_path / "staging", version="0.2.5.0")


def test_build_packs_the_staging_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(module, "write_assets", lambda directory: directory.mkdir(parents=True))
    monkeypatch.setattr(module, "find_makeappx", lambda: Path("makeappx.exe"))
    monkeypatch.setattr(module.subprocess, "run", lambda command, check: calls.append(command))
    output = tmp_path / "out" / "QuotaBubble.msix"

    module.build(
        _fake_build(tmp_path), output, version="0.2.5.0", staging=tmp_path / "staging"
    )

    assert calls == [
        ["makeappx.exe", "pack", "/d", str(tmp_path / "staging"), "/p", str(output), "/o"]
    ]
    assert output.parent.is_dir()


def test_write_assets_renders_valid_pngs_at_the_right_sizes(
    qapp: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from PySide6.QtGui import QImage

    monkeypatch.syspath_prepend(str(SCRIPTS))

    module.write_assets(tmp_path / "Assets")

    for name, size in module.logo_files().items():
        image = QImage(str(tmp_path / "Assets" / name))
        assert (image.width(), image.height()) == (size, size), name
