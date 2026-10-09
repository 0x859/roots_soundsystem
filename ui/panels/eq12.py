from __future__ import annotations

from PySide6.QtWidgets import QSizePolicy

from dsp.eq12 import BANDS, band_label

from ..widgets import ParamSlider, PresetBar
from .base import Panel, hbox


class EQ12Panel(Panel):
    def __init__(self, bridge):
        super().__init__(bridge, "EQ 12-PASMOWY", max_width=430)
        self.presets = PresetBar(bridge, "eq")
        self.add(hbox(self.ctl("eq.enabled", label="EQ"), self.presets), 0, 0, 1, 13)
        sliders = [ParamSlider(bridge, "eq.preamp", "PRE", height=90)]
        sliders += [ParamSlider(bridge, f"eq.b{i}", band_label(f), height=90) for i, f in enumerate(BANDS)]
        for i, sl in enumerate(sliders):
            sl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
            self.add(sl, 1, i)
