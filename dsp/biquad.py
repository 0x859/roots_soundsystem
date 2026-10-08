"""Współczynniki biquadów wg RBJ Audio EQ Cookbook, filtry Linkwitz-Riley i filtr SOS ze stanem."""

from __future__ import annotations

import numpy as np
from scipy import signal

SQRT1_2 = 0.7071067811865476
BUTTER_Q = {2: (SQRT1_2,), 4: (0.5411961001461969, 1.3065629648763766)}


def identity() -> np.ndarray:
    return np.array([1.0, 0.0, 0.0, 1.0, 0.0, 0.0])


def _clip_f(f: float, fs: float) -> float:
    return float(min(max(f, 1.0), 0.49 * fs))


def _norm(b, a) -> np.ndarray:
    a0 = a[0]
    return np.array([b[0] / a0, b[1] / a0, b[2] / a0, 1.0, a[1] / a0, a[2] / a0])


def _w(f: float, q: float, fs: float):
    w0 = 2.0 * np.pi * _clip_f(f, fs) / fs
    return np.cos(w0), np.sin(w0) / (2.0 * q)


def peaking(f0: float, gain_db: float, q: float, fs: float) -> np.ndarray:
    if gain_db == 0.0 or f0 >= 0.49 * fs:
        return identity()
    A = 10.0 ** (gain_db / 40.0)
    c, alpha = _w(f0, q, fs)
    return _norm([1 + alpha * A, -2 * c, 1 - alpha * A], [1 + alpha / A, -2 * c, 1 - alpha / A])


def low_shelf(f0: float, gain_db: float, fs: float, q: float = SQRT1_2) -> np.ndarray:
    if gain_db == 0.0:
        return identity()
    A = 10.0 ** (gain_db / 40.0)
    c, alpha = _w(f0, q, fs)
    s = 2 * np.sqrt(A) * alpha
    b = [A * ((A + 1) - (A - 1) * c + s), 2 * A * ((A - 1) - (A + 1) * c), A * ((A + 1) - (A - 1) * c - s)]
    a = [(A + 1) + (A - 1) * c + s, -2 * ((A - 1) + (A + 1) * c), (A + 1) + (A - 1) * c - s]
    return _norm(b, a)


def high_shelf(f0: float, gain_db: float, fs: float, q: float = SQRT1_2) -> np.ndarray:
    if gain_db == 0.0:
        return identity()
    A = 10.0 ** (gain_db / 40.0)
    c, alpha = _w(f0, q, fs)
    s = 2 * np.sqrt(A) * alpha
    b = [A * ((A + 1) + (A - 1) * c + s), -2 * A * ((A - 1) + (A + 1) * c), A * ((A + 1) + (A - 1) * c - s)]
    a = [(A + 1) - (A - 1) * c + s, 2 * ((A - 1) - (A + 1) * c), (A + 1) - (A - 1) * c - s]
    return _norm(b, a)


def lowpass(f0: float, q: float, fs: float) -> np.ndarray:
    c, alpha = _w(f0, q, fs)
    return _norm([(1 - c) / 2, 1 - c, (1 - c) / 2], [1 + alpha, -2 * c, 1 - alpha])


def highpass(f0: float, q: float, fs: float) -> np.ndarray:
    c, alpha = _w(f0, q, fs)
    return _norm([(1 + c) / 2, -(1 + c), (1 + c) / 2], [1 + alpha, -2 * c, 1 - alpha])


def allpass(f0: float, q: float, fs: float) -> np.ndarray:
    c, alpha = _w(f0, q, fs)
    return _norm([1 - alpha, -2 * c, 1 + alpha], [1 + alpha, -2 * c, 1 - alpha])


def bandpass(f0: float, q: float, fs: float) -> np.ndarray:
    c, alpha = _w(f0, q, fs)
    return _norm([alpha, 0.0, -alpha], [1 + alpha, -2 * c, 1 - alpha])


def _k(f0: float, fs: float) -> float:
    return float(np.tan(np.pi * _clip_f(f0, fs) / fs))


def lowpass1(f0: float, fs: float) -> np.ndarray:
    k = _k(f0, fs)
    return np.array([k / (1 + k), k / (1 + k), 0.0, 1.0, (k - 1) / (k + 1), 0.0])


def highpass1(f0: float, fs: float) -> np.ndarray:
    k = _k(f0, fs)
    return np.array([1 / (1 + k), -1 / (1 + k), 0.0, 1.0, (k - 1) / (k + 1), 0.0])


def allpass1(f0: float, fs: float) -> np.ndarray:
    k = _k(f0, fs)
    a = (k - 1) / (k + 1)
    return np.array([a, 1.0, 0.0, 1.0, a, 0.0])


def butter_highpass(f0: float, order: int, fs: float) -> np.ndarray:
    if order == 1:
        return highpass1(f0, fs)[None, :]
    return np.vstack([highpass(f0, q, fs) for q in BUTTER_Q[order]])


def butter_lowpass(f0: float, order: int, fs: float) -> np.ndarray:
    if order == 1:
        return lowpass1(f0, fs)[None, :]
    return np.vstack([lowpass(f0, q, fs) for q in BUTTER_Q[order]])


def lr_lowpass(f0: float, order: int, fs: float) -> np.ndarray:
    """Linkwitz-Riley rzędu 2, 4 lub 8 jako kwadrat filtra Butterwortha."""
    half = butter_lowpass(f0, order // 2, fs)
    return np.vstack([half, half])


def lr_highpass(f0: float, order: int, fs: float) -> np.ndarray:
    half = butter_highpass(f0, order // 2, fs)
    return np.vstack([half, half])


def lr_allpass(f0: float, order: int, fs: float) -> np.ndarray:
    """Allpass równy sumie LP+HP filtra LR (dla LR2 z odwróconą fazą HP)."""
    if order == 2:
        return allpass1(f0, fs)[None, :]
    return np.vstack([allpass(f0, q, fs) for q in BUTTER_Q[order // 2]])


def lr_hp_sign(order: int) -> float:
    return -1.0 if order == 2 else 1.0


def response(sos: np.ndarray, freqs: np.ndarray, fs: float) -> np.ndarray:
    sos = np.atleast_2d(sos)
    _, h = signal.sosfreqz(sos, worN=np.asarray(freqs, dtype=float), fs=fs)
    return h


class SOSFilter:
    """Kaskada biquadów z zachowaniem stanu między blokami.

    `set_sos` może być wołane z wątku sterującego: nowa macierz jest podmieniana
    referencją, a wątek audio przejmuje ją na początku najbliższego bloku.
    """

    def __init__(self, sos: np.ndarray | None = None, channels: int = 2):
        self.channels = channels
        self._target = np.atleast_2d(identity() if sos is None else np.asarray(sos, dtype=float)).copy()
        self._sos = self._target
        self._zi = np.zeros((self._sos.shape[0], 2, channels))

    @property
    def sos(self) -> np.ndarray:
        return self._target

    def set_sos(self, sos: np.ndarray) -> None:
        self._target = np.ascontiguousarray(np.atleast_2d(sos), dtype=float)

    def reset(self) -> None:
        self._zi = np.zeros((self._sos.shape[0], 2, self.channels))

    def process(self, x: np.ndarray) -> np.ndarray:
        t = self._target
        if t is not self._sos:
            if t.shape[0] != self._sos.shape[0]:
                self._zi = np.zeros((t.shape[0], 2, self.channels))
            self._sos = t
        y, self._zi = signal.sosfilt(self._sos, x, axis=0, zi=self._zi)
        return y

    def response(self, freqs: np.ndarray, fs: float) -> np.ndarray:
        return response(self._target, freqs, fs)
