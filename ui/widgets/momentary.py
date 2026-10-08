"""Przycisk chwilowy (aktywny tylko przy przytrzymaniu); prawy klik zatrzaskuje."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton


class MomentaryButton(QPushButton):
    def __init__(self, bridge, key: str, text: str | None = None, kill: bool = False):
        super().__init__(text or bridge.spec(key).label)
        self.bridge = bridge
        self.key = key
        self.latched = False
        self.setProperty("momentary", "true")
        if kill:
            self.setProperty("kill", "true")
        self.setFocusPolicy(Qt.NoFocus)
        self.setToolTip(f"{self.text()}: przytrzymaj (lewy przycisk) lub zatrzaśnij (prawy przycisk)")
        bridge.watch(key, self._on_value)
        self._on_value(bridge.get(key))

    def _on_value(self, value) -> None:
        self.setProperty("active", "true" if value else "false")
        if not value:
            self.latched = False
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.latched = False
            self.bridge.set(self.key, True)
        elif e.button() == Qt.RightButton:
            self.latched = not self.latched
            self.bridge.set(self.key, self.latched)
        e.accept()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and not self.latched:
            self.bridge.set(self.key, False)
        e.accept()
