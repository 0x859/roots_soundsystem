from __future__ import annotations

from PySide6.QtWidgets import QLabel

from .base import Panel


class OutputPanel(Panel):
    """Limiter mastera i status trybu (reszta w LIVE i ustawieniach audio)."""

    def __init__(self, bridge):
        super().__init__(bridge, "WYJŚCIE", max_width=180)
        self.mode_label = QLabel()
        self.mode_label.setStyleSheet("font-weight: bold;")
        self.add(self.mode_label, 0, 0)
        self.add(self.ctl("out.limit"), 1, 0)
        hint = QLabel("Master, mute i mierniki: pasek LIVE.\nMapowanie kanałów: Ustawienia audio.")
        hint.setProperty("role", "caption")
        hint.setWordWrap(True)
        self.add(hint, 2, 0)
        self.set_mode("sim")

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.mode_label.setText("Tryb: SYMULACJA" if mode == "sim" else "Tryb: MULTI")
