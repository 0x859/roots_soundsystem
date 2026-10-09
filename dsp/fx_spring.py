"""Reverb sprężynowy: łańcuch rozciągniętych allpassów (dyspersja, „boing”) i pętla sprzężenia."""

from __future__ import annotations

import numpy as np

from engine.params import ParamSpec

from .biquad import SOSFilter, highpass, lowpass
from .common import Ramp, Switch

PARAMS = [
    ParamSpec("spring.enabled", "Sprężyna", True, kind="bool"),
    ParamSpec("spring.decay", "Decay", 0.6, 0.0, 1.0, "%"),
    ParamSpec("spring.tone", "Tone", 3500.0, 1000.0, 8000.0, "Hz", scale="log"),
    ParamSpec("spring.return", "Powrót", 0.8, 0.0, 1.5, "%"),
    ParamSpec("spring.crash", "Crash", False, kind="bool", momentary=True, scene=False),
]

LOOP_MS = (37.3, 41.9)
MOD_MS = 0.25
MOD_HZ = (1.1, 1.37)
DISPERSION_SECTIONS = 16
DISPERSION_A = 0.62


def stretched_allpass(a: float) -> np.ndarray:
    """H(z) = (a + z^-2) / (1 + a z^-2) jako jeden biquad."""
    return np.array([a, 0.0, 1.0, 1.0, 0.0, a])


class SpringReverb:
    def __init__(self, fs: float, block: int, channels: int = 2, seed: int = 7):
        self.fs = fs
        self.channels = channels
        self.enabled = True
        disp = [stretched_allpass(DISPERSION_A)] * DISPERSION_SECTIONS
        self.pre = SOSFilter(np.vstack([highpass(150, 0.707, fs), lowpass(5000, 0.707, fs)] + disp), channels)
        self.loop = SOSFilter(np.vstack([lowpass(3500, 0.707, fs)] + [stretched_allpass(0.5)] * 4), channels)
        self.post = SOSFilter(highpass(200, 0.707, fs)[None, :], channels)
        self.delays = np.array([max(ms * fs / 1000.0, block + 3.0) for ms in LOOP_MS[:channels]])
        need = self.delays.max() + MOD_MS * fs / 1000.0 + 4 * block + 16
        size = 1 << int(np.ceil(np.log2(need)))
        self.buf = np.zeros((size, channels))
        self.mask = size - 1
        self.w = 0
        self.phase = np.zeros(channels)
        self.g = 0.69
        self.ret = Ramp(0.8, 20, fs)
        self._crash_prev = False
        self._crash_armed = False
        self._burst = None
        self._burst_pos = 0
        self._rng = np.random.default_rng(seed)
        self.crash = False
        self.switch = Switch(fs, on_silent=self.reset)

    def reset(self) -> None:
        self.buf.fill(0.0)
        for f in (self.pre, self.loop, self.post):
            f.reset()
        self.phase[:] = 0.0
        self._burst = None
        self._crash_armed = False
        self.ret.snap()

    def configure(self, p) -> None:
        self.enabled = bool(p["spring.enabled"])
        self.switch.set(self.enabled)
        self.g = 0.3 + 0.62 * float(p["spring.decay"])
        self.ret.set(float(p["spring.return"]))
        self.loop.set_sos(np.vstack([lowpass(float(p["spring.tone"]), 0.707, self.fs)] + [stretched_allpass(0.5)] * 4))
        crash = bool(p["spring.crash"])
        if crash and not self._crash_prev and self.enabled:  # CRASH przy wyłączonej sprężynie nie czeka
            self._crash_armed = True
        self._crash_prev = crash

    def _make_burst(self) -> np.ndarray:
        n = int(0.09 * self.fs)
        t = np.arange(n) / self.fs
        env = np.exp(-t / 0.018)
        noise = self._rng.standard_normal((n, self.channels)) * 0.6
        thump = np.sin(2 * np.pi * 90 * t)[:, None] * 0.8
        return (noise + thump) * env[:, None]

    def process(self, x: np.ndarray) -> np.ndarray | None:
        n = len(x)
        g = self.switch.block(n)
        if g is None:
            return None
        y = self._process(x, n)
        return y if isinstance(g, float) else y * g

    def _process(self, x: np.ndarray, n: int) -> np.ndarray:
        if self._crash_armed:
            self._crash_armed = False
            self._burst = self._make_burst()
            self._burst_pos = 0
        if self._burst is not None:
            chunk = self._burst[self._burst_pos:self._burst_pos + n]
            x = x.copy()
            x[: len(chunk)] += chunk
            self._burst_pos += n
            if self._burst_pos >= len(self._burst):
                self._burst = None
        xin = self.pre.process(x)
        k = np.arange(1, n + 1)[:, None]
        ph = self.phase + 2 * np.pi * np.array(MOD_HZ[: self.channels]) / self.fs * k
        self.phase = ph[-1] % (2 * np.pi)
        d = self.delays + MOD_MS * self.fs / 1000.0 * 0.5 * (1 + np.sin(ph))
        pos = self.w + np.arange(n)[:, None] - d
        i0 = np.floor(pos).astype(np.int64)
        frac = pos - i0
        cols = np.arange(self.channels)
        a = self.buf[i0 & self.mask, cols]
        b = self.buf[(i0 + 1) & self.mask, cols]
        y = a + (b - a) * frac
        fb = self.loop.process(y)
        idx = (self.w + np.arange(n)) & self.mask
        self.buf[idx] = xin + self.g * fb
        self.w = (self.w + n) & self.mask
        return self.post.process(y) * self.ret.block(n)
