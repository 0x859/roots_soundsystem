"""Syrena dubowa: oscylator z polyBLEP, LFO, pitch sweep i obwiednią."""

from __future__ import annotations

import numpy as np

from engine.params import ParamSpec

from .common import db2lin

WAVES = ("Sinus", "Trójkąt", "Piła", "Prostokąt")
LFO_SHAPES = ("Sinus", "Trójkąt", "Prostokąt", "Piła w górę", "Piła w dół")

PARAMS = [
    ParamSpec("siren.trigger", "Syrena", False, kind="bool", momentary=True, scene=False),
    ParamSpec("siren.wave", "Fala", 0, kind="choice", choices=WAVES),
    ParamSpec("siren.pitch", "Wysokość", 440.0, 60.0, 2000.0, "Hz", scale="log"),
    ParamSpec("siren.lfo_rate", "LFO rate", 4.0, 0.1, 20.0, "Hz", scale="log"),
    ParamSpec("siren.lfo_depth", "LFO depth", 5.0, 0.0, 24.0, "st", step=0.1),
    ParamSpec("siren.lfo_shape", "Kształt LFO", 0, kind="choice", choices=LFO_SHAPES),
    ParamSpec("siren.sweep", "Sweep", 0.0, -24.0, 24.0, "st", step=0.5),
    ParamSpec("siren.sweep_time", "Czas sweepu", 1.0, 0.05, 5.0, "s", scale="log"),
    ParamSpec("siren.release", "Release", 150.0, 5.0, 2000.0, "ms", scale="log"),
    ParamSpec("siren.level", "Poziom", -12.0, -40.0, 0.0, "dB", step=0.5),
    ParamSpec("siren.echo_send", "Send echo", 0.6, 0.0, 1.0, "%"),
]

SIREN_MEMORY_KEYS = [s.key for s in PARAMS if s.key not in ("siren.trigger",)]
ATTACK_S = 0.004


def polyblep(t: np.ndarray, dt: np.ndarray) -> np.ndarray:
    r = np.zeros_like(t)
    m1 = t < dt
    x = t[m1] / dt[m1]
    r[m1] = x + x - x * x - 1.0
    m2 = t > 1.0 - dt
    x = (t[m2] - 1.0) / dt[m2]
    r[m2] = x * x + x + x + 1.0
    return r


def lfo_value(frac: np.ndarray, shape: int) -> np.ndarray:
    if shape == 0:
        return np.sin(2 * np.pi * frac)
    if shape == 1:
        return 1.0 - 4.0 * np.abs(frac - 0.5)
    if shape == 2:
        return np.where(frac < 0.5, 1.0, -1.0)
    if shape == 3:
        return 2.0 * frac - 1.0
    return 1.0 - 2.0 * frac


def oscillator(t: np.ndarray, dt: np.ndarray, wave: int) -> np.ndarray:
    if wave == 0:
        return np.sin(2 * np.pi * t)
    if wave == 1:
        return 1.0 - 4.0 * np.abs(t - 0.5)
    if wave == 2:
        return 2.0 * t - 1.0 - polyblep(t, dt)
    sq = np.where(t < 0.5, 1.0, -1.0)
    return sq + polyblep(t, dt) - polyblep((t + 0.5) % 1.0, dt)


class DubSiren:
    def __init__(self, fs: float, channels: int = 2):
        self.fs = fs
        self.channels = channels
        self.trigger = False
        self.wave = 0
        self.pitch = 440.0
        self.lfo_rate = 4.0
        self.lfo_depth = 5.0
        self.lfo_shape = 0
        self.sweep = 0.0
        self.sweep_time = 1.0
        self.release_s = 0.15
        self.level = db2lin(-12.0)
        self.env = 0.0
        self._gate = False
        self._t = 0.0
        self._lfo_ph = 0.0
        self._ph = 0.0

    def configure(self, p) -> None:
        self.trigger = bool(p["siren.trigger"])
        self.wave = int(p["siren.wave"])
        self.pitch = float(p["siren.pitch"])
        self.lfo_rate = float(p["siren.lfo_rate"])
        self.lfo_depth = float(p["siren.lfo_depth"])
        self.lfo_shape = int(p["siren.lfo_shape"])
        self.sweep = float(p["siren.sweep"])
        self.sweep_time = float(p["siren.sweep_time"])
        self.release_s = float(p["siren.release"]) / 1000.0
        self.level = db2lin(float(p["siren.level"]))

    @property
    def active(self) -> bool:
        return self.trigger or self.env > 1e-5

    def process(self, n: int) -> np.ndarray | None:
        gate = self.trigger
        if gate and not self._gate:
            self._t = 0.0
            if self.env < 1e-3:
                self._lfo_ph = 0.0
        self._gate = gate
        if not gate and self.env <= 1e-5:
            self.env = 0.0
            return None
        k = np.arange(1, n + 1)
        tgt = 1.0 if gate else 0.0
        tau = ATTACK_S if gate else self.release_s
        env = tgt + (self.env - tgt) * np.exp(-k / (tau * self.fs))
        self.env = float(env[-1])
        t = self._t + k / self.fs
        self._t = float(t[-1])
        sweep = self.sweep * np.minimum(t / self.sweep_time, 1.0)
        lfo_ph = self._lfo_ph + self.lfo_rate * k / self.fs
        self._lfo_ph = float(lfo_ph[-1] % 1.0)
        lfo = lfo_value(lfo_ph % 1.0, self.lfo_shape)
        freq = np.minimum(self.pitch * 2.0 ** ((sweep + self.lfo_depth * lfo) / 12.0), 0.45 * self.fs)
        dt = freq / self.fs
        ph = self._ph + np.cumsum(dt)
        self._ph = float(ph[-1] % 1.0)
        y = oscillator(ph % 1.0, dt, self.wave) * env * self.level
        return np.repeat(y[:, None], self.channels, axis=1)
