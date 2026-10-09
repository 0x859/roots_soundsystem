"""Modele kolumn soundsystemowych (tryb Symulacja) i psychoakustyczny „bass feel”."""

from __future__ import annotations

import numpy as np

from engine.params import ParamSpec

from .biquad import SOSFilter, bandpass, high_shelf, highpass, identity, lowpass, peaking, response
from .common import DelayLine, Ramp
from .crossover import ALL_WAYS, WAY_LABELS

# Każdy profil: lista (typ, parametry) przekładana na biquady dla danego fs.
PROFILES: dict[str, dict] = {
    "scoop": {
        "label": "Scoop (tubowy bass bin)",
        "rows": [("hp", 32, 0.9), ("peak", 50, 6.0, 1.4), ("peak", 120, -2.0, 1.0), ("lp", 400, 0.7)],
    },
    "bassbin": {
        "label": "Bass bin 18\" reflex",
        "rows": [("hp", 38, 1.1), ("peak", 70, 3.0, 1.0), ("lp", 800, 0.7)],
    },
    "midhorn": {
        "label": "Mid horn 10\"/12\"",
        "rows": [("hp", 180, 0.8), ("peak", 800, 2.0, 1.2), ("peak", 2500, -2.0, 1.5), ("lp", 6000, 0.7)],
    },
    "tophorn": {
        "label": "Tweeter tubowy (driver)",
        "rows": [("hp", 1200, 0.7), ("peak", 4000, 4.0, 1.0), ("hshelf", 10000, -4.0)],
    },
    "piezo": {
        "label": "Tweetery piezo (bullet)",
        "rows": [("hp", 3500, 0.9), ("peak", 7000, 5.0, 1.2), ("hshelf", 14000, -6.0)],
    },
    "flat": {"label": "Liniowy (bez modelu)", "rows": []},
}
PROFILE_KEYS = tuple(PROFILES)
PROFILE_LABELS = tuple(PROFILES[k]["label"] for k in PROFILE_KEYS)
DEFAULT_PROFILE = {"sub": "scoop", "bass": "bassbin", "mid": "midhorn", "top": "tophorn"}

PARAMS = [
    ParamSpec("sim.enabled", "Modele kolumn", True, kind="bool"),
    ParamSpec("sim.cab_drive", "Kompresja głośników", 0.2, 0.0, 1.0, "%"),
    ParamSpec("sim.width", "Szerokość stereo", 0.6, 0.0, 1.0, "%"),
    ParamSpec("sim.mono_bass", "Mono sub/bass", True, kind="bool"),
    ParamSpec("sim.sub_delay", "Odsunięcie stosu sub", 0.0, 0.0, 10.0, "ms", step=0.05),
    ParamSpec("sim.bassfeel", "Bass feel", 0.0, 0.0, 1.0, "%"),
] + [
    ParamSpec(f"sim.cab.{w}", f"Kolumna {WAY_LABELS[w]}", PROFILE_KEYS.index(DEFAULT_PROFILE[w]), kind="choice", choices=PROFILE_LABELS)
    for w in ALL_WAYS
]


def profile_sos(key: str, fs: float) -> np.ndarray:
    rows = []
    for spec in PROFILES[key]["rows"]:
        kind = spec[0]
        if kind == "hp":
            rows.append(highpass(spec[1], spec[2], fs))
        elif kind == "lp":
            rows.append(lowpass(spec[1], spec[2], fs))
        elif kind == "peak":
            rows.append(peaking(spec[1], spec[2], spec[3], fs))
        elif kind == "hshelf":
            rows.append(high_shelf(spec[1], spec[2], fs))
    return np.vstack(rows) if rows else identity()[None, :]


class CabinetStack:
    """Modele kolumn dla wszystkich dróg i suma do stereo."""

    LOW_WAYS = ("sub", "bass")

    def __init__(self, fs: float, channels: int = 2):
        self.fs = fs
        self.channels = channels
        self.filters = {w: SOSFilter(profile_sos(DEFAULT_PROFILE[w], fs), channels) for w in ALL_WAYS}
        self.profile = dict(DEFAULT_PROFILE)
        self.drive_k = 1.4
        self.width = Ramp(0.6, 30, fs)
        self.mono_bass = True
        self.sub_delay = DelayLine(channels)
        self.bassfeel = BassFeel(fs)
        self.bassfeel_amt = Ramp(0.0, 30, fs)
        self.enabled = True

    def configure(self, p) -> None:
        self.enabled = bool(p["sim.enabled"])
        for w in ALL_WAYS:
            key = PROFILE_KEYS[int(p[f"sim.cab.{w}"])]
            if key != self.profile[w]:
                self.profile[w] = key
                self.filters[w].set_sos(profile_sos(key, self.fs))
        self.drive_k = 1.0 + 2.0 * float(p["sim.cab_drive"])
        self.width.set(float(p["sim.width"]))
        self.mono_bass = bool(p["sim.mono_bass"])
        self.sub_delay.set_delay(int(round(float(p["sim.sub_delay"]) * self.fs / 1000.0)))
        self.bassfeel_amt.set(float(p["sim.bassfeel"]))

    def process(self, ways: dict[str, np.ndarray], n: int) -> np.ndarray:
        if not self.enabled:
            # bez modeli: zwykła suma dróg (LR4 sumuje się płasko), bez kompresji, szerokości i bass feel
            out = np.zeros((n, self.channels))
            for x in ways.values():
                out += x
            return out
        low = np.zeros((n, self.channels))
        high = np.zeros((n, self.channels))
        k = self.drive_k
        for w, x in ways.items():
            y = self.filters[w].process(x)
            if k > 1.001:
                y = np.tanh(y * k) / k
            if w in self.LOW_WAYS:
                if w == "sub":
                    y = self.sub_delay.process(y)
                low += y
            else:
                high += y
        if self.mono_bass and self.channels == 2:
            low[:] = low.mean(axis=1, keepdims=True)
        if self.channels == 2:
            wd = self.width.block(n)
            mid = high.mean(axis=1, keepdims=True)
            side = (high[:, :1] - high[:, 1:]) * 0.5
            high = np.hstack([mid + side * wd, mid - side * wd])
        amt = self.bassfeel_amt.block(n)
        out = low + high
        if not (isinstance(amt, float) and amt == 0.0):
            out = out + self.bassfeel.process(low) * amt
        return out

    def responses(self, freqs: np.ndarray) -> dict[str, np.ndarray]:
        if not self.enabled:
            return {w: np.ones(len(freqs), dtype=complex) for w in self.filters}
        return {w: response(f.sos, freqs, self.fs) for w, f in self.filters.items()}


class BassFeel:
    """Synteza harmonicznych basu, by był słyszalny na słuchawkach bez realnego subu."""

    def __init__(self, fs: float):
        self.fs = fs
        self.pre = SOSFilter(np.vstack([lowpass(120, 0.707, fs), lowpass(120, 0.707, fs)]), 1)
        self.post = SOSFilter(np.vstack([bandpass(160, 0.9, fs), highpass(90, 0.707, fs), lowpass(450, 0.707, fs)]), 1)

    def process(self, low: np.ndarray) -> np.ndarray:
        m = self.pre.process(low.mean(axis=1, keepdims=True))
        h = np.tanh(4.0 * m) * 0.5 + np.abs(m) * 1.5
        y = self.post.process(h) * 2.0
        return np.repeat(y, low.shape[1], axis=1)
