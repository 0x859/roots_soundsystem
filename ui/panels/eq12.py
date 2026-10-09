from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QInputDialog, QMessageBox, QPushButton, QSizePolicy

from dsp.eq12 import BANDS, band_label
from presets import store as preset_store

from ..widgets import ParamSlider
from .base import Panel, hbox


class EQ12Panel(Panel):
    def __init__(self, bridge):
        super().__init__(bridge, "EQ 12-PASMOWY", max_width=430)
        self.presets = QComboBox()
        self.presets.setFocusPolicy(Qt.NoFocus)
        self.presets.activated.connect(self._apply_preset)
        save = QPushButton("Zapisz")
        save.clicked.connect(self._save_preset)
        delete = QPushButton("Usuń")
        delete.clicked.connect(self._delete_preset)
        reset = QPushButton("Reset")
        reset.clicked.connect(lambda: bridge.store.reset(["eq.preamp"] + [f"eq.b{i}" for i in range(12)], source="gui"))
        for b in (save, delete, reset):
            b.setMaximumWidth(56)
        self.presets.setMaximumWidth(110)
        self.add(hbox(self.ctl("eq.enabled", label="EQ"), self.presets, save, delete, reset), 0, 0, 1, 13)
        sliders = [ParamSlider(bridge, "eq.preamp", "PRE", height=90)]
        sliders += [ParamSlider(bridge, f"eq.b{i}", band_label(f), height=90) for i, f in enumerate(BANDS)]
        for i, sl in enumerate(sliders):
            sl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
            self.add(sl, 1, i)
        self._reload()

    def _reload(self, select: str | None = None) -> None:
        self.presets.clear()
        for name, builtin in preset_store.list_eq_presets():
            self.presets.addItem(name if builtin else f"{name} *", name)
        if select:
            idx = self.presets.findData(select)
            if idx >= 0:
                self.presets.setCurrentIndex(idx)

    def _apply_preset(self, idx: int) -> None:
        name = self.presets.itemData(idx)
        values = {"eq.preamp": 0.0} | preset_store.eq_preset_values(name)
        self.bridge.store.set_many(values, source="gui")

    def _save_preset(self) -> None:
        name, ok = QInputDialog.getText(self, "Zapisz preset EQ", "Nazwa:")
        if ok and name.strip():
            preset_store.save_eq_preset(name.strip(), self.bridge.store)
            self._reload(name.strip())

    def _delete_preset(self) -> None:
        name = self.presets.currentData()
        if name is None:
            return
        if dict(preset_store.list_eq_presets()).get(name, True):
            QMessageBox.information(self, "EQ", "Wbudowanych presetów nie można usunąć.")
            return
        preset_store.delete_eq_preset(name)
        self._reload()
