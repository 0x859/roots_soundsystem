"""Akustyka miejsca: splot jednorodnie partycjonowany (overlap-save) z IR.

Partycje mają długość bloku audio, więc splot nie dodaje latencji.
"""

from __future__ import annotations

import threading
from functools import lru_cache

import numpy as np
from scipy import signal

from engine.params import ParamSpec

from .common import Switch, crossfade

ROOM_KEYS = ("dancehall", "concrete", "outdoor", "custom")
ROOM_LABELS = ("Dancehall", "Sala betonowa", "Plener", "Własna IR")
MAX_IR_S = 4.0

PARAMS = [
    ParamSpec("room.enabled", "Miejsce", True, kind="bool"),
    ParamSpec("room.preset", "Miejsce", 0, kind="choice", choices=ROOM_LABELS),
    ParamSpec("room.mix", "Mix", 0.25, 0.0, 1.0, "%"),
    ParamSpec("room.size", "Rozmiar", 1.0, 0.5, 2.0, "x", step=0.05),
]

ROOM_SPECS = {
    # rt60 dla pasm (niskie, średnie, wysokie), długość, odbicia wczesne (ms, wzmocnienie)
    "dancehall": dict(rt60=(1.1, 0.85, 0.5), length=1.6, er=[(7, 0.6), (11, 0.5), (17, 0.45), (23, 0.35), (31, 0.3), (38, 0.25), (47, 0.2)], build=0.02),
    "concrete": dict(rt60=(2.5, 2.1, 1.4), length=2.8, er=[(9, 0.7), (18, 0.55), (27, 0.5), (36, 0.42), (45, 0.36), (54, 0.3), (63, 0.26), (72, 0.22)], build=0.03),
    "outdoor": dict(rt60=(0.35, 0.28, 0.18), length=0.6, er=[(4, 0.5), (92, 0.35), (143, 0.22), (211, 0.14)], build=0.005, tail=0.35),
}


@lru_cache(maxsize=16)
def generate_ir(kind: str, fs: int, size: float = 1.0, seed: int = 1234) -> np.ndarray:
    """Proceduralna, stereo IR bez ścieżki bezpośredniej, znormalizowana energetycznie."""
    spec = ROOM_SPECS[kind]
    rng = np.random.default_rng(seed)
    n = int(spec["length"] * size * fs)
    t = np.arange(n) / fs
    noise = rng.standard_normal((n, 2))
    bands = [
        signal.sosfilt(signal.butter(4, 250, "low", fs=fs, output="sos"), noise, axis=0),
        signal.sosfilt(signal.butter(2, [250, 4000], "band", fs=fs, output="sos"), noise, axis=0),
        signal.sosfilt(signal.butter(4, 4000, "high", fs=fs, output="sos"), noise, axis=0),
    ]
    tail = np.zeros((n, 2))
    for b, rt in zip(bands, spec["rt60"], strict=True):
        tail += b * np.exp(-6.91 * t / (rt * size))[:, None]
    build = spec["build"] * size
    tail *= (1.0 - np.exp(-t / max(build, 1e-3)))[:, None]
    tail *= spec.get("tail", 1.0)

    er = np.zeros((n, 2))
    for i, (ms, g) in enumerate(spec["er"]):
        idx = int(ms * size * fs / 1000.0)
        if idx < n:
            ch = i % 2
            er[idx, ch] += g
            er[min(n - 1, idx + int(0.0007 * fs)), 1 - ch] += g * 0.6
    er = signal.sosfilt(signal.butter(2, 6000, "low", fs=fs, output="sos"), er, axis=0)

    ir = er + tail * 0.05
    ir /= np.sqrt(np.sum(ir**2, axis=0) + 1e-12)
    return ir


def load_ir_file(path: str, fs: int) -> np.ndarray:
    from math import gcd

    import soundfile as sf

    data, sr = sf.read(path, always_2d=True, dtype="float64")
    if sr != fs:
        g = gcd(int(sr), int(fs))
        data = signal.resample_poly(data, fs // g, int(sr) // g, axis=0)
    if data.shape[1] == 1:
        data = np.repeat(data, 2, axis=1)
    data = data[: int(MAX_IR_S * fs), :2]
    data = data / (np.sqrt(np.sum(data**2, axis=0)) + 1e-12)
    return data


class PartitionedConvolver:
    """Uniformly Partitioned Overlap-Save z kołową linią opóźniającą widm."""

    def __init__(self, ir: np.ndarray, block: int):
        ir = np.atleast_2d(ir.T).T if ir.ndim == 1 else ir
        self.block = B = int(block)
        self.channels = ir.shape[1]
        self.P = P = max(1, int(np.ceil(len(ir) / B)))
        padded = np.zeros((P * B, self.channels))
        padded[: len(ir)] = ir
        parts = padded.reshape(P, B, self.channels)
        H = np.fft.rfft(parts, n=2 * B, axis=1).astype(np.complex128)
        G = np.concatenate([H[:1], H[:0:-1]], axis=0) if P > 1 else H
        self._G2 = np.concatenate([G, G], axis=0)
        self._X = np.zeros((P, B + 1, self.channels), dtype=np.complex128)
        self._prev = np.zeros((B, self.channels))
        self._idx = 0

    def reset(self) -> None:
        self._X[:] = 0.0
        self._prev[:] = 0.0

    def process(self, x: np.ndarray) -> np.ndarray:
        B, P = self.block, self.P
        if len(x) != B:
            raise ValueError("Blok splotu musi mieć stałą długość")
        frame = np.vstack([self._prev, x])
        self._prev = x.copy()
        self._X[self._idx] = np.fft.rfft(frame, axis=0)
        Hs = self._G2[P - self._idx: 2 * P - self._idx]
        Y = np.einsum("pfc,pfc->fc", self._X, Hs)
        self._idx = (self._idx + 1) % P
        return np.fft.irfft(Y, n=2 * B, axis=0)[B:]


class Room:
    def __init__(self, fs: float, block: int, channels: int = 2):
        self.fs = int(fs)
        self.block = block
        self.channels = channels
        self.enabled = True
        self.mix = 0.25
        self.kind = None
        self.size = None
        self.custom_ir: np.ndarray | None = None
        self.custom_path: str | None = None
        self.conv: PartitionedConvolver | None = None
        self._lock = threading.Lock()
        self._dry = 1.0
        self._wet = 0.0
        self.switch = Switch(fs, on_silent=self.reset)

    def reset(self) -> None:
        conv = self.conv
        if conv is not None:
            conv.reset()

    def load_custom(self, path: str) -> None:
        ir = load_ir_file(path, self.fs)
        with self._lock:
            self.custom_ir = ir
            self.custom_path = path
            if self.kind == "custom":
                self._rebuild("custom", self.size or 1.0, force=True)

    def _rebuild(self, kind: str, size: float, force: bool = False) -> None:
        if not force and kind == self.kind and size == self.size:
            return
        if kind == "custom":
            ir = self.custom_ir if self.custom_ir is not None else generate_ir("dancehall", self.fs, round(size, 2))
        else:
            ir = generate_ir(kind, self.fs, round(size, 2))
        self.conv = PartitionedConvolver(ir[:, : self.channels], self.block)
        self.kind, self.size = kind, size

    def configure(self, p) -> None:
        with self._lock:
            self.enabled = bool(p["room.enabled"])
            self.switch.set(self.enabled)
            self.mix = float(p["room.mix"])
            self._dry = float(np.cos(self.mix * np.pi / 2))
            self._wet = float(np.sin(self.mix * np.pi / 2))
            if self.enabled:
                self._rebuild(ROOM_KEYS[int(p["room.preset"])], float(p["room.size"]))

    def process(self, x: np.ndarray) -> np.ndarray:
        conv = self.conv
        g = self.switch.block(len(x))
        if g is None or conv is None or self._wet == 0.0:
            return x
        return crossfade(x, x * self._dry + conv.process(x) * self._wet, g)
