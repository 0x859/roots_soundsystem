"""Przedwzmacniacz soundsystemowy: gain, nasycenie lampowe, półki bass/treble, sweep HP/LP."""

from __future__ import annotations

import numpy as np
from scipy import signal

from engine.params import ParamSpec

from .biquad import SOSFilter, high_shelf, highpass1, low_shelf, response
from .common import Ramp, Switch, crossfade, db2lin
from .svf import SweepFilter

BASS_HZ = 100.0
TREBLE_HZ = 5000.0

PARAMS = [
    ParamSpec("preamp.enabled", "Preamp", True, kind="bool"),
    ParamSpec("preamp.gain", "Gain", 0.0, -24.0, 24.0, "dB", step=0.5),
    ParamSpec("preamp.drive", "Drive", 0.2, 0.0, 1.0, "%"),
    ParamSpec("preamp.bias", "Asymetria", 0.3, 0.0, 1.0, "%"),
    ParamSpec("preamp.bass", "Bass", 0.0, -15.0, 15.0, "dB", step=0.5),
    ParamSpec("preamp.treble", "Treble", 0.0, -15.0, 15.0, "dB", step=0.5),
    ParamSpec("preamp.hp", "Sweep HP", 20.0, 20.0, 1000.0, "Hz", scale="log"),
    ParamSpec("preamp.lp", "Sweep LP", 20000.0, 300.0, 20000.0, "Hz", scale="log"),
    ParamSpec("preamp.res", "Rezonans", 0.2, 0.0, 1.0, "%"),
    ParamSpec("preamp.mono", "Mono", False, kind="bool"),
    ParamSpec("preamp.echo_send", "Send echo", 0.0, 0.0, 1.0, "%"),
    ParamSpec("preamp.spring_send", "Send spring", 0.0, 0.0, 1.0, "%"),
    ParamSpec("preamp.master", "Master preamp", 0.0, -24.0, 12.0, "dB", step=0.5),
]


class Oversampler2x:
    """Nadpróbkowanie 2x filtrem półpasmowym FIR ze stanem między blokami."""

    def __init__(self, channels: int, taps: int = 47):
        self.h = signal.firwin(taps, 0.5)
        self._zi_up = np.zeros((taps - 1, channels))
        self._zi_dn = np.zeros((taps - 1, channels))

    def reset(self) -> None:
        self._zi_up[:] = 0.0
        self._zi_dn[:] = 0.0

    def up(self, x: np.ndarray) -> np.ndarray:
        u = np.zeros((2 * len(x), x.shape[1]))
        u[::2] = 2.0 * x
        y, self._zi_up = signal.lfilter(self.h, 1.0, u, axis=0, zi=self._zi_up)
        return y

    def down(self, u: np.ndarray) -> np.ndarray:
        y, self._zi_dn = signal.lfilter(self.h, 1.0, u, axis=0, zi=self._zi_dn)
        return y[::2]


def tube_shape(x: np.ndarray, drive: float, bias: float) -> np.ndarray:
    """Asymetryczne nasycenie: tanh z przesunięciem punktu pracy (parzyste harmoniczne)."""
    k = db2lin(drive * 24.0)
    b = 0.25 * bias
    tb = np.tanh(b)
    y = np.tanh(k * x + b) - tb
    return y / ((1.0 - tb * tb) * np.sqrt(k))


class Preamp:
    def __init__(self, fs: float, channels: int = 2):
        self.fs = fs
        self.channels = channels
        self.enabled = True
        self.drive = 0.2
        self.bias = 0.3
        self.mono = False
        self.gain = Ramp(1.0, 20, fs)
        self.master = Ramp(1.0, 20, fs)
        self.oversampler = Oversampler2x(channels)
        self.tone = SOSFilter(np.vstack([highpass1(10.0, fs)]), channels)
        self.hp = SweepFilter("hp", fs, channels)
        self.lp = SweepFilter("lp", fs, channels)
        self._tone_sos = self.tone.sos
        self.switch = Switch(fs, on_reset=self.reset)

    def reset(self) -> None:
        self.oversampler.reset()
        self.tone.reset()
        self.hp.reset()
        self.lp.reset()
        self.gain.snap()
        self.master.snap()

    def warmup(self) -> None:
        self.hp.warmup()
        self.lp.warmup()

    def configure(self, p) -> None:
        self.enabled = bool(p["preamp.enabled"])
        self.gain.set(db2lin(p["preamp.gain"]))
        self.master.set(db2lin(p["preamp.master"]))
        self.drive = float(p["preamp.drive"])
        self.bias = float(p["preamp.bias"])
        self.mono = bool(p["preamp.mono"])
        sos = np.vstack(
            [
                highpass1(10.0, self.fs),
                low_shelf(BASS_HZ, float(p["preamp.bass"]), self.fs),
                high_shelf(TREBLE_HZ, float(p["preamp.treble"]), self.fs),
            ]
        )
        self._tone_sos = sos
        self.tone.set_sos(sos)
        res = float(p["preamp.res"])
        self.hp.set(float(p["preamp.hp"]), res)
        self.lp.set(float(p["preamp.lp"]), res)
        self.switch.set(self.enabled)

    def process(self, x: np.ndarray) -> np.ndarray:
        n = len(x)
        g = self.switch.block(n)
        if g is None:
            return x
        return crossfade(x, self._process(x, n), g)

    def _process(self, x: np.ndarray, n: int) -> np.ndarray:
        y = x * self.gain.block(n)
        u = self.oversampler.up(y)
        if self.drive > 0.001:
            u = tube_shape(u, self.drive, self.bias)
        y = self.oversampler.down(u)
        y = self.tone.process(y)
        y = self.hp.process(y)
        y = self.lp.process(y)
        if self.mono and y.shape[1] > 1:
            m = y.mean(axis=1, keepdims=True)
            y = np.repeat(m, y.shape[1], axis=1)
        return y * self.master.block(n)

    def response(self, freqs: np.ndarray) -> np.ndarray:
        if not self.enabled:
            return np.ones(len(freqs), dtype=complex)
        h = response(self._tone_sos, freqs, self.fs) * self.hp.response(freqs) * self.lp.response(freqs)
        return h * self.gain.target * self.master.target
