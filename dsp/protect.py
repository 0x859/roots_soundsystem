"""Zabezpieczenia wyjścia: limiter brickwall z wyprzedzeniem o jeden blok."""

from __future__ import annotations

import numpy as np

from .common import db2lin


class LookaheadLimiter:
    """Limiter szczytowy z wyprzedzeniem `lookahead` próbek.

    Wzmocnienie dla wyprowadzanego segmentu jest liniową rampą między dwiema
    wartościami, które obie nie przekraczają progu podzielonego przez szczyt
    segmentu, więc żadna próbka wyjściowa nie przekracza progu.
    """

    def __init__(self, fs: float, lookahead: int, channels: int, threshold_db: float = -1.0, release_ms: float = 150.0):
        self.fs = fs
        self.lookahead = int(lookahead)
        self.channels = channels
        self.threshold = db2lin(threshold_db)
        self.release_s = release_ms / 1000.0
        self._hold = np.zeros((self.lookahead, channels))
        self._g = 1.0
        self.gain_reduction_db = 0.0

    def set_threshold_db(self, db: float) -> None:
        self.threshold = db2lin(db)

    def process(self, x: np.ndarray) -> np.ndarray:
        n = len(x)
        buf = np.vstack([self._hold, x])
        seg = buf[:n]
        fut = buf[n:]
        self._hold = fut.copy()
        thr = self.threshold
        pk_seg = float(np.max(np.abs(seg))) if n else 0.0
        pk_fut = float(np.max(np.abs(fut))) if len(fut) else 0.0
        need_seg = min(1.0, thr / pk_seg) if pk_seg > 0 else 1.0
        need_fut = min(1.0, thr / pk_fut) if pk_fut > 0 else 1.0
        target = min(need_seg, need_fut)
        g0 = min(self._g, need_seg)
        if target < g0:
            g1 = target
        else:
            c = 1.0 - np.exp(-n / (self.release_s * self.fs))
            g1 = min(g0 + (target - g0) * c, target)
        self._g = g1
        self.gain_reduction_db = float(-20 * np.log10(max(min(g0, g1), 1e-6)))
        if g0 == 1.0 and g1 == 1.0:
            return seg
        ramp = (g0 + (g1 - g0) * np.arange(1, n + 1) / n)[:, None]
        return np.clip(seg * ramp, -thr, thr)
