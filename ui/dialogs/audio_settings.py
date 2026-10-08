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
    QPushButton,
    QVBoxLayout,
)

from engine.audio_engine import EngineConfig, find_cable_output, list_devices, wasapi_default_output
from ..widgets.channel_map import ChannelMapEditor

MODES = (("sim", "Symulacja (stereo)"), ("multi", "Multi (wielokanałowe)"))
BLOCKS = (256, 512, 1024)


def _select(cb: QComboBox, label, fallback=None) -> None:
    for i in range(cb.count()):
        if label and cb.itemText(i).startswith(str(label)):
            cb.setCurrentIndex(i)
            return
    if fallback is not None:
        idx = cb.findData(fallback)
        if idx >= 0:
            cb.setCurrentIndex(idx)


def resolve_saved_devices(devices, settings) -> tuple[int | None, int | None, int | None]:
    """Zwraca (music_in, output, mic_in) na podstawie zapisanych etykiet."""
    music_cb, out_cb, mic_cb = QComboBox(), QComboBox(), QComboBox()
    _fill_combos(devices, music_cb, out_cb, mic_cb, settings)
    return music_cb.currentData(), out_cb.currentData(), mic_cb.currentData()


def _fill_combos(devices, music_cb, out_cb, mic_cb, settings) -> None:
    saved = {
        "music": settings.value("audio/music"),
        "out": settings.value("audio/output"),
        "mic": settings.value("audio/mic"),
    }
    for cb in (music_cb, out_cb, mic_cb):
        cb.blockSignals(True)
        cb.clear()
    mic_cb.addItem("— brak mikrofonu —", None)
    for d in devices:
        if d.max_in > 0:
            music_cb.addItem(d.label, d.index)
            mic_cb.addItem(d.label, d.index)
        if d.max_out > 0:
            out_cb.addItem(f"{d.label} ({d.max_out} kan.)", d.index)
    _select(music_cb, saved["music"], find_cable_output(devices))
    default_out = wasapi_default_output()
    dev = next((d for d in devices if d.index == default_out), None)
    if dev is None or "CABLE" in dev.name.upper():
        default_out = next((d.index for d in devices if d.max_out > 0 and "CABLE" not in d.name.upper()), None)
    _select(out_cb, saved["out"], default_out)
    _select(mic_cb, saved["mic"])
    for cb in (music_cb, out_cb, mic_cb):
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
        form.addRow("Muzyka:", self.music_combo)
        form.addRow("Wyjście:", self.out_combo)
        form.addRow("Mikrofon:", self.mic_combo)
        form.addRow("Tryb:", self.mode_combo)
        form.addRow("Blok:", self.block_combo)
        form.addRow("", refresh)
        form.addRow("", self.tray_box)
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
        self.refresh_devices()

    def refresh_devices(self) -> None:
        self.devices = list_devices()
        _fill_combos(self.devices, self.music_combo, self.out_combo, self.mic_combo, self.settings)
        self._on_output_changed()

    def _device(self, index):
        return next((d for d in self.devices if d.index == index), None)

    def _on_output_changed(self, *_):
        dev = self._device(self.out_combo.currentData())
        self.channel_map.set_device_channels(dev.max_out if dev else 0)

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
