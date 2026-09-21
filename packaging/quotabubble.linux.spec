# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

PACKAGING_ROOT = Path(SPECPATH)
PROJECT_ROOT = PACKAGING_ROOT.parent
LINUX_ROOT = PACKAGING_ROOT / "linux"

hiddenimports = [
    "dbus_fast.aio",
    "dbus_fast.service",
    "keyring.backends.SecretService",
]

service_analysis = Analysis(
    [str(LINUX_ROOT / "service_launcher.py")],
    pathex=[str(PROJECT_ROOT / "src")],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
settings_analysis = Analysis(
    [str(LINUX_ROOT / "settings_launcher.py")],
    pathex=[str(PROJECT_ROOT / "src")],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

service_pyz = PYZ(service_analysis.pure)
settings_pyz = PYZ(settings_analysis.pure)

service_exe = EXE(
    service_pyz,
    service_analysis.scripts,
    [],
    exclude_binaries=True,
    name="quotabubble-service",
    console=True,
)
settings_exe = EXE(
    settings_pyz,
    settings_analysis.scripts,
    [],
    exclude_binaries=True,
    name="quotabubble-settings",
    console=False,
)

coll = COLLECT(
    service_exe,
    settings_exe,
    service_analysis.binaries,
    service_analysis.datas,
    settings_analysis.binaries,
    settings_analysis.datas,
    strip=False,
    upx=False,
    name="QuotaBubble-linux",
)
