from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_TEMPLATE = ROOT / "packaging" / "msix" / "AppxManifest.xml.tmpl"
_SDK_GLOB = "Windows Kits/10/bin/*/x64/makeappx.exe"
_SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)")

# Logo sizes the manifest refers to. Windows picks the best match by scale and
# target size, so the base name plus a 200% variant covers the common displays.
_LOGO_BASES = {"StoreLogo": 50, "Square150x150Logo": 150, "Square44x44Logo": 44}
_TASKBAR_SIZES = (16, 24, 32, 48, 256)


def project_version() -> str:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return str(pyproject["project"]["version"])


def msix_version(version: str) -> str:
    """Map 'X.Y.Z' to the four-part MSIX version.

    The Store reserves the fourth part and requires it to be 0.
    """
    match = _SEMVER.match(version)
    if match is None:
        raise ValueError(f"Cannot derive an MSIX version from {version!r}")
    major, minor, patch = match.groups()
    return f"{major}.{minor}.{patch}.0"


def render_manifest(template: str, *, version: str) -> str:
    return template.replace("__VERSION__", version)


def logo_files() -> dict[str, int]:
    """Asset file name -> pixel size, for every logo variant we ship."""
    files: dict[str, int] = {}
    for name, size in _LOGO_BASES.items():
        files[f"{name}.png"] = size
        files[f"{name}.scale-200.png"] = size * 2
    for size in _TASKBAR_SIZES:
        files[f"Square44x44Logo.targetsize-{size}.png"] = size
        files[f"Square44x44Logo.targetsize-{size}_altform-unplated.png"] = size
    return files


def find_makeappx(program_files: tuple[Path, ...] | None = None) -> Path:
    found = shutil.which("makeappx")
    if found:
        return Path(found)
    roots = program_files or (
        Path("C:/Program Files (x86)"),
        Path("C:/Program Files"),
    )
    candidates = sorted(
        (path for root in roots for path in root.glob(_SDK_GLOB)),
        key=lambda path: [int(part) if part.isdigit() else 0 for part in path.parts[-3].split(".")],
    )
    if not candidates:
        raise FileNotFoundError("makeappx.exe not found; install the Windows SDK")
    return candidates[-1]


def write_assets(directory: Path) -> None:
    from make_icon import _png_bytes
    from PySide6.QtGui import QGuiApplication

    QGuiApplication.instance() or QGuiApplication([])
    directory.mkdir(parents=True, exist_ok=True)
    for name, size in logo_files().items():
        (directory / name).write_bytes(_png_bytes(size))


def stage(source: Path, staging: Path, *, version: str) -> None:
    if not (source / "QuotaBubble.exe").is_file():
        raise FileNotFoundError(f"{source} does not contain QuotaBubble.exe")
    if staging.exists():
        shutil.rmtree(staging)
    shutil.copytree(source, staging)
    manifest = render_manifest(MANIFEST_TEMPLATE.read_text(encoding="utf-8"), version=version)
    (staging / "AppxManifest.xml").write_text(manifest, encoding="utf-8")
    write_assets(staging / "Assets")


def build(source: Path, output: Path, *, version: str, staging: Path) -> None:
    stage(source, staging, version=version)
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [str(find_makeappx()), "pack", "/d", str(staging), "/p", str(output), "/o"],
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Microsoft Store MSIX package.")
    parser.add_argument("--source", type=Path, default=ROOT / "dist" / "QuotaBubble")
    parser.add_argument("--output", type=Path, default=ROOT / "QuotaBubble-windows-x64.msix")
    parser.add_argument("--version", help="MSIX version (default: derived from pyproject.toml)")
    parser.add_argument("--staging", type=Path, default=ROOT / "build" / "msix-staging")
    args = parser.parse_args()
    version = args.version or msix_version(project_version())
    build(args.source, args.output, version=version, staging=args.staging)
    print(f"wrote {args.output} (version {version})", file=sys.stderr)


if __name__ == "__main__":
    main()
