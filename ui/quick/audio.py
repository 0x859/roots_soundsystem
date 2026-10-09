"""Robocza konfiguracja audio dla QML: urządzenia, kanały, gotowe układy, mapowanie dróg.

Zmiany trafiają do silnika dopiero po „Zastosuj” (sygnał `applyRequested`), jak w oknie „Ustawienia audio”.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Property, QObject, Signal, Slot

from dsp.crossover import ALL_WAYS, WAY_LABELS, WAYS_BY_COUNT
from dsp.graph import default_channel_map, validate_channel_map
from engine.audio_engine import EngineConfig
from engine.devices import input_pairs, preset, presets_for
from engine.params import ParamStore

from .. import audio_config as ac
from ..audio_config import BLOCKS, MODES, device_by_index, mic_items, music_items, output_items
from .plots import WAY_COLORS

FIELDS = ("music_in", "output", "mic_in", "mode", "block", "channel_map", "sim_mirror", "music_offset", "mic_channel")


def _opt(items) -> list[dict]:
    return [{"label": text, "value": -1 if value is None else value} for text, value in items]


class QmlAudio(QObject):
    changed = Signal()
    applyRequested = Signal()

    def __init__(self, store: ParamStore, list_devices: Callable[[], list], parent: QObject | None = None):
        super().__init__(parent)
        self.store = store
        self._list_devices = list_devices
        self.devices: list = []
        self._d: dict[str, Any] = {
            "music_in": None, "output": None, "mic_in": None, "mode": "sim", "block": 512,
            "channel_map": default_channel_map(), "sim_mirror": False, "music_offset": 0, "mic_channel": 0,
        }
        self._base: dict[str, Any] = copy.deepcopy(self._d)
        self._ways_override: int | None = None
        self._note = ""
        store.subscribe(self._on_store, prefix="xo.ways")

    def _on_store(self, _changed, _source) -> None:
        self.changed.emit()

    # --- wczytanie stanu okna głównego ---
    def load(self, devices: list, cfg: EngineConfig) -> None:
        self.devices = list(devices)
        for f in FIELDS:
            self._d[f] = copy.deepcopy(getattr(cfg, f))
        self._d["channel_map"] = {w: tuple(cfg.channel_map.get(w, (-1, -1))) for w in ALL_WAYS}
        self._base = copy.deepcopy(self._d)
        self._ways_override = None
        self._note = ""
        self.changed.emit()

    def config(self, fs: int) -> EngineConfig:
        return EngineConfig(fs=fs, **{f: copy.deepcopy(self._d[f]) for f in FIELDS})

    @property
    def pending_ways(self) -> int | None:
        return self._ways_override

    def _dev(self, index):
        return device_by_index(self.devices, index)

    def _n_out(self) -> int:
        dev = self._dev(self._d["output"])
        return dev.max_out if dev else 0

    def _ways_index(self) -> int:
        return self._ways_override if self._ways_override is not None else int(self.store["xo.ways"])

    # --- listy ---
    @Property("QVariantList", notify=changed)
    def musicDevices(self) -> list[dict]:
        return _opt(music_items(self.devices))

    @Property("QVariantList", notify=changed)
    def outputDevices(self) -> list[dict]:
        return _opt(output_items(self.devices))

    @Property("QVariantList", notify=changed)
    def micDevices(self) -> list[dict]:
        return _opt(mic_items(self.devices))

    @Property("QVariantList", notify=changed)
    def musicPairs(self) -> list[dict]:
        dev = self._dev(self._d["music_in"])
        return [{"label": label, "value": first} for first, label in input_pairs(dev.max_in if dev else 2)]

    @Property("QVariantList", notify=changed)
    def micChannels(self) -> list[dict]:
        dev = self._dev(self._d["mic_in"])
        return [{"label": f"Wejście {i + 1}", "value": i} for i in range(dev.max_in if dev else 1)]

    @Property("QVariantList", notify=changed)
    def outChannels(self) -> list[dict]:
        return [{"label": "—", "value": -1}] + [{"label": f"kan. {k + 1}", "value": k} for k in range(self._n_out())]

    @Property("QVariantList", notify=changed)
    def presets(self) -> list[dict]:
        return [{"label": "— własny —", "value": ""}] + [{"label": p.label, "value": p.key} for p in presets_for(self._n_out())]

    @Property("QVariantList", constant=True)
    def modes(self) -> list[dict]:
        return [{"label": "SYMULACJA" if k == "sim" else "MULTI", "value": k, "title": t} for k, t in MODES]

    @Property("QVariantList", constant=True)
    def blocks(self) -> list[dict]:
        return [{"label": str(b), "value": b} for b in BLOCKS]

    # --- wartości ---
    music = Property(int, lambda s: -1 if s._d["music_in"] is None else s._d["music_in"], notify=changed)
    output = Property(int, lambda s: -1 if s._d["output"] is None else s._d["output"], notify=changed)
    mic = Property(int, lambda s: -1 if s._d["mic_in"] is None else s._d["mic_in"], notify=changed)
    musicOffset = Property(int, lambda s: int(s._d["music_offset"]), notify=changed)
    micChannel = Property(int, lambda s: int(s._d["mic_channel"]), notify=changed)
    mode = Property(str, lambda s: s._d["mode"], notify=changed)
    block = Property(int, lambda s: int(s._d["block"]), notify=changed)
    simMirror = Property(bool, lambda s: bool(s._d["sim_mirror"]), notify=changed)
    mirrorAvailable = Property(bool, lambda s: s._n_out() >= 4, notify=changed)
    channelCount = Property(int, lambda s: s._n_out(), notify=changed)

    @Property("QVariantList", notify=changed)
    def ways(self) -> list[dict]:
        """Aktywne drogi z kanałami L/R (do edytora mapowania)."""
        out = []
        for w in WAYS_BY_COUNT[(2, 3, 4)[self._ways_index()]]:
            left, right = self._d["channel_map"].get(w, (-1, -1))
            out.append({"way": w, "label": WAY_LABELS[w].upper(), "color": WAY_COLORS[w], "left": left, "right": right})
        return out

    @Property("QVariantList", notify=changed)
    def problems(self) -> list[str]:
        if self._d["mode"] != "multi":
            return []
        ways = WAYS_BY_COUNT[(2, 3, 4)[self._ways_index()]]
        return validate_channel_map(self._d["channel_map"], ways, self._n_out())

    @Property("QVariantList", notify=changed)
    def tips(self) -> list[str]:
        return ac.hints(self.devices, self._d["music_in"], self._d["output"], int(self._d["music_offset"]), self._note)

    @Property(bool, notify=changed)
    def dirty(self) -> bool:
        return self._d != self._base or self._ways_override is not None

    # --- zmiany ---
    def _set(self, key: str, value: Any) -> None:
        if self._d[key] != value:
            self._d[key] = value
            self.changed.emit()

    @Slot(int)
    def setMusic(self, index: int) -> None:
        self._d["music_offset"] = 0
        self._set("music_in", None if index < 0 else index)
        self.changed.emit()

    @Slot(int)
    def setOutput(self, index: int) -> None:
        self._set("output", None if index < 0 else index)
        if self._n_out() < 4:
            self._d["sim_mirror"] = False
        self._note = ""
        self.changed.emit()

    @Slot(int)
    def setMic(self, index: int) -> None:
        self._d["mic_channel"] = 0
        self._set("mic_in", None if index < 0 else index)
        self.changed.emit()

    @Slot(int)
    def setMusicOffset(self, first: int) -> None:
        self._set("music_offset", int(first))

    @Slot(int)
    def setMicChannel(self, ch: int) -> None:
        self._set("mic_channel", int(ch))

    @Slot(str)
    def setMode(self, mode: str) -> None:
        if mode in dict(MODES):
            self._set("mode", mode)

    @Slot(int)
    def setBlock(self, block: int) -> None:
        if block in BLOCKS:
            self._set("block", int(block))

    @Slot(bool)
    def setMirror(self, on: bool) -> None:
        self._set("sim_mirror", bool(on) and self._n_out() >= 4)

    @Slot(str, str, int)
    def setChannel(self, way: str, side: str, ch: int) -> None:
        if way not in ALL_WAYS or side not in ("left", "right"):
            return
        left, right = self._d["channel_map"].get(way, (-1, -1))
        new = dict(self._d["channel_map"])
        new[way] = (ch, right) if side == "left" else (left, ch)
        self._set("channel_map", new)

    @Slot(str)
    def applyPreset(self, key: str) -> None:
        if not key:
            return
        p = preset(key)
        self._d["mode"] = p.mode
        if p.mode == "multi":
            self._ways_override = p.ways_index
            self._d["channel_map"] = {w: tuple(p.channel_map.get(w, (-1, -1))) for w in ALL_WAYS}
        self._d["sim_mirror"] = p.sim_mirror
        self._note = p.note
        self.changed.emit()

    @Slot()
    def refresh(self) -> None:
        self.devices = self._list_devices()
        for key in ("music_in", "output", "mic_in"):
            if self._dev(self._d[key]) is None:
                self._d[key] = None
        self.changed.emit()

    @Slot()
    def revert(self) -> None:
        self._d = copy.deepcopy(self._base)
        self._ways_override = None
        self._note = ""
        self.changed.emit()

    @Slot()
    def apply(self) -> None:
        self.applyRequested.emit()
