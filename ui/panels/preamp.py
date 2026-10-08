from __future__ import annotations

from ..theme import RED
from .base import Panel, hbox


class PreampPanel(Panel):
    def __init__(self, bridge):
        super().__init__(bridge, "PREAMP", max_width=280)
        c = self.ctl
        self.add(hbox(c("preamp.enabled", label="Włączony"), c("preamp.mono")), 0, 0, 1, 3)
        self.add(c("preamp.gain"), 1, 0)
        self.add(c("preamp.drive", color=RED), 1, 1)
        self.add(c("preamp.bias"), 1, 2)
        self.add(c("preamp.bass"), 2, 0)
        self.add(c("preamp.treble"), 2, 1)
        self.add(c("preamp.res"), 2, 2)
        self.add(c("preamp.hp", size=48), 3, 0, 1, 1)
        self.add(c("preamp.lp", size=48), 3, 1, 1, 1)
        self.add(c("preamp.master"), 3, 2)
        self.add(c("preamp.echo_send"), 4, 0)
        self.add(c("preamp.spring_send"), 4, 1)
