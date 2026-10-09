from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from dsp.isolator import BAND_LABELS, BANDS

from ..widgets import MomentaryButton, ParamSlider
from .base import Panel, hbox


class IsolatorPanel(Panel):
    def __init__(self, bridge):
        super().__init__(bridge, "IZOLATOR 5-DROŻNY", max_width=360)
        c = self.ctl
        self.add(hbox(c("iso.enabled", label="Włączony"), c("iso.slope")), 0, 0, 1, 5)
        for i, b in enumerate(BANDS):
            col = QWidget()
            lay = QVBoxLayout(col)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.addWidget(ParamSlider(bridge, f"iso.g.{b}", BAND_LABELS[b], height=90))
            kill = MomentaryButton(bridge, f"iso.kill.{b}", f"KILL {i + 1}", kill=True)
            kill.setMaximumWidth(56)
            lay.addWidget(kill)
            self.add(col, 1, i)
        for i in range(4):
            self.add(c(f"iso.f{i + 1}", label=f"f{i + 1}", size=32), 2, i)
