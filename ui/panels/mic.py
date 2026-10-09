from __future__ import annotations

from PySide6.QtWidgets import QLabel

from ..widgets import LevelMeter, MomentaryButton
from .base import Panel, hbox


class MicPanel(Panel):
    def __init__(self, bridge):
        super().__init__(bridge, "MIC / MC", max_width=260)
        c = self.ctl
        self.add(hbox(c("mic.enabled", label="Włączony"), c("mic.hp")), 0, 0, 1, 3)
        self.add(c("mic.gain"), 1, 0)
        self.add(c("mic.gate"), 1, 1)
        self.meter = LevelMeter("MIC")
        self.add(self.meter, 1, 2, 2, 1)
        self.add(c("mic.comp_thresh"), 2, 0)
        self.add(c("mic.comp_ratio"), 2, 1)
        self.add(c("mic.eq_low"), 3, 0)
        self.add(c("mic.eq_mid"), 3, 1)
        self.add(c("mic.eq_high"), 3, 2)
        self.add(c("mic.level"), 4, 0)
        self.add(c("mic.echo_send"), 4, 1)
        self.add(c("mic.talkover_depth", label="Talkover"), 4, 2)
        self.add(c("mic.talkover", label="Talkover ON"), 5, 0, 1, 2)
        throw = MomentaryButton(bridge, "mic.throw", "THROW")
        throw.setToolTip("Przytrzymaj: mikrofon w całości do echa (klawisz V)")
        self.add(throw, 5, 2)
        self.info = QLabel("GR: 0.0 dB | latencja: —")
        self.info.setProperty("role", "caption")
        self.add(self.info, 6, 0, 1, 3)

    def update_meters(self, level_db: float, gr_db: float, latency_ms: float | None) -> None:
        self.meter.set_db(level_db)
        lat = f"{latency_ms:.0f} ms" if latency_ms else "—"
        self.info.setText(f"GR: {gr_db:.1f} dB | latencja: {lat}")
