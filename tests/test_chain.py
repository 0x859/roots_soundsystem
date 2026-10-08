import time

import numpy as np
import pytest

from conftest import BLOCK, FS
from dsp.graph import SignalChain, default_channel_map, validate_channel_map
from dsp.mic import MicChannel
from dsp.preamp import Preamp


def _music(n, seed=0):
    rng = np.random.default_rng(seed)
    t = np.arange(n) / FS
    x = 0.3 * np.sin(2 * np.pi * 55 * t) + 0.1 * rng.standard_normal(n)
    return np.repeat(x[:, None], 2, axis=1)


@pytest.mark.parametrize("mode", ["sim", "multi"])
def test_chain_runs_and_is_bounded(store, mode):
    store.set_many({"preamp.echo_send": 0.5, "preamp.spring_send": 0.3, "siren.trigger": True, "sim.bassfeel": 0.5})
    chain = SignalChain(store, FS, BLOCK, mode, out_channels=8)
    mic = np.random.default_rng(2).standard_normal((BLOCK * 40, 1)) * 0.2
    y = chain.process(_music(BLOCK * 40), mic)
    assert y.shape == (BLOCK * 40, 2 if mode == "sim" else 8)
    assert np.all(np.isfinite(y))
    assert np.max(np.abs(y)) <= 1.0
    r = chain.response(np.geomspace(20, 20000, 64))
    assert np.all(np.isfinite(r["total"]))
    chain.dispose()


def test_multi_channel_routing(store):
    chain = SignalChain(store, FS, BLOCK, "multi", out_channels=8, channel_map=default_channel_map())
    chain.startup.snap(1.0)
    t = np.arange(BLOCK * 60) / FS
    tone = np.repeat((0.3 * np.sin(2 * np.pi * 55 * t))[:, None], 2, axis=1)
    y = chain.process(tone)
    rms = np.sqrt(np.mean(y[-BLOCK * 20:] ** 2, axis=0))
    assert rms[0] > 0.1
    assert rms[0] > rms[6] * 100  # sub (55 Hz) na kanałach 1-2, top na 7-8 prawie cisza
    chain.dispose()


def test_channel_map_validation():
    ways = ("sub", "bass", "mid", "top")
    assert validate_channel_map(default_channel_map(), ways, 8) == []
    assert validate_channel_map(default_channel_map(), ways, 4)
    bad = default_channel_map()
    bad["top"] = (0, 1)
    assert validate_channel_map(bad, ways, 8)


def test_params_propagate_to_chain(store):
    chain = SignalChain(store, FS, BLOCK)
    store.set("eq.b3", 6.0)
    assert chain.eq._gains[3] == 6.0
    store.set("echo.throw", True)
    assert chain.send_echo.target == 1.0
    chain.dispose()
    store.set("eq.b3", -3.0)
    assert chain.eq._gains[3] == 6.0


def test_preamp_neutral_settings_preserve_level(store):
    store.set_many({"preamp.drive": 0.0})
    pre = Preamp(FS)
    pre.configure(store)
    t = np.arange(BLOCK * 20) / FS
    x = np.repeat((0.5 * np.sin(2 * np.pi * 1000 * t))[:, None], 2, axis=1)
    y = np.vstack([pre.process(x[i:i + BLOCK]) for i in range(0, len(x), BLOCK)])
    assert abs(np.sqrt(np.mean(y[-4096:] ** 2)) / np.sqrt(np.mean(x[-4096:] ** 2)) - 1.0) < 0.02


def test_preamp_sweep_filter(store):
    store.set_many({"preamp.hp": 800.0, "preamp.drive": 0.0})
    pre = Preamp(FS)
    pre.configure(store)
    t = np.arange(BLOCK * 40) / FS
    x = np.repeat((0.5 * np.sin(2 * np.pi * 60 * t))[:, None], 2, axis=1)
    y = np.vstack([pre.process(x[i:i + BLOCK]) for i in range(0, len(x), BLOCK)])
    assert np.sqrt(np.mean(y[-4096:] ** 2)) < 0.02


def test_mic_gate_and_talkover(store):
    store.set_many({"mic.talkover": True, "mic.talkover_depth": -12.0})
    mic = MicChannel(FS)
    mic.configure(store)
    quiet = np.random.default_rng(0).standard_normal((BLOCK, 1)) * 1e-5
    y, duck = mic.process(quiet, BLOCK)
    assert y is None
    t = np.arange(BLOCK) / FS
    voice = (0.3 * np.sin(2 * np.pi * 300 * t))[:, None]
    for _ in range(40):
        y, duck = mic.process(voice, BLOCK)
    assert y is not None and y.shape == (BLOCK, 2)
    d = duck if isinstance(duck, float) else float(duck[-1, 0])
    assert abs(20 * np.log10(d) + 12.0) < 1.0


def test_performance_budget(store):
    """Pełny tor (wszystkie moduły aktywne) na bloku 512 poniżej 50% czasu bloku."""
    store.set_many({"preamp.echo_send": 0.5, "preamp.spring_send": 0.3, "siren.trigger": True, "sim.bassfeel": 0.3, "room.preset": 1})
    chain = SignalChain(store, FS, BLOCK)
    chain.warmup()
    mic = np.random.default_rng(2).standard_normal((BLOCK, 1)) * 0.2
    music = _music(BLOCK)
    for _ in range(20):
        chain.process(music, mic)
    times = []
    for _ in range(200):
        t0 = time.perf_counter()
        chain.process(music, mic)
        times.append(time.perf_counter() - t0)
    budget = BLOCK / FS
    load = float(np.median(times)) / budget
    print(f"obciążenie mediana {load * 100:.1f}%, p95 {np.percentile(times, 95) / budget * 100:.1f}%")
    assert load < 0.5
    chain.dispose()
