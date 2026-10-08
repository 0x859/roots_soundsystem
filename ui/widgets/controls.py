"""Przełączniki, listy wyboru i fabryka kontrolek dla parametrów."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QLabel, QPushButton, QVBoxLayout, QWidget


class ToggleButton(QPushButton):
    def __init__(self, bridge, key: str, text: str | None = None):
        super().__init__(text or bridge.spec(key).label)
        self.bridge = bridge
        self.key = key
        self.setCheckable(True)
        self.setFocusPolicy(Qt.NoFocus)
        self.toggled.connect(lambda on: bridge.set(key, on))
        bridge.watch(key, self._on_value)
        self._on_value(bridge.get(key))

    def _on_value(self, value) -> None:
        self.blockSignals(True)
        self.setChecked(bool(value))
        self.blockSignals(False)


class ParamCombo(QWidget):
    def __init__(self, bridge, key: str, label: str | None = None, show_label: bool = True):
        super().__init__()
        self.bridge = bridge
        self.key = key
        spec = bridge.spec(key)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 0, 2, 0)
        lay.setSpacing(1)
        if show_label:
            cap = QLabel(label or spec.label)
            cap.setProperty("role", "caption")
            lay.addWidget(cap)
        self.combo = QComboBox()
        self.combo.addItems(list(spec.choices))
        self.combo.setFocusPolicy(Qt.NoFocus)
        self.combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.combo.setMinimumContentsLength(6)
        self.combo.setFixedWidth(130)
        self.combo.currentIndexChanged.connect(lambda i: bridge.set(key, i))
        lay.addWidget(self.combo)
        bridge.watch(key, self._on_value)
        self._on_value(bridge.get(key))

    def _on_value(self, value) -> None:
        self.combo.blockSignals(True)
        self.combo.setCurrentIndex(int(value))
        self.combo.blockSignals(False)


def make_control(bridge, key: str, **kw):
    from .knob import Knob
    from .momentary import MomentaryButton

    spec = bridge.spec(key)
    if spec.kind == "choice":
        return ParamCombo(bridge, key, kw.get("label"))
    if spec.kind == "bool":
        if spec.momentary:
            return MomentaryButton(bridge, key, kw.get("label"))
        return ToggleButton(bridge, key, kw.get("label"))
    return Knob(bridge, key, size=kw.get("size", 44), label=kw.get("label"), color=kw.get("color"))
