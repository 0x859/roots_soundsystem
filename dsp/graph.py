"""Tor sygnału soundsystemu: składa moduły DSP i rozdziela zmiany parametrów."""

from __future__ import annotations

from typing import Any

import numpy as np

from engine.params import ParamSpec, ParamStore

from . import cabinets, crossover, eq12, fx_echo, fx_siren, fx_spring, isolator, mic, preamp, room
from .common import Ramp, Tap, db2lin
from .crossover import ALL_WAYS, WAY_LABELS
from .protect import LookaheadLimiter

MODES = ("sim", "multi")
STARTUP_RAMP_MS = 1500.0

OUT_PARAMS = [
    ParamSpec("out.master", "Master", 0.0, -60.0, 6.0, "dB", step=0.5),
    ParamSpec("out.mute", "Mute", False, kind="bool", scene=False),
    ParamSpec("out.limit", "Limiter master", -0.5, -12.0, 0.0, "dB", step=0.1),
] + [ParamSpec(f"out.limit.{w}", f"Limiter {WAY_LABELS[w]}", -1.0, -24.0, 0.0, "dB", step=0.1) for w in ALL_WAYS]

SEND_KEYS = ("preamp.echo_send", "preamp.spring_send", "echo.throw", "mic.echo_send", "siren.echo_send")


def all_specs() -> list[ParamSpec]:
    specs: list[ParamSpec] = []
    for mod in (preamp, mic, fx_echo, fx_spring, fx_siren, eq12, isolator, crossover, cabinets, room):
        specs += mod.PARAMS
    return specs + OUT_PARAMS


def default_channel_map(ways=ALL_WAYS) -> dict[str, tuple[int, int]]:
    return {w: (2 * i, 2 * i + 1) for i, w in enumerate(ways)}


def validate_channel_map(channel_map: dict[str, tuple[int, int]], ways, n_channels: int) -> list[str]:
    """Zwraca listę problemów z mapowaniem dróg na kanały (pusta lista = poprawne)."""
    problems = []
    used: dict[int, str] = {}
    for w in ways:
        chans = channel_map.get(w, (-1, -1))
        if all(c < 0 for c in chans):
            problems.append(f"Droga {WAY_LABELS[w]} nie ma przypisanego kanału")
        for c in chans:
            if c < 0:
                continue
            if c >= n_channels:
                problems.append(f"Droga {WAY_LABELS[w]}: kanał {c + 1} poza zakresem urządzenia ({n_channels} kan.)")
            elif c in used and used[c] != w:
                problems.append(f"Kanał {c + 1} przypisany do dróg {WAY_LABELS[used[c]]} i {WAY_LABELS[w]}")
            used.setdefault(c, w)
    return problems


class SignalChain:
    def __init__(
        self,
        params: ParamStore,
        fs: float,
        block: int,
        mode: str = "sim",
        out_channels: int = 2,
        channel_map: dict[str, tuple[int, int]] | None = None,
    ):
        if mode not in MODES:
            raise ValueError(mode)
        self.params = params
        self.fs = fs
        self.block = block
        self.mode = mode
        self.out_channels = out_channels if mode == "multi" else 2
        self.channel_map = channel_map or default_channel_map()

        self.preamp = preamp.Preamp(fs)
        self.mic = mic.MicChannel(fs)
        self.echo = fx_echo.TapeEcho(fs, block)
        self.spring = fx_spring.SpringReverb(fs, block)
        self.siren = fx_siren.DubSiren(fs)
        self.eq = eq12.Equalizer(fs)
        self.iso = isolator.Isolator(fs)
        self.xo = crossover.Crossover(fs)
        self.cabs = cabinets.CabinetStack(fs)
        self.room = room.Room(fs, block)
        self.modules = {
            "preamp.": self.preamp,
            "mic.": self.mic,
            "echo.": self.echo,
            "spring.": self.spring,
            "siren.": self.siren,
            "eq.": self.eq,
            "iso.": self.iso,
            "xo.": self.xo,
            "sim.": self.cabs,
            "room.": self.room,
        }

        self.send_echo = Ramp(0.0, 10, fs)
        self.send_spring = Ramp(0.0, 10, fs)
        self.mic_echo_send = 0.3
        self.siren_echo_send = 0.6
        self.master = Ramp(1.0, 20, fs)
        self.startup = Ramp(0.0, STARTUP_RAMP_MS, fs)
        self.startup.set(1.0)
        self.master_limiter = LookaheadLimiter(fs, block, 2, -0.5)
        self.limiters = {w: LookaheadLimiter(fs, block, 2, -1.0) for w in ALL_WAYS}

        self.tap_in = Tap()
        self.tap_out = Tap()
        self.taps = {w: Tap() for w in ALL_WAYS}
        self.mic_level_db = -120.0
        self.clip = False

        for mod in self.modules.values():
            mod.configure(params)
        self._configure_sends(params)
        self._configure_out(params)
        params.subscribe(self._on_params)

    def warmup(self) -> None:
        self.preamp.warmup()

    def dispose(self) -> None:
        self.params.unsubscribe(self._on_params)

    # --- parametry (wątek sterujący) ---
    def _on_params(self, changed: dict[str, Any], source: Any) -> None:
        touched = set()
        for key in changed:
            for prefix, mod in self.modules.items():
                if key.startswith(prefix):
                    touched.add(prefix)
        for prefix in touched:
            self.modules[prefix].configure(self.params)
        if any(k in SEND_KEYS for k in changed):
            self._configure_sends(self.params)
        if any(k.startswith("out.") for k in changed):
            self._configure_out(self.params)

    def _configure_sends(self, p) -> None:
        send = float(p["preamp.echo_send"])
        if p["echo.throw"]:
            send = 1.0
        self.send_echo.set(send)
        self.send_spring.set(float(p["preamp.spring_send"]))
        self.mic_echo_send = float(p["mic.echo_send"])
        self.siren_echo_send = float(p["siren.echo_send"])

    def _configure_out(self, p) -> None:
        self.master.set(0.0 if p["out.mute"] else db2lin(float(p["out.master"])))
        self.master_limiter.set_threshold_db(float(p["out.limit"]))
        for w in ALL_WAYS:
            self.limiters[w].set_threshold_db(float(p[f"out.limit.{w}"]))

    # --- audio ---
    def process(self, music: np.ndarray, mic_in: np.ndarray | None = None) -> np.ndarray:
        n = len(music)
        if n == self.block:
            return self._process_block(music, mic_in)
        if n % self.block:
            raise ValueError("Długość wejścia musi być wielokrotnością bloku")
        outs = []
        for i in range(0, n, self.block):
            m = mic_in[i:i + self.block] if mic_in is not None else None
            outs.append(self._process_block(music[i:i + self.block], m))
        return np.vstack(outs)

    def _process_block(self, music: np.ndarray, mic_in: np.ndarray | None) -> np.ndarray:
        n = len(music)
        music = np.asarray(music, dtype=np.float64)
        self.tap_in.push(music)
        x = self.preamp.process(music)

        mic_sig, duck = self.mic.process(mic_in, n)
        self.mic_level_db = self.mic.level_db
        if not (isinstance(duck, float) and duck == 1.0):
            x = x * duck
        siren = self.siren.process(n)

        mix = x.copy()
        echo_in = x * self.send_echo.block(n)
        if mic_sig is not None:
            mix += mic_sig
            if self.mic_echo_send > 0:
                echo_in = echo_in + mic_sig * self.mic_echo_send
        if siren is not None:
            mix += siren
            if self.siren_echo_send > 0:
                echo_in = echo_in + siren * self.siren_echo_send
        e = self.echo.process(echo_in)
        if e is not None:
            mix += e
        s = self.spring.process(x * self.send_spring.block(n))
        if s is not None:
            mix += s

        mix = self.eq.process(mix)
        mix = self.iso.process(mix)
        ways = self.xo.process(mix)
        for w, y in ways.items():
            self.taps[w].push(y)

        gain = self.master.block(n)
        start = self.startup.block(n)
        if self.mode == "sim":
            out = self.cabs.process(ways, n)
            out = self.room.process(out)
            out = self.master_limiter.process(out * gain * start)
        else:
            out = np.zeros((n, self.out_channels))
            for w, y in ways.items():
                y = self.limiters[w].process(y * gain * start)
                ch_l, ch_r = self.channel_map.get(w, (-1, -1))
                if ch_l >= 0 and ch_r >= 0:
                    out[:, ch_l] += y[:, 0]
                    out[:, ch_r] += y[:, 1]
                elif ch_l >= 0 or ch_r >= 0:
                    out[:, max(ch_l, ch_r)] += y.mean(axis=1)
        self.clip = bool(np.max(np.abs(out)) >= 0.999) if n else False
        self.tap_out.push(out[:, :2] if self.mode == "sim" else out)
        return out

    # --- wykresy ---
    def response(self, freqs: np.ndarray) -> dict[str, Any]:
        pre = self.preamp.response(freqs) * self.eq.response(freqs) * self.iso.response(freqs)
        xo = self.xo.responses(freqs)
        cabs = self.cabs.responses(freqs) if self.mode == "sim" else {}
        ways = {w: pre * h * cabs.get(w, 1.0) for w, h in xo.items()}
        total = sum(ways.values()) if ways else pre
        return {"total": total, "ways": ways, "xo": xo}
