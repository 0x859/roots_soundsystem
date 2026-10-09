"""Wykresy: odpowiedź całego toru, podział zwrotnicy i analizator widma dróg."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QSizePolicy, QTabWidget

from dsp.crossover import ALL_WAYS, WAY_LABELS

from .theme import WAY_COLORS

pg.setConfigOptions(antialias=True, background="#121418", foreground="#b8bcc4")

FREQS = np.geomspace(20, 20000, 512)
FFT_N = 4096


def _db(h: np.ndarray) -> np.ndarray:
    return 20 * np.log10(np.abs(h) + 1e-9)


def _freq_plot(ymin: float, ymax: float, ylabel: str = "dB") -> pg.PlotWidget:
    w = pg.PlotWidget()
    p = w.getPlotItem()
    p.setLogMode(x=True, y=False)
    p.showGrid(x=True, y=True, alpha=0.15)
    p.setXRange(np.log10(20), np.log10(20000), padding=0)
    p.setYRange(ymin, ymax, padding=0)
    p.setLabel("bottom", "Hz")
    p.setLabel("left", ylabel)
    p.setMouseEnabled(x=False, y=False)
    p.hideButtons()
    p.addLegend(offset=(-10, 10))
    return w


class PlotTabs(QTabWidget):
    def __init__(self, chain_getter, fs_getter):
        super().__init__()
        self.chain_getter = chain_getter
        self.fs_getter = fs_getter
        self.setMinimumSize(240, 220)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.resp = _freq_plot(-36, 18)
        self.resp_ways = {w: self.resp.plot(name=WAY_LABELS[w], pen=pg.mkPen(WAY_COLORS[w], width=1, style=pg.QtCore.Qt.DashLine)) for w in ALL_WAYS}
        self.resp_total = self.resp.plot(name="Cały tor", pen=pg.mkPen("#f0f0f0", width=2.5))
        self.addTab(self.resp, "Odpowiedź toru")

        self.xo = _freq_plot(-48, 12)
        self.xo_ways = {w: self.xo.plot(name=WAY_LABELS[w], pen=pg.mkPen(WAY_COLORS[w], width=2)) for w in ALL_WAYS}
        self.xo_sum = self.xo.plot(name="Suma", pen=pg.mkPen("#f0f0f0", width=1.5, style=pg.QtCore.Qt.DotLine))
        self.addTab(self.xo, "Zwrotnica")

        self.spec = _freq_plot(-100, 0, "dBFS")
        self.spec_ways = {w: self.spec.plot(name=WAY_LABELS[w], pen=pg.mkPen(WAY_COLORS[w], width=1)) for w in ALL_WAYS}
        self.spec_out = self.spec.plot(name="Wyjście", pen=pg.mkPen("#f0f0f0", width=1.8))
        self.addTab(self.spec, "Analizator")

        self._win = np.hanning(FFT_N)
        self._smooth: dict[str, np.ndarray] = {}

    def sizeHint(self) -> QSize:
        return QSize(280, 280)

    def update_response(self) -> None:
        chain = self.chain_getter()
        if chain is None:
            return
        r = chain.response(FREQS)
        self.resp_total.setData(FREQS, _db(r["total"]))
        for w, curve in self.resp_ways.items():
            if w in r["ways"]:
                curve.setData(FREQS, _db(r["ways"][w]))
            else:
                curve.setData([], [])
        total_xo = 0
        for w, curve in self.xo_ways.items():
            if w in r["xo"]:
                curve.setData(FREQS, _db(r["xo"][w]))
                total_xo = total_xo + r["xo"][w]
            else:
                curve.setData([], [])
        if not isinstance(total_xo, int):
            self.xo_sum.setData(FREQS, _db(total_xo))

    def update_spectrum(self, chain) -> None:
        if self.currentWidget() is not self.spec:
            return
        if chain is None:
            for c in list(self.spec_ways.values()) + [self.spec_out]:
                c.setData([], [])
            self._smooth.clear()
            return
        fs = self.fs_getter()
        f = np.fft.rfftfreq(FFT_N, 1 / fs)
        sel = (f >= 20) & (f <= 20000)
        norm = np.sum(self._win) / 2

        def spectrum(name, tap):
            x = tap.latest(FFT_N) * self._win
            mag = np.abs(np.fft.rfft(x)) / norm
            db = 20 * np.log10(mag + 1e-9)[sel]
            prev = self._smooth.get(name)
            db = db if prev is None or len(prev) != len(db) else np.maximum(db, prev - 3.0) * 0.4 + prev * 0.6
            self._smooth[name] = db
            return db

        self.spec_out.setData(f[sel], spectrum("out", chain.tap_out))
        for w, curve in self.spec_ways.items():
            if w in chain.xo.ways:
                curve.setData(f[sel], spectrum(w, chain.taps[w]))
            else:
                curve.setData([], [])
