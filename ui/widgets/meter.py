"""Pionowy miernik poziomu z pamięcią szczytu i wskaźnikiem przesterowania."""

from __future__ import annotations

import math
import time

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

FLOOR_DB = -60.0
CLIP_DB = -0.3
CLIP_HOLD_S = 1.5


class _Bar(QWidget):
    def __init__(self):
        super().__init__()
        self.db = FLOOR_DB
        self.peak_db = FLOOR_DB
        self.clip_until = 0.0
        self.setMinimumSize(14, 90)

    def sizeHint(self) -> QSize:
        return QSize(max(14, self.minimumWidth()), max(40, self.minimumHeight()))

    def paintEvent(self, _):
        p = QPainter(self)
        r = self.rect().adjusted(1, 6, -1, -1)
        p.fillRect(r, QColor("#101215"))
        frac = (self.db - FLOOR_DB) / -FLOOR_DB
        h = r.height() * max(0.0, min(1.0, frac))
        g = QLinearGradient(0, r.bottom(), 0, r.top())
        g.setColorAt(0.0, QColor("#2a9d38"))
        g.setColorAt(0.75, QColor("#f7b801"))
        g.setColorAt(1.0, QColor("#d62828"))
        p.fillRect(QRectF(r.left(), r.bottom() - h, r.width(), h), g)
        pf = (self.peak_db - FLOOR_DB) / -FLOOR_DB
        y = r.bottom() - r.height() * max(0.0, min(1.0, pf))
        p.fillRect(QRectF(r.left(), y - 1, r.width(), 2), QColor("#f0f0f0"))
        clip = time.monotonic() < self.clip_until
        p.fillRect(QRectF(r.left(), 0, r.width(), 5), QColor("#d62828") if clip else QColor("#3a1e1e"))
        p.end()


class LevelMeter(QWidget):
    def __init__(self, label: str, height: int = 90):
        super().__init__()
        self._base_h = height
        lay = QVBoxLayout(self)
        lay.setContentsMargins(1, 0, 1, 0)
        lay.setSpacing(1)
        self.bar = _Bar()
        self.bar.setMinimumSize(14, height)
        cap = QLabel(label)
        cap.setProperty("role", "caption")
        cap.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.bar, 1, Qt.AlignHCenter)
        lay.addWidget(cap)

    def set_linear(self, peak: float) -> None:
        self.set_db(20 * math.log10(peak) if peak > 1e-6 else FLOOR_DB)

    def set_db(self, db: float) -> None:
        b = self.bar
        b.db = max(FLOOR_DB, db) if db > b.db else max(FLOOR_DB, b.db - 1.5)
        b.peak_db = db if db > b.peak_db else max(FLOOR_DB, b.peak_db - 0.3)
        if db >= CLIP_DB:
            b.clip_until = time.monotonic() + CLIP_HOLD_S
        b.update()

    @property
    def clipping(self) -> bool:
        return time.monotonic() < self.bar.clip_until

    def set_scale(self, factor: float) -> None:
        self.bar.setMinimumSize(max(8, int(round(14 * factor))), max(36, int(round(self._base_h * factor))))
