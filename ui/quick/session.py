"""Stan sesji dla QML: start/stop, scena, status silnika, mierniki, tryb ekranu i akcje."""

from __future__ import annotations

import math
import time
from typing import Any

from PySide6.QtCore import Property, QObject, Signal, Slot

from dsp.crossover import ALL_WAYS

FLOOR_DB = -60.0
CLIP_DB = -0.3
CLIP_HOLD_S = 1.5
METER_RELEASE = 0.82  # spadek wskazania na odświeżenie (~30 Hz)
METER_LABELS = ("IN", "SUB", "BASS", "MID", "TOP", "OUT")


def db_norm(db: float) -> float:
    return max(0.0, min(1.0, (db - FLOOR_DB) / -FLOOR_DB))


def lin_db(x: float) -> float:
    return 20.0 * math.log10(x) if x > 1e-6 else -120.0


def _mid_text(mid: str) -> str:
    kind, _, rest = mid.partition(":")
    chan, _, num = rest.partition(":")
    ch = f" · kan. {int(chan) + 1}" if chan.isdigit() and chan != "0" else ""
    if kind == "cc":
        return f"CC {num}{ch}"
    if kind == "note":
        return f"Nuta {num}{ch}"
    if kind == "pw":
        return "Pitch bend"
    return mid


def midi_label(mapping: dict[str, str], shift_mapping: dict[str, str], target: str) -> str:
    """Opis elementu kontrolera przypisanego do celu, np. „CC 19” albo „SHIFT + CC 16”."""
    found = [_mid_text(m) for m, t in mapping.items() if t == target]
    found += ["SHIFT + " + _mid_text(m) for m, t in shift_mapping.items() if t == target]
    return ", ".join(found)


class QmlSession(QObject):
    """Wszystko, co QML potrzebuje poza parametrami: stan silnika i polecenia do okna głównego.

    Polecenia trafiają do okna głównego sygnałem `requested(akcja, argument)`.
    """

    requested = Signal(str, "QVariant")
    runningChanged = Signal()
    sceneChanged = Signal()
    statusChanged = Signal()
    metersChanged = Signal()
    screenChanged = Signal()
    editingChanged = Signal()
    devicesChanged = Signal()
    pickupChanged = Signal()
    eqPresetsChanged = Signal()
    dspChanged = Signal()
    toast = Signal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._running = False
        self._scene = "—"
        self._scenes: list[str] = []
        self._chips: list[str] = []
        self._cpu = ""
        self._levels = [0.0] * len(METER_LABELS)
        self._active = [True] * len(METER_LABELS)
        self._clip_until = [0.0] * len(METER_LABELS)
        self._mic = 0.0
        self._mic_gr = 0.0
        self._screen = "live"
        self._editing = False
        self._devices: dict[str, Any] = {}
        self._pickup: dict[str, float] = {}
        self._eq_presets: list[dict] = []
        self._dsp = (0, 0)
        self.midi_lookup = lambda _key: ""
        self.memory_lookup = lambda _i: False

    # --- właściwości ---
    @Property(bool, notify=runningChanged)
    def running(self) -> bool:
        return self._running

    @Property(str, notify=sceneChanged)
    def scene(self) -> str:
        return self._scene

    @Property("QVariantList", notify=sceneChanged)
    def scenes(self) -> list[str]:
        return self._scenes

    @Property("QVariantList", notify=statusChanged)
    def chips(self) -> list[str]:
        return self._chips

    @Property(str, notify=statusChanged)
    def cpu(self) -> str:
        return self._cpu

    @Property("QVariantList", notify=metersChanged)
    def levels(self) -> list[float]:
        return self._levels

    @Property("QVariantList", notify=metersChanged)
    def meterActive(self) -> list[bool]:
        return self._active

    @Property("QVariantList", notify=metersChanged)
    def clips(self) -> list[bool]:
        now = time.monotonic()
        return [now < t for t in self._clip_until]

    @Property("QVariantList", constant=True)
    def meterLabels(self) -> list[str]:
        return list(METER_LABELS)

    @Property(float, notify=metersChanged)
    def micLevel(self) -> float:
        return self._mic

    @Property(float, notify=metersChanged)
    def micGr(self) -> float:
        return self._mic_gr

    def _get_screen(self) -> str:
        return self._screen

    def _set_screen(self, value: str) -> None:
        if value in ("live", "config") and value != self._screen:
            self._screen = value
            self.screenChanged.emit()

    screen = Property(str, _get_screen, _set_screen, notify=screenChanged)

    def _get_editing(self) -> bool:
        return self._editing

    def _set_editing(self, value: bool) -> None:
        if bool(value) != self._editing:
            self._editing = bool(value)
            self.editingChanged.emit()

    editing = Property(bool, _get_editing, _set_editing, notify=editingChanged)

    @Property("QVariantMap", notify=devicesChanged)
    def devices(self) -> dict[str, Any]:
        return self._devices

    @Property("QVariantMap", notify=pickupChanged)
    def pickup(self) -> dict[str, float]:
        """Parametry czekające na przejęcie przez kontroler MIDI: klucz -> pozycja elementu (0..1)."""
        return self._pickup

    @Property("QVariantList", notify=eqPresetsChanged)
    def eqPresets(self) -> list[dict]:
        """Presety EQ: [{label, value, builtin}] (własne oznaczone gwiazdką)."""
        return self._eq_presets

    @Property(int, notify=dspChanged)
    def dspOn(self) -> int:
        return self._dsp[0]

    @Property(int, notify=dspChanged)
    def dspTotal(self) -> int:
        return self._dsp[1]

    # --- aktualizacje z okna głównego ---
    def set_eq_presets(self, presets: list[tuple[str, bool]]) -> None:
        items = [{"label": n if b else f"{n} *", "value": n, "builtin": b} for n, b in presets]
        if items != self._eq_presets:
            self._eq_presets = items
            self.eqPresetsChanged.emit()

    def set_dsp(self, on: int, total: int) -> None:
        if (on, total) != self._dsp:
            self._dsp = (on, total)
            self.dspChanged.emit()

    def set_devices(self, info: dict[str, Any]) -> None:
        if info != self._devices:
            self._devices = dict(info)
            self.devicesChanged.emit()

    def set_pickup(self, pending: dict[str, float]) -> None:
        rounded = {k: round(float(v), 3) for k, v in pending.items()}
        if rounded != self._pickup:
            self._pickup = rounded
            self.pickupChanged.emit()

    def set_running(self, running: bool) -> None:
        if running != self._running:
            self._running = running
            self.runningChanged.emit()

    def set_scenes(self, names: list[str], current: str) -> None:
        if names != self._scenes or current != self._scene:
            self._scenes = list(names)
            self._scene = current or "—"
            self.sceneChanged.emit()

    def set_status(self, chips: list[str], cpu: str) -> None:
        if chips != self._chips or cpu != self._cpu:
            self._chips = list(chips)
            self._cpu = cpu
            self.statusChanged.emit()

    def set_meters(self, chain: Any, mic_db: float = -120.0, mic_gr: float = 0.0) -> None:
        """Szczyty z toru (lub cisza, gdy `chain` jest None) z łagodnym opadaniem wskazań."""
        if chain is None:
            peaks = [0.0] * len(METER_LABELS)
            active = [True] * len(METER_LABELS)
        else:
            ways = chain.xo.ways
            peaks = [chain.tap_in.peak]
            peaks += [chain.taps[w].peak if w in ways else 0.0 for w in ALL_WAYS]
            peaks.append(chain.tap_out.peak)
            active = [True] + [w in ways for w in ALL_WAYS] + [True]
        now = time.monotonic()
        for i, pk in enumerate(peaks):
            db = lin_db(pk)
            if db >= CLIP_DB:
                self._clip_until[i] = now + CLIP_HOLD_S
            self._levels[i] = max(db_norm(db), self._levels[i] * METER_RELEASE)
        self._active = active
        self._mic = max(db_norm(mic_db), self._mic * METER_RELEASE)
        self._mic_gr = mic_gr
        self.metersChanged.emit()

    # --- polecenia z QML ---
    @Slot(str)
    def request(self, action: str) -> None:
        self.requested.emit(action, None)

    @Slot(str, "QVariant")
    def requestWith(self, action: str, arg: Any) -> None:
        self.requested.emit(action, arg)

    @Slot(str, result=str)
    def midiFor(self, key: str) -> str:
        return self.midi_lookup(key)

    @Slot(int, result=bool)
    def hasMemory(self, i: int) -> bool:
        return bool(self.memory_lookup(i))
