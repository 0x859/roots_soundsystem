"""Filtr sweep HP/LP z rezonansem.

Z numba: SVF w topologii TPT z interpolacją częstotliwości w każdej próbce
(płynne „przemiatanie” bez trzasków). Bez numba: biquad RBJ aktualizowany co blok.
"""

from __future__ import annotations

import numpy as np

from .biquad import SOSFilter, highpass, lowpass, response
from .common import one_pole_coef
from .jit import HAVE_NUMBA, njit


@njit(cache=True, fastmath=True)
def _svf_block(x, g_arr, k, ic1, ic2, highpass_mode):
    n_samples, n_ch = x.shape
    y = np.empty_like(x)
    for n in range(n_samples):
        g = g_arr[n]
        a1 = 1.0 / (1.0 + g * (g + k))
        a2 = g * a1
        a3 = g * a2
        for c in range(n_ch):
            v3 = x[n, c] - ic2[c]
            v1 = a1 * ic1[c] + a2 * v3
            v2 = ic2[c] + a2 * ic1[c] + a3 * v3
            ic1[c] = 2.0 * v1 - ic1[c]
            ic2[c] = 2.0 * v2 - ic2[c]
            if highpass_mode:
                y[n, c] = x[n, c] - k * v1 - v2
            else:
                y[n, c] = v2
    return y


def res_to_q(res: float) -> float:
    return 0.707 + max(0.0, min(1.0, res)) ** 1.5 * 9.0


class SweepFilter:
    def __init__(self, mode: str, fs: float, channels: int = 2, bypass_hz: float | None = None, smooth_ms: float = 25.0):
        self.mode = mode
        self.fs = fs
        self.channels = channels
        self.fmax = 0.45 * fs
        self.bypass_hz = bypass_hz if bypass_hz is not None else (20.5 if mode == "hp" else 19900.0)
        self.target = 20.0 if mode == "hp" else 20000.0
        self.cur = self.target
        self.q = 0.707
        self.smooth_s = smooth_ms / 1000.0
        self.use_jit = HAVE_NUMBA
        self._ic1 = np.zeros(channels)
        self._ic2 = np.zeros(channels)
        self._sos = SOSFilter(self._design(self.cur), channels)

    def warmup(self) -> None:
        if self.use_jit:
            _svf_block(np.zeros((4, self.channels)), np.full(4, 0.1), 1.0, np.zeros(self.channels), np.zeros(self.channels), True)

    def reset(self) -> None:
        """Czysty stan filtra; częstotliwość od razu docelowa (bez przemiatania od starej wartości)."""
        self._ic1[:] = 0.0
        self._ic2[:] = 0.0
        self._sos.reset()
        self.cur = self.target

    def set(self, freq: float, res: float) -> None:
        self.target = float(min(max(freq, 10.0), self.fmax))
        self.q = res_to_q(res)

    def _design(self, f: float) -> np.ndarray:
        f = min(f, self.fmax)
        return highpass(f, self.q, self.fs) if self.mode == "hp" else lowpass(f, self.q, self.fs)

    def _bypassed(self, f: float) -> bool:
        return f <= self.bypass_hz if self.mode == "hp" else f >= self.bypass_hz

    def process(self, x: np.ndarray) -> np.ndarray:
        n = len(x)
        start = self.cur
        c = one_pole_coef(self.smooth_s, n, self.fs)
        end = float(np.exp(np.log(start) + (np.log(self.target) - np.log(start)) * c))
        if abs(end - self.target) / self.target < 1e-3:
            end = self.target
        self.cur = end
        if self._bypassed(start) and self._bypassed(end):
            self._ic1[:] = 0.0
            self._ic2[:] = 0.0
            self._sos.reset()
            return x
        if self.use_jit:
            fc = start * (end / start) ** (np.arange(1, n + 1) / n)
            g = np.tan(np.pi * np.minimum(fc, self.fmax) / self.fs)
            return _svf_block(np.ascontiguousarray(x), g, 1.0 / self.q, self._ic1, self._ic2, self.mode == "hp")
        self._sos.set_sos(self._design(end))
        return self._sos.process(x)

    def response(self, freqs: np.ndarray) -> np.ndarray:
        if self._bypassed(self.target):
            return np.ones(len(freqs), dtype=complex)
        return response(self._design(self.target), freqs, self.fs)
