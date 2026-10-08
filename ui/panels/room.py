from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFileDialog, QLabel, QPushButton

from dsp.crossover import ALL_WAYS, WAY_LABELS
from .base import Panel, hbox


class RoomPanel(Panel):
    """Tryb Symulacja: modele kolumn (lewa kolumna) i akustyka miejsca (prawa)."""

    irFileChosen = Signal(str)

    def __init__(self, bridge):
        super().__init__(bridge, "KOLUMNY I MIEJSCE", max_width=340)
        c = self.ctl
        for i, w in enumerate(ALL_WAYS):
            self.add(c(f"sim.cab.{w}", label=WAY_LABELS[w]), i, 0)
        self.add(c("sim.cab_drive", size=36), 4, 0)
        self.add(c("room.preset", label="Miejsce"), 0, 1)
        self.add(c("room.mix", size=36), 1, 1)
        self.add(c("room.size", size=36), 2, 1)
        self.add(c("sim.bassfeel", size=36), 3, 1)
        self.add(hbox(c("sim.width", size=36), c("sim.sub_delay", size=36)), 4, 1)
        self.add(hbox(c("sim.mono_bass"), c("room.enabled", label="Akustyka")), 5, 0)
        load = QPushButton("Wczytaj IR…")
        load.clicked.connect(self._choose_ir)
        self.ir_label = QLabel("Własna IR: brak")
        self.ir_label.setProperty("role", "caption")
        self.ir_label.setWordWrap(True)
        self.add(load, 5, 1)

    def _choose_ir(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Wybierz odpowiedź impulsową", "", "Pliki audio (*.wav *.flac *.aiff *.ogg)")
        if path:
            self.irFileChosen.emit(path)

    def set_ir_path(self, path: str | None) -> None:
        self.ir_label.setText(f"IR: {Path(path).name}" if path else "Własna IR: brak")
