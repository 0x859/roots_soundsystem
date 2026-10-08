"""Roots Soundsystem – cyfrowy tor soundsystemu roots and culture."""

from __future__ import annotations

import importlib.util
import json
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
from ui.main_window import MainWindow  # noqa: E402
from ui.theme import app_icon, apply_theme  # noqa: E402


def main() -> int:
    app = QApplication(sys.argv)
    app.setOrganizationName("RootsSoundsystem")
    app.setApplicationName("RootsSoundsystem")
    app.setWindowIcon(app_icon())
    app.setQuitOnLastWindowClosed(False)
    apply_theme(app)

    settings = QSettings()
    store = ParamStore(all_specs())
    raw = settings.value("state/params")
    if raw:
        try:
            store.load(json.loads(raw))
        except (TypeError, ValueError):
            pass

    win = MainWindow(store, settings)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
