from __future__ import annotations

from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from dsp.crossover import ALL_WAYS, SPLITS_BY_COUNT, WAY_LABELS, WAYS_BY_COUNT

from ..theme import WAY_COLORS
from .base import Panel, hbox


class CrossoverPanel(Panel):
    def __init__(self, bridge):
        super().__init__(bridge, "ZWROTNICA", max_width=380)
        c = self.ctl
        self.add(hbox(c("xo.ways"), c("xo.slope")), 0, 0, 1, 4)
        self.splits = {k: c(k) for k in ("xo.f1", "xo.f2", "xo.f3")}
        for i, w in enumerate(self.splits.values()):
            self.add(w, 1, i)
        self.add(hbox(c("xo.subsonic"), c("xo.subsonic_hz", label="HP")), 1, 3)
        self.columns = {}
        for i, way in enumerate(ALL_WAYS):
            col = QWidget()
            lay = QVBoxLayout(col)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(2)
            title = QLabel(WAY_LABELS[way].upper())
            title.setStyleSheet(f"color: {WAY_COLORS[way]}; font-weight: bold;")
            lay.addWidget(title)
            lay.addWidget(c(f"xo.gain.{way}", label="Gain", color=WAY_COLORS[way], size=36))
            lay.addWidget(c(f"xo.delay.{way}", label="Delay", size=36))
            lay.addWidget(c(f"xo.invert.{way}", label="Faza Ø"))
            lay.addWidget(c(f"xo.mute.{way}", label="Mute"))
            col.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
            col.setMinimumWidth(68)
            col.setMaximumWidth(78)
            self.columns[way] = col
            self.add(col, 2, i)
        bridge.watch("xo.ways", lambda _v: self._update_enabled())
        self._update_enabled()

    def _update_enabled(self) -> None:
        count = (2, 3, 4)[int(self.bridge.get("xo.ways"))]
        active = WAYS_BY_COUNT[count]
        for way, col in self.columns.items():
            col.setEnabled(way in active)
        for key, w in self.splits.items():
            w.setEnabled(key in SPLITS_BY_COUNT[count])
