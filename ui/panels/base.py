from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QGridLayout, QGroupBox, QHBoxLayout, QWidget

from ..widgets import make_control


class Panel(QGroupBox):
    def __init__(self, bridge, title: str, max_width: int | None = None):
        super().__init__(title)
        self.bridge = bridge
        self._max_hint_w = max_width
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(6, 10, 6, 6)
        self.grid.setHorizontalSpacing(3)
        self.grid.setVerticalSpacing(3)

    def sizeHint(self) -> QSize:
        hint = super().sizeHint()
        if self._max_hint_w is not None:
            return QSize(min(hint.width(), self._max_hint_w), hint.height())
        return hint

    def minimumSizeHint(self) -> QSize:
        hint = super().minimumSizeHint()
        if self._max_hint_w is not None:
            return QSize(min(hint.width(), self._max_hint_w), hint.height())
        return hint

    def ctl(self, key: str, **kw):
        return make_control(self.bridge, key, **kw)

    def add(self, widget, row: int, col: int, rowspan: int = 1, colspan: int = 1):
        self.grid.addWidget(widget, row, col, rowspan, colspan)
        return widget


def hbox(*widgets, spacing: int = 4) -> QWidget:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(spacing)
    for x in widgets:
        lay.addWidget(x)
    return w
