"""Stały pasek LIVE: start, sceny, kill, throw, syrena, sweep, master, mierniki."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from dsp.crossover import ALL_WAYS, WAY_LABELS
from dsp.isolator import BANDS
from presets import store as preset_store

from ..theme import GOLD, RED
from ..widgets import Knob, LevelMeter, MomentaryButton, ToggleButton


class LivePanel(QFrame):
    startToggled = Signal(bool)
    settingsClicked = Signal()
    sceneActivated = Signal(int)
    saveSceneClicked = Signal()
    deleteSceneClicked = Signal()

    def __init__(self, bridge):
        super().__init__()
        self.bridge = bridge
        self.setObjectName("liveStrip")
        self.setFrameShape(QFrame.StyledPanel)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(8)

        self.start_btn = QPushButton("START")
        self.start_btn.setCheckable(True)
        self.start_btn.setMinimumWidth(88)
        self.start_btn.setMinimumHeight(44)
        self.start_btn.setFocusPolicy(Qt.NoFocus)
        self.start_btn.toggled.connect(self.startToggled.emit)
        lay.addWidget(self.start_btn)

        scene_box = QVBoxLayout()
        scene_box.setSpacing(2)
        cap = QLabel("Scena")
        cap.setProperty("role", "caption")
        self.scene_combo = QComboBox()
        self.scene_combo.setMinimumWidth(160)
        self.scene_combo.setFocusPolicy(Qt.NoFocus)
        self.scene_combo.activated.connect(self.sceneActivated.emit)
        row = QHBoxLayout()
        save = QPushButton("Zapisz")
        delete = QPushButton("Usuń")
        for b in (save, delete):
            b.setFocusPolicy(Qt.NoFocus)
        save.clicked.connect(self.saveSceneClicked.emit)
        delete.clicked.connect(self.deleteSceneClicked.emit)
        row.addWidget(self.scene_combo, 1)
        row.addWidget(save)
        row.addWidget(delete)
        scene_box.addWidget(cap)
        scene_box.addLayout(row)
        lay.addLayout(scene_box)

        settings = QPushButton("Audio…")
        settings.setFocusPolicy(Qt.NoFocus)
        settings.clicked.connect(self.settingsClicked.emit)
        lay.addWidget(settings)

        kills = QHBoxLayout()
        kills.setSpacing(3)
        for i, b in enumerate(BANDS):
            btn = MomentaryButton(bridge, f"iso.kill.{b}", f"KILL {i + 1}", kill=True)
            btn.setMinimumHeight(40)
            btn.setMinimumWidth(58)
            kills.addWidget(btn)
        lay.addLayout(kills)

        for key, text in (
            ("echo.throw", "THROW"),
            ("preamp.cut", "DRY CUT"),
            ("siren.trigger", "SYRENA"),
            ("spring.crash", "CRASH"),
            ("out.fx_panic", "FX PANIC"),
        ):
            btn = MomentaryButton(bridge, key, text)
            btn.setMinimumHeight(40)
            btn.setMinimumWidth(72)
            lay.addWidget(btn)

        self.hp = Knob(bridge, "preamp.hp", size=40, label="Sweep HP")
        self.lp = Knob(bridge, "preamp.lp", size=40, label="Sweep LP")
        self.master = Knob(bridge, "out.master", size=44, label="Master", color=GOLD)
        lay.addWidget(self.hp)
        lay.addWidget(self.lp)
        lay.addWidget(self.master)
        lay.addWidget(ToggleButton(bridge, "out.mute", "MUTE"))

        self.meters = {"in": LevelMeter("IN", height=44)}
        lay.addWidget(self.meters["in"])
        for w in ALL_WAYS:
            m = LevelMeter(WAY_LABELS[w], height=44)
            self.meters[w] = m
            lay.addWidget(m)
        self.meters["out"] = LevelMeter("OUT", height=44)
        lay.addWidget(self.meters["out"])
        self.clip_label = QLabel("")
        self.clip_label.setStyleSheet(f"color: {RED.name()}; font-weight: bold;")
        lay.addWidget(self.clip_label)
        lay.addStretch(1)
        self.reload_scenes()

    def reload_scenes(self, select: str | None = None) -> None:
        self.scene_combo.clear()
        for name, builtin in preset_store.list_scenes():
            self.scene_combo.addItem(name if builtin else f"{name} *", name)
        if select:
            idx = self.scene_combo.findData(select)
            if idx >= 0:
                self.scene_combo.setCurrentIndex(idx)

    def set_running(self, running: bool) -> None:
        self.start_btn.blockSignals(True)
        self.start_btn.setChecked(running)
        self.start_btn.blockSignals(False)
        self.start_btn.setText("STOP" if running else "START")

    def update_meters(self, chain) -> None:
        if chain is None:
            for m in self.meters.values():
                m.set_db(-60.0)
            self.clip_label.setText("")
            return
        self.meters["in"].set_linear(chain.tap_in.peak)
        for w in ALL_WAYS:
            self.meters[w].set_linear(chain.taps[w].peak if w in chain.xo.ways else 0.0)
        self.meters["out"].set_linear(chain.tap_out.peak)
        clip = any(m.clipping for m in self.meters.values())
        self.clip_label.setText("CLIP" if clip else "")
