"""Skalowanie stołu do rozmiaru okna (bez zmiany układu)."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QTimer
from PySide6.QtWidgets import QApplication

from .theme import apply_scaled_stylesheet
from .widgets import Knob, LevelMeter, ParamSlider

MIN_SCALE = 0.7
MAX_SCALE = 1.4


class DeskScaler(QObject):
    """Obserwuje kontener i skaluje pokrętła, suwaki, mierniki oraz czcionki."""

    def __init__(self, viewport, content):
        super().__init__(viewport)
        self.viewport = viewport
        self.content = content
        self.scale = 1.0
        self.natural_w = 0
        self.natural_h = 0
        self._busy = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(150)
        self._timer.timeout.connect(self.apply)
        viewport.installEventFilter(self)

    def eventFilter(self, obj, ev):
        if obj is self.viewport and ev.type() == QEvent.Resize:
            self._timer.start()
        return False

    def measure_natural(self) -> None:
        app = QApplication.instance()
        if app is not None:
            apply_scaled_stylesheet(app, 1.0)
        self._set_widget_scale(1.0)
        self.content.adjustSize()
        hint = self.content.sizeHint()
        self.natural_w = max(1, hint.width())
        self.natural_h = max(1, hint.height())

    def apply(self) -> None:
        if self._busy:
            return
        avail = self.viewport.size()
        if avail.width() <= 1 or avail.height() <= 1:
            return
        self._busy = True
        try:
            if self.natural_w <= 0 or self.natural_h <= 0:
                self.measure_natural()
            scale = min(avail.width() / self.natural_w, avail.height() / self.natural_h)
            scale = max(MIN_SCALE, min(MAX_SCALE, scale))
            self.scale = scale
            self._set_widget_scale(scale)
            app = QApplication.instance()
            if app is not None:
                apply_scaled_stylesheet(app, scale)
        finally:
            self._busy = False

    def _set_widget_scale(self, factor: float) -> None:
        for w in self.content.findChildren(Knob):
            w.set_scale(factor)
        for w in self.content.findChildren(ParamSlider):
            w.set_scale(factor)
        for w in self.content.findChildren(LevelMeter):
            w.set_scale(factor)
        self.content.updateGeometry()
