"""Edytor mapowania dróg zwrotnicy na kanały urządzenia wyjściowego."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QGridLayout, QLabel, QWidget

from dsp.crossover import ALL_WAYS, WAY_LABELS, WAYS_BY_COUNT
from dsp.graph import default_channel_map, validate_channel_map
from ..theme import WAY_COLORS
from .controls import make_control


class ChannelMapEditor(QWidget):
    mapChanged = Signal(dict)

    def __init__(self, bridge, n_channels: int = 8):
        super().__init__()
        self.bridge = bridge
        self.mode = "sim"
        self._n_channels = n_channels
        self._map = default_channel_map()
        self.combos: dict[str, tuple[QComboBox, QComboBox]] = {}
        lay = QGridLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setHorizontalSpacing(6)
        lay.setVerticalSpacing(4)
        hdr = QLabel("Kanały L / R i limiter dla każdej drogi")
        hdr.setProperty("role", "caption")
        lay.addWidget(hdr, 0, 0, 1, 4)
        for i, w in enumerate(ALL_WAYS):
            name = QLabel(WAY_LABELS[w])
            name.setStyleSheet(f"color: {WAY_COLORS[w]}; font-weight: bold;")
            left, right = QComboBox(), QComboBox()
            for cb in (left, right):
                cb.setFocusPolicy(Qt.NoFocus)
                cb.currentIndexChanged.connect(self._emit_map)
            lim = make_control(bridge, f"out.limit.{w}", label="Limit", size=36)
            self.combos[w] = (left, right)
            lay.addWidget(name, 1 + i, 0)
            lay.addWidget(left, 1 + i, 1)
            lay.addWidget(right, 1 + i, 2)
            lay.addWidget(lim, 1 + i, 3)
        self.problems = QLabel("")
        self.problems.setStyleSheet("color: #f77f00;")
        self.problems.setWordWrap(True)
        lay.addWidget(self.problems, 5, 0, 1, 4)
        self.set_device_channels(n_channels)
        bridge.watch("xo.ways", lambda _v: self._validate())

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.setEnabled(mode == "multi")
        self._validate()

    def set_device_channels(self, n: int) -> None:
        self._n_channels = max(0, int(n))
        for w, (left, right) in self.combos.items():
            for cb, ch in ((left, self._map.get(w, (-1, -1))[0]), (right, self._map.get(w, (-1, -1))[1])):
                cb.blockSignals(True)
                cb.clear()
                cb.addItem("—", -1)
                for k in range(self._n_channels):
                    cb.addItem(f"kan. {k + 1}", k)
                idx = cb.findData(ch)
                cb.setCurrentIndex(idx if idx >= 0 else 0)
                cb.blockSignals(False)
        self._validate()

    def set_channel_map(self, mapping: dict[str, tuple[int, int]]) -> None:
        self._map = {w: tuple(mapping.get(w, (-1, -1))) for w in ALL_WAYS}
        self.set_device_channels(self._n_channels)

    def channel_map(self) -> dict[str, tuple[int, int]]:
        return dict(self._map)

    def active_ways(self):
        return WAYS_BY_COUNT[(2, 3, 4)[int(self.bridge.get("xo.ways"))]]

    def _emit_map(self) -> None:
        self._map = {w: (l.currentData(), r.currentData()) for w, (l, r) in self.combos.items()}
        self._validate()
        self.mapChanged.emit(self.channel_map())

    def problems_list(self) -> list[str]:
        return validate_channel_map(self._map, self.active_ways(), self._n_channels)

    def _validate(self) -> None:
        if self.mode != "multi":
            self.problems.setText("")
            return
        probs = self.problems_list()
        self.problems.setText("\n".join(probs) if probs else "Mapowanie poprawne.")
