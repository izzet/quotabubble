# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
from tomllib import loads

from PyInstaller.utils.hooks import collect_submodules

PACKAGING_ROOT = Path(SPECPATH)
PROJECT_ROOT = PACKAGING_ROOT.parent
VERSION = loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"][
    "version"
]

a = Analysis(
    [str(PACKAGING_ROOT / "launcher.py")],
    pathex=[str(PROJECT_ROOT / "src")],
    binaries=[],
    datas=[],
    # keyring discovers its platform backend through entry points. Collecting
    # its macOS package preserves Keychain support in the frozen app.
    hiddenimports=collect_submodules("keyring.backends.macOS"),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="QuotaBubble",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)

app = BUNDLE(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    name="QuotaBubble.app",
    icon=str(PROJECT_ROOT / "assets" / "quotabubble.icns"),
    bundle_identifier="com.izzet.quotabubble",
    info_plist={
        "CFBundleDisplayName": "QuotaBubble",
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "LSUIElement": True,
        "NSHighResolutionCapable": True,
    },
)
