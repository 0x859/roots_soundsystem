"""Pokrętło powiązane z parametrem: przeciąganie w pionie, kółko myszy, dwuklik = wartość domyślna."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from ..theme import GOLD

START_DEG = 225.0
SPAN_DEG = 270.0


class _Dial(QWidget):
    def __init__(self, knob: Knob, size: int):
        super().__init__()
        self.knob = knob
        self._size = size
        self._drag_y = None
        self._drag_norm = 0.0
        self.setFixedSize(size, size)
        self.setCursor(Qt.SizeVerCursor)

    def sizeHint(self) -> QSize:
        return QSize(self._size, self._size)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        s = self._size
        m = 5
        rect = QRectF(m, m, s - 2 * m, s - 2 * m)
        norm = self.knob.norm
        p.setPen(QPen(QColor("#33373e"), 4, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(rect, int((START_DEG) * 16), int(-SPAN_DEG * 16))
        col = QColor(self.knob.color) if self.enabled_look() else QColor("#555")
        p.setPen(QPen(col, 4, Qt.SolidLine, Qt.RoundCap))
        origin = self.knob.origin_norm
        a0 = START_DEG - SPAN_DEG * origin
        p.drawArc(rect, int(a0 * 16), int(-SPAN_DEG * (norm - origin) * 16))
        inner = rect.adjusted(7, 7, -7, -7)
        g = QRadialGradient(inner.center() - QPointF(3, 3), inner.width() / 1.4)
        g.setColorAt(0, QColor("#4a4f58"))
        g.setColorAt(1, QColor("#1b1d21"))
        p.setPen(QPen(QColor("#111"), 1))
        p.setBrush(g)
        p.drawEllipse(inner)
        ang = math.radians(START_DEG - SPAN_DEG * norm)
        c = inner.center()
        r = inner.width() / 2 - 3
        p.setPen(QPen(QColor("#f0f0f0"), 2.5, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(c + QPointF(math.cos(ang) * r * 0.35, -math.sin(ang) * r * 0.35), c + QPointF(math.cos(ang) * r, -math.sin(ang) * r))
        p.end()

    def enabled_look(self) -> bool:
        return self.isEnabled()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_y = e.position().y()
            self._drag_norm = self.knob.norm

    def mouseMoveEvent(self, e):
        if self._drag_y is None:
            return
        dy = self._drag_y - e.position().y()
        fine = 0.25 if e.modifiers() & Qt.ShiftModifier else 1.0
        self.knob.set_norm(self._drag_norm + dy / 200.0 * fine)

    def mouseReleaseEvent(self, e):
        self._drag_y = None

    def mouseDoubleClickEvent(self, e):
        self.knob.reset()

    def wheelEvent(self, e):
        steps = e.angleDelta().y() / 120.0
        fine = 0.2 if e.modifiers() & Qt.ShiftModifier else 1.0
        self.knob.set_norm(self.knob.norm + steps * 0.02 * fine)


class Knob(QWidget):
    def __init__(self, bridge, key: str, size: int = 48, label: str | None = None, color=None):
        super().__init__()
        self.bridge = bridge
        self.key = key
        self.spec = bridge.spec(key)
        self.color = color or GOLD
        self._base_size = size
        self.norm = self.spec.to_norm(bridge.get(key))
        self.origin_norm = self.spec.to_norm(0.0) if self.spec.min < 0 < self.spec.max else 0.0
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 0, 2, 0)
        lay.setSpacing(1)
        cap = QLabel(label or self.spec.label)
        cap.setProperty("role", "caption")
        cap.setAlignment(Qt.AlignCenter)
        self.dial = _Dial(self, size)
        self.value_label = QLabel()
        self.value_label.setProperty("role", "value")
        self.value_label.setAlignment(Qt.AlignCenter)
        lay.addWidget(cap)
        lay.addWidget(self.dial, 0, Qt.AlignHCenter)
        lay.addWidget(self.value_label)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setToolTip(f"{self.spec.label} ({key})\nDwuklik: wartość domyślna, Shift: precyzyjnie")
        bridge.watch(key, self._on_value)
        self._on_value(bridge.get(key))

    def _on_value(self, value) -> None:
        self.norm = self.spec.to_norm(value)
        self.value_label.setText(self.spec.format(value))
        self.dial.update()

    def set_norm(self, norm: float) -> None:
        self.bridge.set(self.key, self.spec.from_norm(norm))

    def reset(self) -> None:
        self.bridge.set(self.key, self.spec.default)

    def set_scale(self, factor: float) -> None:
        s = max(16, int(round(self._base_size * factor)))
        self.dial._size = s
        self.dial.setFixedSize(s, s)
