"""12-pasmowy graficzny EQ (filtry peaking RBJ), globalna korekcja toru."""

from __future__ import annotations

import numpy as np

from engine.params import ParamSpec

from .biquad import SOSFilter, identity, peaking, response
from .common import Ramp, Switch, crossfade, db2lin

BANDS = (25, 50, 100, 200, 400, 800, 1600, 3150, 6300, 10000, 12500, 16000)
Q = 1.4


def band_label(f: float) -> str:
    return f"{f / 1000:g}k" if f >= 1000 else f"{f:g}"


PARAMS = [
    ParamSpec("eq.enabled", "EQ12", True, kind="bool"),
    ParamSpec("eq.preamp", "Preamp EQ", 0.0, -12.0, 12.0, "dB", step=0.5),
] + [ParamSpec(f"eq.b{i}", band_label(f), 0.0, -12.0, 12.0, "dB", step=0.5) for i, f in enumerate(BANDS)]


def peaking_sos(f0: float, gain_db: float, q: float, fs: float) -> np.ndarray:
    return peaking(f0, gain_db, q, fs)


class Equalizer:
    def __init__(self, fs: float, channels: int = 2):
        self.fs = fs
        self.enabled = True
        self._gains = [0.0] * len(BANDS)
        self._sos = np.vstack([identity() for _ in BANDS])
        self.filter = SOSFilter(self._sos, channels)
        self.preamp = Ramp(1.0, 20, fs)
        self.switch = Switch(fs, on_silent=self.reset)

    def reset(self) -> None:
        self.filter.reset()
        self.preamp.snap()

    def configure(self, p) -> None:
        self.enabled = bool(p["eq.enabled"])
        self.switch.set(self.enabled)
        self.preamp.set(db2lin(p["eq.preamp"]))
        sos = None
        for i, f in enumerate(BANDS):
            g = float(p[f"eq.b{i}"])
            if g != self._gains[i]:
                if sos is None:
                    sos = self._sos.copy()
                sos[i] = peaking_sos(f, g, Q, self.fs)
                self._gains[i] = g
        if sos is not None:
            self._sos = sos
            self.filter.set_sos(sos)

    @property
    def sos(self) -> np.ndarray:
        return self._sos

    def process(self, x: np.ndarray) -> np.ndarray:
        g = self.switch.block(len(x))
        if g is None:
            return x
        return crossfade(x, self.filter.process(x) * self.preamp.block(len(x)), g)

    def response(self, freqs: np.ndarray) -> np.ndarray:
        if not self.enabled:
            return np.ones(len(freqs), dtype=complex)
        return response(self._sos, freqs, self.fs) * self.preamp.target
