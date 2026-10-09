"""Osadzenie interfejsu QML w oknie Widgets (QQuickWidget) na czas migracji."""

from __future__ import annotations

from pathlib import Path

import shiboken6
from PySide6.QtCore import QUrl
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtQuickWidgets import QQuickWidget

from .audio import QmlAudio
from .layout_model import LayoutModel, load_bundled_fonts
from .params import QmlParams
from .plots import QmlPlots
from .session import QmlSession


def qml_dir() -> Path:
    return Path(__file__).resolve().parent / "qml"


class QuickDesk(QQuickWidget):
    """Ekran LIVE / KONFIGURACJA w QML; kontekst: `Params`, `Profile`, `Theme`, `Session`, `Plots`, `Audio`."""

    def __init__(self, params: QmlParams, layout: LayoutModel, session: QmlSession, plots: QmlPlots | None = None,
                 audio: QmlAudio | None = None, parent=None):
        QQuickStyle.setStyle("Basic")
        load_bundled_fonts()
        super().__init__(parent)
        self.params = params
        self.layout = layout
        self.session = session
        self.plots = plots if plots is not None else QmlPlots(self)
        self.audio = audio if audio is not None else QmlAudio(params.bridge.store, list, self)
        ctx = self.rootContext()
        ctx.setContextProperty("Params", params)
        ctx.setContextProperty("Profile", layout)
        ctx.setContextProperty("Theme", layout.theme)
        ctx.setContextProperty("Session", session)
        ctx.setContextProperty("Plots", self.plots)
        ctx.setContextProperty("Audio", self.audio)
        self.setResizeMode(QQuickWidget.SizeRootObjectToView)
        self.setClearColor(layout.theme.bg)
        layout.theme.changed.connect(lambda: self.setClearColor(layout.theme.bg))
        self.setSource(QUrl.fromLocalFile(str(qml_dir() / "Main.qml")))
        # obiekty kontekstu muszą żyć dłużej niż scena, inaczej przy niszczeniu okna wiązania QML
        # trafią na null; dzieci widżetu są usuwane dopiero po scenie
        for obj in (params, layout, session, self.plots, self.audio):
            obj.setParent(self)

    def shutdown(self, *_args) -> None:
        """Wyładowuje scenę QML (bez błędów wiązań przy niszczeniu obiektów kontekstu)."""
        if self.source().isEmpty():
            return
        root = self.rootObject()
        self.setSource(QUrl())
        # korzeń jest normalnie usuwany z opóźnieniem – do tego czasu jego wiązania wciąż by się przeliczały
        if root is not None and shiboken6.isValid(root):
            shiboken6.delete(root)

    def error_text(self) -> str:
        return "\n".join(e.toString() for e in self.errors())

    @property
    def ok(self) -> bool:
        return self.status() == QQuickWidget.Ready and not self.errors()
