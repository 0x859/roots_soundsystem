"""Okno ustawień audio: urządzenia, tryb, blok, zasobnik, mapowanie Multi."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from engine.audio_engine import EngineConfig, list_devices
from engine.devices import input_pairs, preset, presets_for

from ..audio_config import BLOCKS, MODES, hints, mic_items, music_items, output_items, resolve_devices
from ..widgets.channel_map import ChannelMapEditor

__all__ = ["BLOCKS", "MODES", "AudioSettingsDialog", "resolve_saved_devices"]


def resolve_saved_devices(devices, settings) -> tuple[int | None, int | None, int | None]:
    """Zwraca (music_in, output, mic_in) na podstawie zapisanych etykiet."""
    return resolve_devices(devices, settings)


def _fill_combos(devices, music_cb, out_cb, mic_cb, settings) -> None:
    chosen = resolve_devices(devices, settings)
    for cb, items, data in ((music_cb, music_items(devices), chosen[0]), (out_cb, output_items(devices), chosen[1]),
                            (mic_cb, mic_items(devices), chosen[2])):
        cb.blockSignals(True)
        cb.clear()
        for text, value in items:
            cb.addItem(text, value)
        idx = cb.findData(data)
        cb.setCurrentIndex(max(0, idx))
        cb.blockSignals(False)


class AudioSettingsDialog(QDialog):
    def __init__(self, parent, bridge, settings, devices, mode: str, block: int, channel_map, tray_checked: bool, fs: int = 48000):
        super().__init__(parent)
        self.bridge = bridge
        self.settings = settings
        self.devices = devices
        self.fs = fs
        self.setWindowTitle("Ustawienia audio")
        self.setMinimumWidth(480)
        root = QVBoxLayout(self)

        form = QFormLayout()
        self.music_combo = QComboBox()
        self.out_combo = QComboBox()
        self.mic_combo = QComboBox()
        for cb in (self.music_combo, self.out_combo, self.mic_combo):
            cb.setFocusPolicy(Qt.NoFocus)
        self.mode_combo = QComboBox()
        for key, label in MODES:
            self.mode_combo.addItem(label, key)
        self.mode_combo.setCurrentIndex([m for m, _ in MODES].index(mode) if mode in dict(MODES) else 0)
        self.block_combo = QComboBox()
        for b in BLOCKS:
            self.block_combo.addItem(f"{b} próbek", b)
        if block in BLOCKS:
            self.block_combo.setCurrentIndex(BLOCKS.index(block))
        refresh = QPushButton("Odśwież urządzenia")
        refresh.clicked.connect(self.refresh_devices)
        self.tray_box = QCheckBox("Minimalizuj do zasobnika")
        self.tray_box.setChecked(tray_checked)
        self.music_pair = QComboBox()
        self.mic_chan = QComboBox()
        self.preset_combo = QComboBox()
        self._pending_ways: int | None = None
        self.mirror_box = QCheckBox("Symulacja: kopia na wyjścia 3–4 (np. słuchawki Scarlett 4i4)")
        self.mirror_box.setChecked(settings.value("audio/sim_mirror", "false") in (True, "true"))
        self.hint = QLabel("")
        self.hint.setWordWrap(True)
        self.hint.setProperty("role", "caption")
        form.addRow("Muzyka:", self.music_combo)
        form.addRow("Kanały muzyki:", self.music_pair)
        form.addRow("Wyjście:", self.out_combo)
        form.addRow("Gotowy układ:", self.preset_combo)
        form.addRow("", self.mirror_box)
        form.addRow("Mikrofon:", self.mic_combo)
        form.addRow("Kanał mikrofonu:", self.mic_chan)
        form.addRow("Tryb:", self.mode_combo)
        form.addRow("Blok:", self.block_combo)
        form.addRow("", refresh)
        form.addRow("", self.tray_box)
        form.addRow("", self.hint)
        root.addLayout(form)

        multi = QGroupBox("Multi: mapowanie kanałów")
        ml = QVBoxLayout(multi)
        self.channel_map = ChannelMapEditor(bridge)
        self.channel_map.set_channel_map(channel_map)
        self.channel_map.set_mode(mode)
        ml.addWidget(self.channel_map)
        root.addWidget(multi)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(buttons)
        root.addLayout(row)

        self.out_combo.currentIndexChanged.connect(self._on_output_changed)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self.music_combo.currentIndexChanged.connect(self._on_music_changed)
        self.mic_combo.currentIndexChanged.connect(self._on_mic_changed)
        self.preset_combo.activated.connect(self._apply_preset)
        self.refresh_devices()

    def refresh_devices(self) -> None:
        self.devices = list_devices()
        _fill_combos(self.devices, self.music_combo, self.out_combo, self.mic_combo, self.settings)
        self._on_output_changed()
        self._on_music_changed(initial=True)
        self._on_mic_changed(initial=True)

    def _device(self, index):
        return next((d for d in self.devices if d.index == index), None)

    def _on_output_changed(self, *_):
        dev = self._device(self.out_combo.currentData())
        n = dev.max_out if dev else 0
        self.channel_map.set_device_channels(n)
        self.preset_combo.clear()
        self.preset_combo.addItem("— własny —", None)
        for p in presets_for(n):
            self.preset_combo.addItem(p.label, p.key)
        self.preset_combo.setEnabled(self.preset_combo.count() > 1)
        self.mirror_box.setEnabled(n >= 4)
        self._update_hint()

    def _on_music_changed(self, *_, initial: bool = False):
        dev = self._device(self.music_combo.currentData())
        self.music_pair.clear()
        for first, label in input_pairs(dev.max_in if dev else 2):
            self.music_pair.addItem(label, first)
        saved = int(self.settings.value("audio/music_offset", 0)) if initial else 0
        idx = self.music_pair.findData(saved)
        self.music_pair.setCurrentIndex(max(0, idx))
        self.music_pair.setEnabled(self.music_pair.count() > 1)
        self._update_hint()

    def _on_mic_changed(self, *_, initial: bool = False):
        dev = self._device(self.mic_combo.currentData())
        self.mic_chan.clear()
        for i in range(dev.max_in if dev else 1):
            self.mic_chan.addItem(f"Wejście {i + 1}", i)
        saved = int(self.settings.value("audio/mic_channel", 0)) if initial else 0
        idx = self.mic_chan.findData(saved)
        self.mic_chan.setCurrentIndex(max(0, idx))
        self.mic_chan.setEnabled(dev is not None and self.mic_chan.count() > 1)

    def _apply_preset(self, *_):
        key = self.preset_combo.currentData()
        if key is None:
            return
        p = preset(key)
        self.mode_combo.setCurrentIndex([m for m, _ in MODES].index(p.mode))
        if p.mode == "multi":
            self._pending_ways = p.ways_index
            self.channel_map.set_ways_override(p.ways_index)
            self.channel_map.set_channel_map(p.channel_map)
        self.mirror_box.setChecked(p.sim_mirror)
        self._update_hint(p.note)

    def _update_hint(self, note: str = "") -> None:
        tips = hints(self.devices, self.music_combo.currentData(), self.out_combo.currentData(),
                     int(self.music_pair.currentData() or 0), note)
        self.hint.setText("\n".join(tips))
        self.hint.setVisible(bool(tips))

    def _on_mode_changed(self, *_):
        self.channel_map.set_mode(self.mode_combo.currentData())

    def result_config(self) -> EngineConfig:
        return EngineConfig(
            music_in=self.music_combo.currentData(),
            output=self.out_combo.currentData(),
            mic_in=self.mic_combo.currentData(),
            mode=self.mode_combo.currentData(),
            fs=self.fs,
            block=self.block_combo.currentData(),
            channel_map=self.channel_map.channel_map(),
            sim_mirror=self.mirror_box.isEnabled() and self.mirror_box.isChecked(),
            music_offset=int(self.music_pair.currentData() or 0),
            mic_channel=int(self.mic_chan.currentData() or 0),
        )

    def persist(self) -> None:
        s = self.settings
        s.setValue("audio/music", self.music_combo.currentText())
        s.setValue("audio/output", self.out_combo.currentText().rsplit(" (", 1)[0])
        s.setValue("audio/mic", self.mic_combo.currentText() if self.mic_combo.currentData() is not None else "")
        s.setValue("audio/mode", self.mode_combo.currentData())
        s.setValue("audio/block", self.block_combo.currentData())
        import json

        s.setValue("audio/channel_map", json.dumps(self.channel_map.channel_map()))
        s.setValue("ui/minimize_to_tray", "true" if self.tray_box.isChecked() else "false")
        if self._pending_ways is not None:
            self.bridge.store.set("xo.ways", self._pending_ways, source="gui")
        s.setValue("audio/sim_mirror", "true" if self.mirror_box.isChecked() else "false")
        s.setValue("audio/music_offset", int(self.music_pair.currentData() or 0))
        s.setValue("audio/mic_channel", int(self.mic_chan.currentData() or 0))
