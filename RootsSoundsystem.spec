# -*- mode: python ; coding: utf-8 -*-
"""Pakiet onedir: EXE + ikona + DLL (PortAudio, libsndfile, Qt)."""

import re
import sys
from pathlib import Path

from PyInstaller.building.api import COLLECT, EXE, PYZ
from PyInstaller.building.build_main import Analysis
from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

ROOT = Path(SPECPATH)
sys.path.insert(0, str(ROOT))
from version import APP_NAME, VERSION, version_tuple  # noqa: E402

# zasób wersji EXE (Właściwości → Szczegóły); język polski, Unicode
VERSION_INFO = VSVersionInfo(
    ffi=FixedFileInfo(filevers=version_tuple(), prodvers=version_tuple()),
    kids=[
        StringFileInfo([
            StringTable("041504B0", [
                StringStruct("CompanyName", APP_NAME),
                StringStruct("FileDescription", f"{APP_NAME} – cyfrowy tor roots and culture"),
                StringStruct("FileVersion", VERSION),
                StringStruct("InternalName", "RootsSoundsystem"),
                StringStruct("OriginalFilename", "RootsSoundsystem.exe"),
                StringStruct("ProductName", APP_NAME),
                StringStruct("ProductVersion", VERSION),
            ])
        ]),
        VarFileInfo([VarStruct("Translation", [0x0415, 1200])]),
    ],
)

datas = [(str(ROOT / "assets" / "icon.ico"), "assets")]
# interfejs QML (pliki .qml obok modułu ui.quick) i opcjonalne czcionki OFL
datas += [(str(ROOT / "ui" / "quick" / "qml" / "*.qml"), "ui/quick/qml")]
if any((ROOT / "assets" / "fonts").glob("*.[ot]tf")):
    datas += [(str(ROOT / "assets" / "fonts" / "*.*tf"), "assets/fonts")]
binaries = []
hiddenimports = [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtNetwork",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuickWidgets",
    "PySide6.QtQuickControls2",
    "ui.quick.view",
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
    "engine.audio_engine",
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
    hiddenimports += [m for m in collected_hidden if not re.search(r"\.(tests?|examples|docs)(\.|$)", m)]

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

# --- odchudzenie paczki ---------------------------------------------------------------------------
# Hooki PySide6 zbierają wszystkie moduły QML razem z ich DLL (sam WebEngine to ~200 MB). Interfejs
# używa tylko QtQuick + Controls (styl Basic) + Layouts + Shapes, a pyqtgraph – OpenGL, Svg i Test.
# Lista rodzin jest czarna (nie biała), żeby nowy, potrzebny moduł nie wypadł po cichu; braki
# zależności wyłapuje autotest `--selftest` uruchamiany przez build_exe.ps1.
QT_UNUSED = (
    "3D", "Quick3D", "Charts", "DataVisualization", "Graphs", "Multimedia", "SpatialAudio", "Location",
    "Positioning", "Sensors", "TextToSpeech", "RemoteObjects", "Scxml", "StateMachine", "VirtualKeyboard",
    "WebEngine", "WebChannel", "WebSockets", "WebView", "Pdf", "Labs", "ShaderTools", "Sql", "QuickTest",
    "QuickParticles", "QuickTimeline", "QuickDialogs2", "QuickVectorImage", "QuickShapesDesignHelpers",
    "QmlLocalStorage", "QmlXmlListModel", "QuickControls2Fusion", "QuickControls2Imagine",
    "QuickControls2Material", "QuickControls2Universal", "QuickControls2FluentWinUI3", "QuickControls2Windows",
)
QT_UNUSED_DLL = re.compile(r"PySide6/(Qt6|Qt)(" + "|".join(QT_UNUSED) + r")[^/]*\.(dll|pyd)$", re.I)
QML_KEEP = re.compile(r"PySide6/qml/(QtQml|QtQuick)/")
QML_UNUSED = re.compile(
    r"PySide6/qml/(QtQml/(StateMachine|XmlListModel)"
    r"|QtQuick/(VirtualKeyboard|NativeStyle|Dialogs|Pdf|Scene2D|Scene3D|Particles|Timeline|LocalStorage"
    r"|VectorImage|tooling|Shapes/DesignHelpers|Controls/(Fusion|Imagine|Material|Universal|FluentWinUI3|Windows|designer)))/"
)
OTHER_UNUSED = re.compile(
    r"PySide6/(translations|plugins/(qmltooling|platforminputcontexts)|plugins/imageformats/qpdf)"
    r"|/(tests?|examples|docs)/"
)


def unused(dest: str) -> bool:
    d = dest.replace("\\", "/")
    if d.startswith("PySide6/qml/"):
        return not QML_KEEP.match(d) or bool(QML_UNUSED.match(d))
    return bool(QT_UNUSED_DLL.match(d) or OTHER_UNUSED.search("/" + d))


a.binaries = [e for e in a.binaries if not unused(e[0])]
a.datas = [e for e in a.datas if not unused(e[0])]

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
    version=VERSION_INFO,
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
