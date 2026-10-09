"""Silnik audio: wejście muzyki (VB-Cable) i mikrofonu, wyjście stereo lub wielokanałowe."""

from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, field

import numpy as np

from dsp.common import RingBuffer
from dsp.crossover import WAYS_BY_COUNT
from dsp.graph import SignalChain, validate_channel_map

from .devices import fit_channels
from .params import ParamStore

try:
    import sounddevice as sd
except Exception:  # brak PortAudio
    sd = None

CABLE_NAME = "CABLE Output"
TARGET_FILL_BLOCKS = 2
MAX_FILL_BLOCKS = 6


class EngineError(RuntimeError):
    pass


@dataclass
class DeviceInfo:
    index: int
    name: str
    hostapi: str
    max_in: int
    max_out: int
    default_fs: float

    @property
    def label(self) -> str:
        return f"{self.name} [{self.hostapi}]"


@dataclass
class EngineConfig:
    music_in: int | None
    output: int | None
    mic_in: int | None = None
    mode: str = "sim"
    fs: int = 48000
    block: int = 512
    channel_map: dict[str, tuple[int, int]] = field(default_factory=dict)
    out_channels: int = 2
    sim_mirror: bool = False  # Symulacja: kopia 1-2 na kolejne pary wyjść (np. słuchawki 3-4 w Scarlett 4i4)
    music_offset: int = 0  # pierwszy kanał wejścia muzyki (4 = Loopback 5-6 w Scarlett 4i4)
    mic_channel: int = 0  # kanał wejścia mikrofonu (0 = wejście 1)


@dataclass
class EngineStats:
    running: bool = False
    cpu_load: float = 0.0
    cpu_peak: float = 0.0
    underruns: int = 0
    overflows: int = 0
    mic_underruns: int = 0
    callback_errors: int = 0
    last_error: str = ""
    latency_ms: float = 0.0
    mic_latency_ms: float = 0.0
    status_flags: int = 0
    primed: bool = False


def hostapi_name(idx: int) -> str:
    return sd.query_hostapis(idx)["name"] if sd else ""


def list_devices(wasapi_only: bool = True) -> list[DeviceInfo]:
    if sd is None:
        return []
    out = []
    for i, d in enumerate(sd.query_devices()):
        api = hostapi_name(d["hostapi"])
        if wasapi_only and "WASAPI" not in api:
            continue
        out.append(DeviceInfo(i, d["name"], api, d["max_input_channels"], d["max_output_channels"], d["default_samplerate"]))
    return out


def find_cable_output(devices: list[DeviceInfo]) -> int | None:
    for d in devices:
        if d.max_in > 0 and CABLE_NAME.lower() in d.name.lower():
            return d.index
    return None


def wasapi_default_output() -> int | None:
    if sd is None:
        return None
    for api in sd.query_hostapis():
        if "WASAPI" in api["name"]:
            idx = api.get("default_output_device", -1)
            return idx if idx is not None and idx >= 0 else None
    return None


def _wasapi_settings():
    if sd is None:
        return None
    try:
        return sd.WasapiSettings(exclusive=False, auto_convert=True)
    except TypeError:
        return sd.WasapiSettings(exclusive=False)


class AudioEngine:
    def __init__(self, params: ParamStore):
        self.params = params
        self.chain: SignalChain | None = None
        self.config: EngineConfig | None = None
        self.stats = EngineStats()
        self._in_stream = None
        self._mic_stream = None
        self._out_stream = None
        self._music_ring: RingBuffer | None = None
        self._mic_ring: RingBuffer | None = None
        self._music_buf = None
        self._mic_buf = None
        self._primed = False
        self._drops = 0
        self._in_channels = 2
        self._in_offset = 0
        self._mic_col = 0
        self._lost = False

    @property
    def running(self) -> bool:
        return self._out_stream is not None

    def device_lost(self) -> bool:
        """True, gdy strumień przestał działać bez polecenia stop (np. odłączone urządzenie)."""
        if not self.running:
            return False
        for s in (self._in_stream, self._out_stream, self._mic_stream):
            if s is not None and not s.active:
                return True
        return self._lost

    def build_chain(self, cfg: EngineConfig) -> SignalChain:
        chain = SignalChain(self.params, cfg.fs, cfg.block, cfg.mode, cfg.out_channels, cfg.channel_map or None)
        chain.warmup()
        return chain

    def start(self, cfg: EngineConfig) -> None:
        if sd is None:
            raise EngineError("Biblioteka sounddevice/PortAudio jest niedostępna.")
        if cfg.music_in is None:
            raise EngineError("Nie wybrano wejścia muzyki (CABLE Output).")
        if cfg.output is None:
            raise EngineError("Nie wybrano urządzenia wyjściowego.")
        self.stop()
        out_dev = sd.query_devices(cfg.output)
        if cfg.mode == "multi":
            ways = WAYS_BY_COUNT[(2, 3, 4)[int(self.params["xo.ways"])]]
            cfg.out_channels = int(out_dev["max_output_channels"])
            problems = validate_channel_map(cfg.channel_map, ways, cfg.out_channels)
            if problems:
                raise EngineError("Niepoprawne mapowanie kanałów:\n" + "\n".join(problems))
        else:
            max_out = int(out_dev["max_output_channels"])
            if max_out < 2:
                raise EngineError("Urządzenie wyjściowe musi mieć co najmniej 2 kanały.")
            cfg.out_channels = 4 if cfg.sim_mirror and max_out >= 4 else 2

        self.config = cfg
        self.stats = EngineStats()
        self._lost = False
        self.chain = self.build_chain(cfg)
        cap = cfg.block * 32
        self._music_ring = RingBuffer(cap, 2)
        self._music_buf = np.zeros((cfg.block, 2), dtype=np.float32)
        self._primed = False
        self._drops = 0
        extra = _wasapi_settings()
        try:
            in_dev = sd.query_devices(cfg.music_in)
            max_in = int(in_dev["max_input_channels"])
            if max_in < 1:
                raise EngineError("Wybrane wejście muzyki nie ma kanałów wejściowych.")
            offset = cfg.music_offset if 0 <= cfg.music_offset < max_in else 0
            in_ch = min(2, max_in - offset)
            self._in_channels = in_ch
            self._in_offset = offset
            self._in_stream = sd.InputStream(
                device=cfg.music_in, channels=offset + in_ch, samplerate=cfg.fs, blocksize=cfg.block,
                dtype="float32", callback=self._in_cb, extra_settings=extra, latency="low",
            )
            if cfg.mic_in is not None:
                self._mic_ring = RingBuffer(cap, 1)
                self._mic_buf = np.zeros((cfg.block, 1), dtype=np.float32)
                mic_max = int(sd.query_devices(cfg.mic_in)["max_input_channels"])
                self._mic_col = cfg.mic_channel if 0 <= cfg.mic_channel < mic_max else 0
                self._mic_stream = sd.InputStream(
                    device=cfg.mic_in, channels=self._mic_col + 1, samplerate=cfg.fs, blocksize=cfg.block,
                    dtype="float32", callback=self._mic_cb, extra_settings=extra, latency="low",
                )
            self._out_stream = sd.OutputStream(
                device=cfg.output, channels=cfg.out_channels, samplerate=cfg.fs, blocksize=cfg.block,
                dtype="float32", callback=self._out_cb, extra_settings=extra, latency="low",
                finished_callback=self._finished,
            )
            self._in_stream.start()
            if self._mic_stream is not None:
                self._mic_stream.start()
            self._out_stream.start()
        except EngineError:
            self.stop()
            raise
        except Exception as exc:
            self.stop()
            raise EngineError(f"Nie udało się otworzyć strumieni audio: {exc}") from exc
        self.stats.running = True
        self._update_latency()

    def stop(self) -> None:
        streams = (self._out_stream, self._in_stream, self._mic_stream)
        self._out_stream = self._in_stream = self._mic_stream = None
        for s in streams:
            if s is None:
                continue
            try:
                s.stop()
                s.close()
            except Exception:
                pass
        if self.chain is not None:
            self.chain.dispose()
        self.chain = None
        self._mic_ring = None
        self.stats.running = False

    def _update_latency(self) -> None:
        cfg = self.config
        try:
            lin = self._in_stream.latency if self._in_stream else 0.0
            lout = self._out_stream.latency if self._out_stream else 0.0
            ring = TARGET_FILL_BLOCKS * cfg.block / cfg.fs
            # limiter z wyprzedzeniem dokłada jeden blok
            self.stats.latency_ms = (lin + lout + ring + cfg.block / cfg.fs) * 1000.0
            if self._mic_stream is not None:
                self.stats.mic_latency_ms = (self._mic_stream.latency + lout + ring + cfg.block / cfg.fs) * 1000.0
        except Exception:
            pass

    # --- callbacki (wątek audio) ---
    def _finished(self) -> None:
        if self._out_stream is not None:
            self._lost = True

    def _in_cb(self, indata, frames, t, status) -> None:
        if status:
            self.stats.status_flags += 1
        off = self._in_offset
        data = indata[:, off : off + self._in_channels]
        if self._in_channels == 1:
            data = np.repeat(data, 2, axis=1)
        self._music_ring.write(data)

    def _mic_cb(self, indata, frames, t, status) -> None:
        ring = self._mic_ring
        if ring is not None:
            col = self._mic_col
            ring.write(indata[:, col : col + 1])

    def _out_cb(self, outdata, frames, t, status) -> None:
        t0 = time.perf_counter()
        cfg = self.config
        chain = self.chain
        ring = self._music_ring
        if status:
            self.stats.status_flags += 1
        if chain is None or ring is None or frames != cfg.block:
            outdata.fill(0)
            return
        fill = len(ring)
        if not self._primed:
            if fill < TARGET_FILL_BLOCKS * frames:
                outdata.fill(0)
                self.stats.primed = False
                return
            self._primed = True
            self.stats.primed = True
        if fill > MAX_FILL_BLOCKS * frames:
            ring.discard(fill - TARGET_FILL_BLOCKS * frames)
            self._drops += 1
        got = ring.read(frames, self._music_buf)
        if got < frames:
            self.stats.underruns += 1
            if got == 0:
                self._primed = False
        mic = None
        mring = self._mic_ring
        if mring is not None:
            mfill = len(mring)
            if mfill > MAX_FILL_BLOCKS * frames:
                mring.discard(mfill - TARGET_FILL_BLOCKS * frames)
            if mring.read(frames, self._mic_buf) < frames:
                self.stats.mic_underruns += 1
            mic = self._mic_buf
        try:
            out = chain.process(self._music_buf, mic)
            outdata[:] = fit_channels(out, outdata.shape[1]).astype(np.float32, copy=False)
        except Exception:
            outdata.fill(0)
            self.stats.callback_errors += 1
            self.stats.last_error = traceback.format_exc(limit=3)
        load = (time.perf_counter() - t0) / (frames / cfg.fs)
        st = self.stats
        st.cpu_load = 0.9 * st.cpu_load + 0.1 * load
        st.cpu_peak = max(load, st.cpu_peak * 0.995)
        st.overflows = self._drops + ring.overflows
