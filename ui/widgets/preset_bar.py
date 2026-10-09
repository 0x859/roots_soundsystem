"""Pasek presetów (EQ, syrena) dla stołu klasycznego: lista, zapis, usuwanie własnych, reset."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QInputDialog, QMessageBox, QPushButton, QWidget

from presets.store import PRESET_KINDS


class _PresetCombo(QComboBox):
    """Lista odświeżana przed rozwinięciem – widzi też presety zapisane w interfejsie QML."""

    def __init__(self, bar: PresetBar):
        super().__init__()
        self._bar = bar

    def showPopup(self) -> None:
        self._bar.reload(self.currentData())
        super().showPopup()


class PresetBar(QWidget):
    def __init__(self, bridge, kind: str, combo_width: int = 110, buttons: bool = True):
        super().__init__()
        self.bridge = bridge
        self.kind = PRESET_KINDS[kind]
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self.combo = _PresetCombo(self)
        self.combo.setFocusPolicy(Qt.NoFocus)
        self.combo.setMaximumWidth(combo_width)
        self.combo.setPlaceholderText(f"{self.kind.title.capitalize()}…")
        self.combo.setToolTip(f"Wybór od razu ustawia {self.kind.title}")
        self.combo.activated.connect(self._apply)
        lay.addWidget(self.combo, 1)
        if buttons:
            for text, slot in (("Zapisz", self._save), ("Usuń", self._delete), ("Reset", self._reset)):
                b = QPushButton(text)
                b.setFocusPolicy(Qt.NoFocus)
                b.setMaximumWidth(56)
                b.clicked.connect(slot)
                lay.addWidget(b)
        self.reload()

    def reload(self, select: str | None = None) -> None:
        self.combo.blockSignals(True)
        self.combo.clear()
        for name, builtin in self.kind.list():
            self.combo.addItem(name if builtin else f"{name} *", name)
        idx = self.combo.findData(select) if select else -1
        self.combo.setCurrentIndex(idx)
        self.combo.blockSignals(False)

    def _apply(self, idx: int) -> None:
        name = self.combo.itemData(idx)
        if name is not None:
            self.bridge.store.set_many(self.kind.values(self.bridge.store, name), source="gui")

    def _save(self) -> None:
        name, ok = QInputDialog.getText(self, f"Zapisz {self.kind.title}", "Nazwa:")
        if ok and name.strip():
            self.kind.save(name.strip(), self.bridge.store)
            self.reload(name.strip())

    def _delete(self) -> None:
        name = self.combo.currentData()
        if name is None:
            return
        if self.kind.is_builtin(name):
            QMessageBox.information(self, "Presety", "Wbudowanych presetów nie można usunąć.")
            return
        self.kind.delete(name)
        self.reload()

    def _reset(self) -> None:
        self.bridge.store.reset(list(self.kind.keys), source="gui")
        self.combo.setCurrentIndex(-1)
