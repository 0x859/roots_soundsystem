"""Pionowy suwak pasma/tłumika: etykieta, bieżąca wartość, dwuklik resetuje."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSlider, QVBoxLayout, QWidget

RESOLUTION = 1000


class _Slider(QSlider):
    def __init__(self, owner):
        super().__init__(Qt.Vertical)
        self.owner = owner

    def mouseDoubleClickEvent(self, e):
        self.owner.reset()


class ParamSlider(QWidget):
    def __init__(self, bridge, key: str, label: str | None = None, height: int = 140):
        super().__init__()
        self.bridge = bridge
        self.key = key
        self.spec = bridge.spec(key)
        self._base_height = height
        self._base_width = 32
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 0, 2, 0)
        lay.setSpacing(2)
        self.value_label = QLabel()
        self.value_label.setProperty("role", "value")
        self.value_label.setAlignment(Qt.AlignCenter)
        self.slider = _Slider(self)
        self.slider.setRange(0, RESOLUTION)
        self.slider.setMinimumHeight(height)
        self.slider.setPageStep(RESOLUTION // 20)
        self.slider.valueChanged.connect(self._on_slider)
        cap = QLabel(label or self.spec.label)
        cap.setProperty("role", "caption")
        cap.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.value_label)
        lay.addWidget(self.slider, 1, Qt.AlignHCenter)
        lay.addWidget(cap)
        self.setFixedWidth(self._base_width)
        self.setToolTip(f"{self.spec.label} ({key})\nDwuklik: wartość domyślna")
        bridge.watch(key, self._on_value)
        self._on_value(bridge.get(key))

    def _on_value(self, value) -> None:
        self.slider.blockSignals(True)
        self.slider.setValue(int(round(self.spec.to_norm(value) * RESOLUTION)))
        self.slider.blockSignals(False)
        self.value_label.setText(self.spec.format(value))

    def _on_slider(self, pos: int) -> None:
        self.bridge.set(self.key, self.spec.from_norm(pos / RESOLUTION))

    def reset(self) -> None:
        self.bridge.set(self.key, self.spec.default)

    def set_scale(self, factor: float) -> None:
        self.slider.setMinimumHeight(max(40, int(round(self._base_height * factor))))
        self.setFixedWidth(max(22, int(round(self._base_width * factor))))
