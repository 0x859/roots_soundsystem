"""Kanał mikrofonu MC: gate, HP, kompresor, 3-pasmowy EQ, talkover.

Detekcja poziomu działa na blokach (około 10 ms), a wzmocnienie jest rampowane
liniowo w obrębie bloku, więc nie ma skoków.
"""

from __future__ import annotations

import numpy as np

from engine.params import ParamSpec

from .biquad import SOSFilter, high_shelf, highpass, identity, low_shelf, peaking
from .common import Ramp, Switch, db2lin, lin2db, one_pole_coef

PARAMS = [
    ParamSpec("mic.enabled", "Mikrofon", True, kind="bool"),
    ParamSpec("mic.gain", "Gain", 0.0, -12.0, 36.0, "dB", step=0.5),
    ParamSpec("mic.hp", "HP 100 Hz", True, kind="bool"),
    ParamSpec("mic.gate", "Gate", -55.0, -80.0, -20.0, "dB", step=0.5),
    ParamSpec("mic.comp_thresh", "Próg kompresji", -20.0, -40.0, 0.0, "dB", step=0.5),
    ParamSpec("mic.comp_ratio", "Ratio", 4.0, 1.0, 10.0, ":1", step=0.1),
    ParamSpec("mic.eq_low", "Low", 0.0, -12.0, 12.0, "dB", step=0.5),
    ParamSpec("mic.eq_mid", "Mid", 0.0, -12.0, 12.0, "dB", step=0.5),
    ParamSpec("mic.eq_high", "High", 0.0, -12.0, 12.0, "dB", step=0.5),
    ParamSpec("mic.level", "Poziom", 0.0, -40.0, 12.0, "dB", step=0.5),
    ParamSpec("mic.echo_send", "Send echo", 0.3, 0.0, 1.0, "%"),
    ParamSpec("mic.talkover", "Talkover", False, kind="bool"),
    ParamSpec("mic.talkover_depth", "Głębokość talkover", -10.0, -30.0, 0.0, "dB", step=0.5),
]

GATE_HYST_DB = 4.0
GATE_RELEASE_S = 0.15
COMP_ATTACK_S = 0.01
COMP_RELEASE_S = 0.2
DUCK_ATTACK_S = 0.03
DUCK_RELEASE_S = 0.5


class MicChannel:
    def __init__(self, fs: float, channels: int = 2):
        self.fs = fs
        self.channels = channels
        self.enabled = True
        self.gain = Ramp(1.0, 20, fs)
        self.level = Ramp(1.0, 20, fs)
        self.hp_on = True
        self.hp = SOSFilter(highpass(100.0, 0.707, fs)[None, :], 1)
        self.eq = SOSFilter(np.vstack([identity()] * 3), 1)
        self.gate_db = -55.0
        self.thresh = -20.0
        self.ratio = 4.0
        self.talkover = False
        self.duck_depth = db2lin(-10.0)
        self._gate_open = False
        self._gate_g = 0.0
        self._gr_db = 0.0
        self._comp_g = 1.0
        self._duck = 1.0
        self.level_db = -120.0
        self.gr_db = 0.0
        self.switch = Switch(fs, on_reset=self.reset)

    def reset(self) -> None:
        self.hp.reset()
        self.eq.reset()
        self._gate_open = False
        self._gate_g = 0.0
        self._gr_db = 0.0
        self._comp_g = 1.0
        self.gr_db = 0.0
        self.gain.snap()
        self.level.snap()

    def configure(self, p) -> None:
        self.enabled = bool(p["mic.enabled"])
        self.gain.set(db2lin(float(p["mic.gain"])))
        self.level.set(db2lin(float(p["mic.level"])))
        self.hp_on = bool(p["mic.hp"])
        self.gate_db = float(p["mic.gate"])
        self.thresh = float(p["mic.comp_thresh"])
        self.ratio = float(p["mic.comp_ratio"])
        self.talkover = bool(p["mic.talkover"])
        self.duck_depth = db2lin(float(p["mic.talkover_depth"]))
        self.eq.set_sos(
            np.vstack(
                [
                    low_shelf(120.0, float(p["mic.eq_low"]), self.fs),
                    peaking(2500.0, float(p["mic.eq_mid"]), 1.0, self.fs),
                    high_shelf(8000.0, float(p["mic.eq_high"]), self.fs),
                ]
            )
        )
        self.switch.set(self.enabled)

    @staticmethod
    def _ramp(a: float, b: float, n: int) -> np.ndarray:
        return (a + (b - a) * np.arange(1, n + 1) / n)[:, None]

    def process(self, x: np.ndarray | None, n: int):
        """Zwraca (sygnał stereo lub None, wzmocnienie duckingu muzyki)."""
        duck_prev = self._duck
        sw = self.switch.block(n)
        if sw is None or x is None:
            self._duck = duck_prev + (1.0 - duck_prev) * one_pole_coef(DUCK_RELEASE_S, n, self.fs)
            self.level_db = -120.0
            duck = self._ramp(duck_prev, self._duck, n) if duck_prev != self._duck else 1.0
            return None, duck
        m = x[:, :1] if x.ndim == 2 else x[:, None]
        m = m * self.gain.block(n)
        if self.hp_on:
            m = self.hp.process(m)
        rms = float(np.sqrt(np.mean(m * m)) + 1e-12)
        lvl = lin2db(rms)
        self.level_db = lvl

        if self._gate_open:
            self._gate_open = lvl > self.gate_db - GATE_HYST_DB
        else:
            self._gate_open = lvl > self.gate_db
        g_prev = self._gate_g
        if self._gate_open:
            self._gate_g = 1.0
        else:
            self._gate_g = g_prev * (1.0 - one_pole_coef(GATE_RELEASE_S, n, self.fs))
            if self._gate_g < 1e-3:
                self._gate_g = 0.0

        peak_db = lin2db(float(np.max(np.abs(m))) * self._gate_g + 1e-12)
        over = peak_db - self.thresh
        target_gr = over * (1.0 - 1.0 / self.ratio) if over > 0 else 0.0
        tau = COMP_ATTACK_S if target_gr > self._gr_db else COMP_RELEASE_S
        self._gr_db += (target_gr - self._gr_db) * one_pole_coef(tau, n, self.fs)
        self.gr_db = self._gr_db
        c_prev = self._comp_g
        self._comp_g = db2lin(-self._gr_db)

        dyn = self._ramp(g_prev * c_prev, self._gate_g * self._comp_g, n)
        y = self.eq.process(m * dyn) * self.level.block(n)
        if not (isinstance(sw, float) and sw == 1.0):
            y = y * sw

        duck_target = self.duck_depth if (self.talkover and self._gate_open) else 1.0
        tau = DUCK_ATTACK_S if duck_target < duck_prev else DUCK_RELEASE_S
        self._duck = duck_prev + (duck_target - duck_prev) * one_pole_coef(tau, n, self.fs)
        duck = self._ramp(duck_prev, self._duck, n) if duck_prev != self._duck else self._duck
        if self._gate_g == 0.0 and g_prev == 0.0:
            return None, duck
        return np.repeat(y, self.channels, axis=1), duck
