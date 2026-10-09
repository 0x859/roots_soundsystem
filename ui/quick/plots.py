"""Krzywe dla wykresów QML: odpowiedź toru, podział zwrotnicy, analizator widma dróg.

Punkty są znormalizowane (x: 20 Hz–20 kHz w skali log, y: 0 = góra zakresu, 1 = dół),
więc QML tylko skaluje je do rozmiaru wykresu.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from PySide6.QtCore import Property, QObject, QPointF, Signal, Slot

from dsp.crossover import ALL_WAYS, WAY_LABELS

FREQS = np.geomspace(20, 20000, 256)
FFT_N = 4096
SPEC_POINTS = 200
WAY_COLORS = {"sub": "#B07A12", "bass": "#E3A52B", "mid": "#3FB6A8", "top": "#9BC9E0"}
TOTAL_COLOR = "#EEE8DC"
RANGES = {"response": (-36.0, 18.0), "crossover": (-48.0, 12.0), "spectrum": (-100.0, 0.0)}


def _db(h: np.ndarray) -> np.ndarray:
    return 20 * np.log10(np.abs(h) + 1e-9)


def norm_x(freqs: np.ndarray) -> np.ndarray:
    return np.log10(np.asarray(freqs) / 20.0) / 3.0


def curve_points(freqs: np.ndarray, db: np.ndarray, lo: float, hi: float) -> list[QPointF]:
    x = norm_x(freqs)
    y = np.clip((hi - np.asarray(db)) / (hi - lo), 0.0, 1.0)
    return [QPointF(float(a), float(b)) for a, b in zip(x, y, strict=True)]


def _curve(name: str, color: str, freqs: np.ndarray, db: np.ndarray, kind: str, width: float = 1.5,
           dashed: bool = False) -> dict[str, Any]:
    lo, hi = RANGES[kind]
    return {"name": name, "color": color, "width": width, "dashed": dashed, "points": curve_points(freqs, db, lo, hi)}


class QmlPlots(QObject):
    responseChanged = Signal()
    spectrumChanged = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._response: list[dict] = []
        self._crossover: list[dict] = []
        self._spectrum: list[dict] = []
        self._watchers = 0
        self._win = np.hanning(FFT_N)
        self._smooth: dict[str, np.ndarray] = {}

    @Property("QVariantList", notify=responseChanged)
    def response(self) -> list[dict]:
        return self._response

    @Property("QVariantList", notify=responseChanged)
    def crossover(self) -> list[dict]:
        return self._crossover

    @Property("QVariantList", notify=spectrumChanged)
    def spectrum(self) -> list[dict]:
        return self._spectrum

    @Slot(str, result="QVariantList")
    def rangeOf(self, kind: str) -> list[float]:
        return list(RANGES.get(kind, RANGES["response"]))

    @property
    def active(self) -> bool:
        """Czy jakiś widoczny wykres widma potrzebuje danych."""
        return self._watchers > 0

    @Slot(int)
    def watch(self, delta: int) -> None:
        self._watchers = max(0, self._watchers + delta)

    def update_response(self, chain: Any) -> None:
        if chain is None:
            return
        r = chain.response(FREQS)
        resp = [_curve(WAY_LABELS[w], WAY_COLORS[w], FREQS, _db(r["ways"][w]), "response", 1.2, True)
                for w in ALL_WAYS if w in r["ways"]]
        resp.append(_curve("Cały tor", TOTAL_COLOR, FREQS, _db(r["total"]), "response", 2.5))
        xo = []
        total = None
        for w in ALL_WAYS:
            if w in r["xo"]:
                xo.append(_curve(WAY_LABELS[w], WAY_COLORS[w], FREQS, _db(r["xo"][w]), "crossover", 2.0))
                total = r["xo"][w] if total is None else total + r["xo"][w]
        if total is not None:
            xo.append(_curve("Suma", TOTAL_COLOR, FREQS, _db(total), "crossover", 1.2, True))
        self._response, self._crossover = resp, xo
        self.responseChanged.emit()

    def update_spectrum(self, chain: Any, fs: float) -> None:
        if chain is None:
            if self._spectrum:
                self._spectrum = []
                self._smooth.clear()
                self.spectrumChanged.emit()
            return
        f = np.fft.rfftfreq(FFT_N, 1 / fs)
        sel = (f >= 20) & (f <= 20000)
        fx = np.geomspace(20, min(20000, f[sel][-1]), SPEC_POINTS)
        norm = np.sum(self._win) / 2

        def spectrum(name: str, tap) -> np.ndarray:
            x = tap.latest(FFT_N) * self._win
            mag = np.abs(np.fft.rfft(x)) / norm
            db = np.interp(np.log10(fx), np.log10(f[sel]), 20 * np.log10(mag + 1e-9)[sel])
            prev = self._smooth.get(name)
            if prev is not None:
                db = np.maximum(db, prev - 3.0) * 0.4 + prev * 0.6
            self._smooth[name] = db
            return db

        out = [_curve(WAY_LABELS[w], WAY_COLORS[w], fx, spectrum(w, chain.taps[w]), "spectrum", 1.2)
               for w in ALL_WAYS if w in chain.xo.ways]
        out.append(_curve("Wyjście", TOTAL_COLOR, fx, spectrum("out", chain.tap_out), "spectrum", 1.8))
        self._spectrum = out
        self.spectrumChanged.emit()
