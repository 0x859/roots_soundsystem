# -*- mode: python ; coding: utf-8 -*-
"""Pakiet onedir: EXE + ikona + DLL (PortAudio, libsndfile, Qt)."""

from pathlib import Path

from PyInstaller.building.api import COLLECT, EXE, PYZ
from PyInstaller.building.build_main import Analysis
from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs

ROOT = Path(SPECPATH)

datas = [(str(ROOT / "assets" / "icon.ico"), "assets")]
binaries = []
hiddenimports = [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtNetwork",
    "sounddevice",
    "soundfile",
    "numpy",
    "scipy",
    "scipy.signal",
    "scipy.signal.windows",
    "pyqtgraph",
    "numba",
    "llvmlite",
    "mido",
    "pygame",
    "pygame.midi",
    "presets",
    "presets.store",
    "presets.builtin",
    "engine.audio",
    "engine.midi",
    "engine.params",
    "dsp.graph",
    "dsp.jit",
]

for pkg in ("sounddevice", "soundfile", "scipy", "numba", "llvmlite", "pygame", "pyqtgraph"):
    try:
        collected_datas, collected_binaries, collected_hidden = collect_all(pkg)
    except Exception:
        continue
    datas += collected_datas
    binaries += collected_binaries
    hiddenimports += collected_hidden

for pkg in ("sounddevice", "soundfile"):
    try:
        binaries += collect_dynamic_libs(pkg)
    except Exception:
        pass

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "tkinter"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="RootsSoundsystem",
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
    icon=str(ROOT / "assets" / "icon.ico"),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="RootsSoundsystem",
)
