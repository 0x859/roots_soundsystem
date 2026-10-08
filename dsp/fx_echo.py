"""Echo taśmowe w stylu Space Echo.

Opóźnienie jest zawsze dłuższe niż blok, więc odczyt z linii dotyczy wyłącznie
próbek zapisanych we wcześniejszych blokach i cały blok liczy się wektorowo,
łącznie z modulacją wow/flutter i „bezwładnością taśmy” przy zmianie czasu.
"""

from __future__ import annotations

import numpy as np

from engine.params import ParamSpec

from .biquad import SOSFilter, highpass, lowpass
from .common import Ramp

SYNC_CHOICES = ("Wolny", "1/2", "1/4.", "1/4", "1/8.", "1/8", "1/16")
SYNC_BEATS = (None, 2.0, 1.5, 1.0, 0.75, 0.5, 0.25)
MIN_MS = 20.0
MAX_MS = 1500.0
WOW_HZ, WOW_MS = 0.55, 2.0
FLUTTER_HZ, FLUTTER_MS = 7.3, 0.12

PARAMS = [
    ParamSpec("echo.enabled", "Echo", True, kind="bool"),
    ParamSpec("echo.time", "Czas", 375.0, MIN_MS, MAX_MS, "ms", scale="log"),
    ParamSpec("echo.sync", "Sync", 0, kind="choice", choices=SYNC_CHOICES),
    ParamSpec("echo.bpm", "BPM", 75.0, 50.0, 200.0, "BPM", step=0.1),
    ParamSpec("echo.feedback", "Feedback", 0.55, 0.0, 1.2, "%"),
    ParamSpec("echo.hp", "HP pętli", 150.0, 20.0, 1000.0, "Hz", scale="log"),
    ParamSpec("echo.lp", "LP pętli", 3500.0, 800.0, 12000.0, "Hz", scale="log"),
    ParamSpec("echo.drive", "Nasycenie taśmy", 0.3, 0.0, 1.0, "%"),
    ParamSpec("echo.wow", "Wow/flutter", 0.25, 0.0, 1.0, "%"),
    ParamSpec("echo.glide", "Bezwładność", 250.0, 10.0, 2000.0, "ms", scale="log"),
    ParamSpec("echo.return", "Powrót", 0.8, 0.0, 1.5, "%"),
    ParamSpec("echo.throw", "Throw", False, kind="bool", momentary=True, scene=False),
]


def echo_time_ms(p) -> float:
    beats = SYNC_BEATS[int(p["echo.sync"])]
    if beats is None:
        return float(p["echo.time"])
    return float(np.clip(beats * 60000.0 / float(p["echo.bpm"]), MIN_MS, MAX_MS))


class TapeEcho:
    def __init__(self, fs: float, block: int, channels: int = 2):
        self.fs = fs
        self.channels = channels
        self.enabled = True
        self.min_d = max(MIN_MS * fs / 1000.0, block + 3.0)
        need = MAX_MS * fs / 1000.0 + (WOW_MS + FLUTTER_MS) * fs / 1000.0 + 4 * block + 16
        size = 1 << int(np.ceil(np.log2(need)))
        self.buf = np.zeros((size, channels))
        self.mask = size - 1
        self.w = 0
        self.target_d = 375.0 * fs / 1000.0
        self.d = self.target_d
        self.glide_s = 0.25
        self.fb = 0.55
        self.drive_k = 1.9
        self.wow = 0.25
        self.ph_wow = 0.0
        self.ph_flut = 0.0
        self.ret = Ramp(0.8, 20, fs)
        self.loop = SOSFilter(np.vstack([highpass(150, 0.707, fs), lowpass(3500, 0.707, fs)]), channels)
        self._idle = 0

    def configure(self, p) -> None:
        self.enabled = bool(p["echo.enabled"])
        self.target_d = max(self.min_d, echo_time_ms(p) * self.fs / 1000.0)
        self.glide_s = float(p["echo.glide"]) / 1000.0
        self.fb = float(p["echo.feedback"])
        self.drive_k = 1.0 + 3.0 * float(p["echo.drive"])
        self.wow = float(p["echo.wow"])
        self.ret.set(float(p["echo.return"]))
        self.loop.set_sos(np.vstack([highpass(float(p["echo.hp"]), 0.707, self.fs), lowpass(float(p["echo.lp"]), 0.707, self.fs)]))

    def process(self, x: np.ndarray) -> np.ndarray | None:
        n = len(x)
        if not self.enabled:
            return None
        k = np.arange(1, n + 1)
        r = np.exp(-1.0 / (self.glide_s * self.fs))
        d = self.target_d + (self.d - self.target_d) * r ** k
        self.d = float(d[-1])
        if self.wow > 0:
            pw = self.ph_wow + 2 * np.pi * WOW_HZ / self.fs * k
            pf = self.ph_flut + 2 * np.pi * FLUTTER_HZ / self.fs * k
            self.ph_wow = float(pw[-1] % (2 * np.pi))
            self.ph_flut = float(pf[-1] % (2 * np.pi))
            mod = self.wow * self.fs / 1000.0 * (WOW_MS * (1 + np.sin(pw)) + FLUTTER_MS * (1 + np.sin(pf))) * 0.5
            d = d + mod
        d = np.maximum(d, self.min_d)
        pos = self.w + np.arange(n) - d
        i0 = np.floor(pos).astype(np.int64)
        frac = (pos - i0)[:, None]
        a = self.buf[i0 & self.mask]
        b = self.buf[(i0 + 1) & self.mask]
        wet = a + (b - a) * frac
        fb = self.loop.process(wet)
        fb = np.tanh(self.drive_k * self.fb * fb) / self.drive_k
        idx = (self.w + np.arange(n)) & self.mask
        self.buf[idx] = np.tanh(x * 0.9) / 0.9 + fb
        self.w = (self.w + n) & self.mask
        return wet * self.ret.block(n)
