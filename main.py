"""Roots Soundsystem – cyfrowy tor soundsystemu roots and culture."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)
if FROZEN:
    ROOT = Path(sys.executable).resolve().parent
    sys.path.insert(0, getattr(sys, "_MEIPASS", str(ROOT)))
else:
    ROOT = Path(__file__).resolve().parent
    sys.path.insert(0, str(ROOT))

VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"

if not FROZEN and importlib.util.find_spec("PySide6") is None:
    if VENV_PYTHON.exists() and Path(sys.executable).resolve() != VENV_PYTHON.resolve():
        sys.exit(subprocess.call([str(VENV_PYTHON), str(ROOT / "main.py"), *sys.argv[1:]]))
    sys.exit(
        "Brak pakietu PySide6. Zainstaluj zależności:\n"
        "  python -m venv .venv\n"
        "  .\\.venv\\Scripts\\python -m pip install -r requirements.txt"
    )

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from dsp.graph import all_specs  # noqa: E402
from engine.params import ParamStore  # noqa: E402
from presets.store import restore_state  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402
from ui.theme import app_icon, apply_theme  # noqa: E402
from version import APP_USER_MODEL_ID, VERSION  # noqa: E402


def set_app_user_model_id() -> None:
    """Własny AppUserModelID: pasek zadań Windows pokazuje ikonę aplikacji, a nie Pythona (start z kodu)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except (AttributeError, OSError):
        pass


def selftest(path: str) -> int:
    """Sprawdzenie paczki (także EXE bez konsoli): ładowanie QML, ekrany, tryb edycji; wynik JSON do pliku.

    Działa na tymczasowych ustawieniach i profilach, nie startuje audio i nie pokazuje okna na ekranie.
    """
    import json
    import os
    import tempfile

    from PySide6.QtCore import Qt, qInstallMessageHandler

    tmp = tempfile.mkdtemp(prefix="roots_selftest_")
    os.environ["APPDATA"] = tmp
    messages: list[str] = []
    qInstallMessageHandler(lambda _mode, _ctx, text: messages.append(text))
    app = QApplication(sys.argv[:1])
    apply_theme(app)
    settings = QSettings(os.path.join(tmp, "settings.ini"), QSettings.IniFormat)
    store = ParamStore(all_specs())
    restore_state(store, None, "clean")
    win = MainWindow(store, settings, startup_checks=False)
    win.setAttribute(Qt.WA_DontShowOnScreen)
    win.show()

    def pump() -> None:
        for _ in range(8):
            app.processEvents()

    pump()
    steps = []
    if win.quick is not None:
        for screen in ("config", "live"):
            win.session.setProperty("screen", screen)
            pump()
            steps.append(screen)
        win.session.setProperty("editing", True)
        pump()
        win.session.setProperty("editing", False)
        pump()
        steps.append("edit")
    qml_problems = [m for m in messages if ".qml" in m or "TypeError" in m or "ReferenceError" in m]
    result = {
        "version": VERSION,
        "frozen": FROZEN,
        "qml_loaded": win.quick is not None,
        "qml_errors": win.quick.error_text() if win.quick is not None else "brak interfejsu QML",
        "qml_warnings": qml_problems,
        "view": win.view,
        "steps": steps,
        "fonts": {"label": win.layout_model.theme.property("labelFont"), "value": win.layout_model.theme.property("valueFont")},
        "dsp_on": win.session.property("dspOn"),
        "audio_backend": win.devices is not None,
        "devices": len(win.devices),
    }
    if win.quick is not None:
        win.quick.shutdown()
    win.engine.stop()
    win.midi.close()
    ok = result["qml_loaded"] and not qml_problems
    result["ok"] = ok
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    return 0 if ok else 1


def main() -> int:
    if "--selftest" in sys.argv:
        i = sys.argv.index("--selftest")
        out = sys.argv[i + 1] if i + 1 < len(sys.argv) else str(ROOT / "selftest.json")
        return selftest(out)
    set_app_user_model_id()
    app = QApplication(sys.argv)
    app.setOrganizationName("RootsSoundsystem")
    app.setApplicationName("RootsSoundsystem")
    app.setApplicationVersion(VERSION)
    app.setWindowIcon(app_icon())
    app.setQuitOnLastWindowClosed(False)
    apply_theme(app)

    settings = QSettings()
    store = ParamStore(all_specs())
    # domyślnie start z czystym torem (moduły DSP wyłączone); „last” przywraca ostatni stan w całości
    restore_state(store, settings.value("state/params"), settings.value("startup/dsp", "clean"))

    win = MainWindow(store, settings)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
