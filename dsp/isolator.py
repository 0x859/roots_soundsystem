"""5-drożny izolator z płynnym wzmocnieniem od KILL do +6 dB i przyciskami kill."""

from __future__ import annotations

import numpy as np

from engine.params import ParamSpec

from .bandsplit import BandSplitter
from .common import Ramp, Switch, crossfade, gain_from_db

BANDS = ("sub", "bass", "lowmid", "highmid", "top")
BAND_LABELS = {"sub": "Sub", "bass": "Bass", "lowmid": "Low-mid", "highmid": "High-mid", "top": "Top"}
KILL_DB = -40.0
SLOPES = ("24 dB/okt (LR4)", "48 dB/okt (LR8)")
SLOPE_ORDER = (4, 8)
SPLITS = (
    ("iso.f1", "Podział sub/bass", 60.0, 30.0, 150.0),
    ("iso.f2", "Podział bass/low-mid", 250.0, 150.0, 600.0),
    ("iso.f3", "Podział low-mid/high-mid", 1200.0, 600.0, 3000.0),
    ("iso.f4", "Podział high-mid/top", 5000.0, 3000.0, 12000.0),
)
KILL_RAMP_MS = 5.0
# Suma: kill tnie wszystko (z ogonami echa, MC i syreną); Muzyka: tylko muzykę przed sendami – ogony wybrzmiewają
POSITIONS = ("Suma (po efektach)", "Muzyka (przed efektami)")

PARAMS = [
    ParamSpec("iso.enabled", "Izolator", True, kind="bool"),
    ParamSpec("iso.slope", "Nachylenie", 1, kind="choice", choices=SLOPES),
    ParamSpec("iso.position", "Miejsce w torze", 0, kind="choice", choices=POSITIONS),
] + [ParamSpec(k, lbl, d, lo, hi, "Hz", scale="log") for k, lbl, d, lo, hi in SPLITS]
for _b in BANDS:
    PARAMS.append(ParamSpec(f"iso.g.{_b}", BAND_LABELS[_b], 0.0, KILL_DB, 6.0, "dB", step=0.5, kill_floor=KILL_DB))
    PARAMS.append(ParamSpec(f"iso.kill.{_b}", f"Kill {BAND_LABELS[_b]}", False, kind="bool", scene=False))


class Isolator:
    def __init__(self, fs: float, channels: int = 2):
        self.fs = fs
        self.channels = channels
        self.enabled = True
        self.order = 8
        self.splitter = BandSplitter(fs, [s[2] for s in SPLITS], self.order, channels)
        self.gains = [Ramp(1.0, KILL_RAMP_MS, fs) for _ in BANDS]
        self.switch = Switch(fs, on_reset=self.reset)
        # miejsce w torze: `pre` ustawia wątek sterujący, `active_pre` zmienia wątek audio, gdy moduł
        # jest wyciszony (przenikanie do obejścia, przeniesienie, czysty stan i przenikanie z powrotem)
        self.pre = False
        self.active_pre = False
        self._running = False

    def reset(self) -> None:
        self.splitter.reset()
        for ramp in self.gains:
            ramp.snap()

    def configure(self, p) -> None:
        self.enabled = bool(p["iso.enabled"])
        order = SLOPE_ORDER[int(p["iso.slope"])]
        freqs = sorted(float(p[s[0]]) for s in SPLITS)
        if order != self.order:
            self.order = order
            self.splitter = BandSplitter(self.fs, freqs, order, self.channels)
        elif freqs != self.splitter.freqs:
            self.splitter.set_freqs(freqs)
        for ramp, b in zip(self.gains, BANDS, strict=True):
            g = 0.0 if p[f"iso.kill.{b}"] else gain_from_db(float(p[f"iso.g.{b}"]), KILL_DB)
            ramp.set(g)
        self.pre = int(p["iso.position"]) == 1
        if not self._running:
            self.active_pre = self.pre
        self.switch.set(self.enabled and self.pre == self.active_pre)

    def process(self, x: np.ndarray) -> np.ndarray:
        """Tor woła `process` tylko w miejscu `active_pre` odczytanym na początku bloku."""
        self._running = True
        n = len(x)
        sw = self.switch.block(n)
        if sw is None:
            # wyciszony: tu (wątek audio) przenosimy moduł; włączenie po przeniesieniu też tutaj, więc
            # wyłączenie z wątku sterującego, które minęło się z przeniesieniem, samo się naprawia
            self.active_pre = self.pre
            if self.enabled:
                self.switch.set(True)
            return x
        return crossfade(x, self._process(x, n), sw)

    def _process(self, x: np.ndarray, n: int) -> np.ndarray:
        bands = self.splitter.process(x)
        y = np.zeros_like(x)
        for band, ramp in zip(bands, self.gains, strict=False):  # wątek audio
            g = ramp.block(n)
            if isinstance(g, float) and g == 0.0:
                continue
            y += band * g
        return y

    def response(self, freqs: np.ndarray) -> np.ndarray:
        if not self.enabled:
            return np.ones(len(freqs), dtype=complex)
        h = np.zeros(len(freqs), dtype=complex)
        for r, ramp in zip(self.splitter.responses(freqs), self.gains, strict=True):
            h += r * ramp.target
        return h
