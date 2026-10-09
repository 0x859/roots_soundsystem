from __future__ import annotations

from PySide6.QtCore import QSettings, QSize, Qt
from PySide6.QtWidgets import QApplication, QGridLayout, QGroupBox, QHBoxLayout, QPushButton, QWidget

from ..dub_actions import N_MEMORIES, TapTempo, recall_siren_memory, store_siren_memory
from ..theme import GREEN, RED
from ..widgets import MomentaryButton, PresetBar, make_control

__all__ = ["N_MEMORIES", "DubPanel"]


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
        self._tap = TapTempo(bridge.store)
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
        g.addWidget(throw, 3, 2)
        swell = MomentaryButton(self.bridge, "echo.swell", "SWELL")
        swell.setMinimumHeight(22)
        swell.setToolTip("Przytrzymaj: sprzężenie rośnie do samooscylacji, puść – wraca (klawisz W)")
        g.addWidget(swell, 3, 3)
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
        g.addWidget(PresetBar(self.bridge, "siren", combo_width=170), 3, 0, 1, 4)
        g.addWidget(mem, 4, 0, 1, 4)
        trig = MomentaryButton(self.bridge, "siren.trigger", "SYRENA")
        trig.setMinimumHeight(22)
        g.addWidget(trig, 5, 0, 1, 4)
        return box

    def _memory_clicked(self, i: int) -> None:
        if QApplication.keyboardModifiers() & Qt.ControlModifier:
            self.store_memory(i)
        else:
            self.recall_memory(i)

    def store_memory(self, i: int) -> None:
        store_siren_memory(self.bridge.store, self.settings, i)

    def recall_memory(self, i: int) -> None:
        recall_siren_memory(self.bridge.store, self.settings, i)

    def tap_tempo(self) -> None:
        self._tap.tap()
