from __future__ import annotations

import json
import time

from PySide6.QtCore import QSettings, QSize, Qt
from PySide6.QtWidgets import QApplication, QGroupBox, QGridLayout, QHBoxLayout, QPushButton, QWidget

from dsp.fx_siren import SIREN_MEMORY_KEYS
from ..theme import GREEN, RED
from ..widgets import MomentaryButton, make_control

N_MEMORIES = 4
TAP_TIMEOUT_S = 2.0


class _Box(QGroupBox):
    def __init__(self, title):
        super().__init__(title)
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(4, 10, 4, 4)
        self.grid.setSpacing(4)


class DubPanel(QWidget):
    """Echo taśmowe, sprężyna i syrena obok siebie."""

    def __init__(self, bridge, settings: QSettings):
        super().__init__()
        self.bridge = bridge
        self.settings = settings
        self._taps: list[float] = []
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._echo())
        lay.addWidget(self._spring())
        lay.addWidget(self._siren())

    def sizeHint(self) -> QSize:
        hint = super().sizeHint()
        return QSize(min(hint.width(), 780), hint.height())

    def minimumSizeHint(self) -> QSize:
        hint = super().minimumSizeHint()
        return QSize(min(hint.width(), 780), hint.height())

    def c(self, key, **kw):
        return make_control(self.bridge, key, **kw)

    def _echo(self):
        box = _Box("ECHO TAŚMOWE")
        g = box.grid
        g.addWidget(self.c("echo.enabled", label="Włączone"), 0, 0, 1, 2)
        g.addWidget(self.c("echo.sync"), 0, 2, 1, 2)
        g.addWidget(self.c("echo.time", size=56), 1, 0)
        g.addWidget(self.c("echo.feedback", size=56, color=RED), 1, 1)
        g.addWidget(self.c("echo.bpm"), 1, 2)
        tap = QPushButton("TAP")
        tap.setFocusPolicy(Qt.NoFocus)
        tap.setToolTip("Stukaj w rytm, aby ustawić BPM (klawisz T)")
        tap.pressed.connect(self.tap_tempo)
        g.addWidget(tap, 1, 3)
        g.addWidget(self.c("echo.hp"), 2, 0)
        g.addWidget(self.c("echo.lp"), 2, 1)
        g.addWidget(self.c("echo.drive"), 2, 2)
        g.addWidget(self.c("echo.wow"), 2, 3)
        g.addWidget(self.c("echo.glide"), 3, 0)
        g.addWidget(self.c("echo.return"), 3, 1)
        throw = MomentaryButton(self.bridge, "echo.throw", "THROW")
        throw.setMinimumHeight(22)
        g.addWidget(throw, 3, 2, 1, 2)
        return box

    def _spring(self):
        box = _Box("SPRĘŻYNA")
        g = box.grid
        g.addWidget(self.c("spring.enabled", label="Włączona"), 0, 0)
        g.addWidget(self.c("spring.decay", size=56), 1, 0)
        g.addWidget(self.c("spring.tone"), 2, 0)
        g.addWidget(self.c("spring.return"), 3, 0)
        crash = MomentaryButton(self.bridge, "spring.crash", "CRASH")
        crash.setMinimumHeight(22)
        g.addWidget(crash, 4, 0)
        return box

    def _siren(self):
        box = _Box("SYRENA")
        g = box.grid
        g.addWidget(self.c("siren.wave"), 0, 0, 1, 2)
        g.addWidget(self.c("siren.lfo_shape"), 0, 2, 1, 2)
        g.addWidget(self.c("siren.pitch", size=56, color=GREEN), 1, 0)
        g.addWidget(self.c("siren.lfo_rate", size=56), 1, 1)
        g.addWidget(self.c("siren.lfo_depth"), 1, 2)
        g.addWidget(self.c("siren.sweep"), 1, 3)
        g.addWidget(self.c("siren.sweep_time"), 2, 0)
        g.addWidget(self.c("siren.release"), 2, 1)
        g.addWidget(self.c("siren.level"), 2, 2)
        g.addWidget(self.c("siren.echo_send"), 2, 3)
        mem = QWidget()
        ml = QHBoxLayout(mem)
        ml.setContentsMargins(0, 0, 0, 0)
        for i in range(N_MEMORIES):
            b = QPushButton(f"M{i + 1}")
            b.setFocusPolicy(Qt.NoFocus)
            b.setToolTip(f"Klik: przywołaj pamięć {i + 1} (F{5 + i}); Ctrl+klik: zapisz bieżące ustawienia syreny")
            b.clicked.connect(lambda _=False, i=i: self._memory_clicked(i))
            ml.addWidget(b)
        g.addWidget(mem, 3, 0, 1, 4)
        trig = MomentaryButton(self.bridge, "siren.trigger", "SYRENA")
        trig.setMinimumHeight(22)
        g.addWidget(trig, 4, 0, 1, 4)
        return box

    def _memory_clicked(self, i: int) -> None:
        if QApplication.keyboardModifiers() & Qt.ControlModifier:
            self.store_memory(i)
        else:
            self.recall_memory(i)

    def store_memory(self, i: int) -> None:
        data = {k: self.bridge.get(k) for k in SIREN_MEMORY_KEYS}
        self.settings.setValue(f"siren/mem{i}", json.dumps(data))

    def recall_memory(self, i: int) -> None:
        raw = self.settings.value(f"siren/mem{i}")
        if not raw:
            return
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            return
        self.bridge.store.set_many({k: data[k] for k in SIREN_MEMORY_KEYS if k in data}, source="gui")

    def tap_tempo(self) -> None:
        now = time.monotonic()
        self._taps = [t for t in self._taps if now - t < TAP_TIMEOUT_S] + [now]
        if len(self._taps) >= 2:
            diffs = [b - a for a, b in zip(self._taps, self._taps[1:])]
            bpm = 60.0 / (sum(diffs) / len(diffs))
            values = {"echo.bpm": bpm}
            if self.bridge.get("echo.sync") == 0:
                values["echo.time"] = 60000.0 / bpm
            self.bridge.store.set_many(values, source="gui")
