"""Aktywna zwrotnica Linkwitz-Riley 2-4 drożna z wyrównaniem czasowym i polaryzacją."""

from __future__ import annotations

import numpy as np

from engine.params import ParamSpec

from .bandsplit import BandSplitter
from .biquad import SOSFilter, butter_highpass, identity, response
from .common import DelayLine, Ramp, db2lin

ALL_WAYS = ("sub", "bass", "mid", "top")
WAY_LABELS = {"sub": "Sub", "bass": "Bass", "mid": "Mid", "top": "Top"}
WAY_CHOICES = ("2 drogi", "3 drogi", "4 drogi")
WAYS_BY_COUNT = {2: ("bass", "top"), 3: ("bass", "mid", "top"), 4: ("sub", "bass", "mid", "top")}
SPLITS_BY_COUNT = {2: ("xo.f3",), 3: ("xo.f2", "xo.f3"), 4: ("xo.f1", "xo.f2", "xo.f3")}
SLOPES = ("12 dB/okt (LR2)", "24 dB/okt (LR4)")
SLOPE_ORDER = (2, 4)
MAX_DELAY_MS = 20.0
TOP_MIN_HZ = 800.0

PARAMS = [
    ParamSpec("xo.ways", "Liczba dróg", 2, kind="choice", choices=WAY_CHOICES),
    ParamSpec("xo.slope", "Nachylenie", 1, kind="choice", choices=SLOPES),
    ParamSpec("xo.f1", "Sub / bass", 90.0, 40.0, 200.0, "Hz", scale="log"),
    ParamSpec("xo.f2", "Bass / mid", 350.0, 150.0, 1000.0, "Hz", scale="log"),
    ParamSpec("xo.f3", "Mid / top", 3500.0, TOP_MIN_HZ, 8000.0, "Hz", scale="log"),
    ParamSpec("xo.subsonic", "Subsonic", True, kind="bool"),
    ParamSpec("xo.subsonic_hz", "Subsonic HP", 25.0, 15.0, 40.0, "Hz", scale="log"),
]
for _w in ALL_WAYS:
    PARAMS += [
        ParamSpec(f"xo.gain.{_w}", f"{WAY_LABELS[_w]} gain", 0.0, -24.0, 12.0, "dB", step=0.5),
        ParamSpec(f"xo.delay.{_w}", f"{WAY_LABELS[_w]} delay", 0.0, 0.0, MAX_DELAY_MS, "ms", step=0.05),
        ParamSpec(f"xo.invert.{_w}", f"{WAY_LABELS[_w]} faza", False, kind="bool"),
        ParamSpec(f"xo.mute.{_w}", f"{WAY_LABELS[_w]} mute", False, kind="bool"),
    ]


class _Layout:
    """Niezmienny zestaw filtrów dla danej liczby dróg i nachylenia (podmieniany atomowo)."""

    def __init__(self, fs, ways, freqs, order, channels):
        self.ways = ways
        self.order = order
        self.splitter = BandSplitter(fs, freqs, order, channels)


class Crossover:
    def __init__(self, fs: float, channels: int = 2):
        self.fs = fs
        self.channels = channels
        self.subsonic_on = True
        self.subsonic = SOSFilter(butter_highpass(25.0, 2, fs), channels)
        self._subsonic_sos = self.subsonic.sos
        self.layout = _Layout(fs, WAYS_BY_COUNT[4], [90.0, 350.0, 3500.0], 4, channels)
        self.gains = {w: Ramp(1.0, 20, fs) for w in ALL_WAYS}
        self.delays = {w: DelayLine(channels) for w in ALL_WAYS}
        self.polarity = {w: 1.0 for w in ALL_WAYS}

    @property
    def ways(self) -> tuple[str, ...]:
        return self.layout.ways

    def configure(self, p) -> None:
        count = (2, 3, 4)[int(p["xo.ways"])]
        order = SLOPE_ORDER[int(p["xo.slope"])]
        ways = WAYS_BY_COUNT[count]
        freqs = sorted(float(p[k]) for k in SPLITS_BY_COUNT[count])
        lay = self.layout
        if lay.ways != ways or lay.order != order:
            self.layout = _Layout(self.fs, ways, freqs, order, self.channels)
        elif lay.splitter.freqs != freqs:
            lay.splitter.set_freqs(freqs)
        self.subsonic_on = bool(p["xo.subsonic"])
        self._subsonic_sos = butter_highpass(float(p["xo.subsonic_hz"]), 2, self.fs)
        self.subsonic.set_sos(self._subsonic_sos)
        for w in ALL_WAYS:
            g = 0.0 if p[f"xo.mute.{w}"] else db2lin(float(p[f"xo.gain.{w}"]))
            self.gains[w].set(g)
            self.polarity[w] = -1.0 if p[f"xo.invert.{w}"] else 1.0
            self.delays[w].set_delay(int(round(float(p[f"xo.delay.{w}"]) * self.fs / 1000.0)))

    def process(self, x: np.ndarray) -> dict[str, np.ndarray]:
        lay = self.layout
        n = len(x)
        if self.subsonic_on:
            x = self.subsonic.process(x)
        out = {}
        for way, band in zip(lay.ways, lay.splitter.process(x), strict=False):  # wątek audio
            y = self.delays[way].process(band)
            out[way] = y * (self.gains[way].block(n) * self.polarity[way])
        return out

    def responses(self, freqs: np.ndarray) -> dict[str, np.ndarray]:
        lay = self.layout
        pre = response(self._subsonic_sos, freqs, self.fs) if self.subsonic_on else response(identity(), freqs, self.fs)
        out = {}
        w = 2 * np.pi * np.asarray(freqs) / self.fs
        for way, h in zip(lay.ways, lay.splitter.responses(freqs), strict=True):
            d = self.delays[way].delay
            out[way] = pre * h * self.gains[way].target * self.polarity[way] * np.exp(-1j * w * d)
        return out
