# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules


ROOT = Path(SPECPATH)
RELEASE_DATA = ROOT / "build" / "release_data" / "data"

datas = [
    (str(RELEASE_DATA), "data"),
]

hiddenimports = []
hiddenimports += collect_submodules("src.skills")
hiddenimports += [
    "pystray._win32",
    "pyttsx3.drivers",
    "pyttsx3.drivers.sapi5",
    "pythoncom",
    "pywintypes",
    "win32com",
    "win32com.client",
]

binaries = []
binaries += collect_dynamic_libs("vosk")

excludes = [
    "matplotlib",
    "pandas",
    "pytest",
    "IPython",
]

a = Analysis(
    ["ui.py"],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CryAssistant",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="CryAssistant",
)
