import numpy as np
from conftest import BLOCK, FS
from scipy import signal

from dsp.fx_echo import TapeEcho
from dsp.fx_siren import DubSiren
from dsp.fx_spring import SpringReverb
from dsp.protect import LookaheadLimiter
from dsp.room import PartitionedConvolver, generate_ir


def test_partitioned_convolution_matches_fftconvolve():
    rng = np.random.default_rng(1)
    ir = rng.standard_normal((3000, 2)) * np.exp(-np.arange(3000) / 600)[:, None]
    x = rng.standard_normal((BLOCK * 12, 2))
    conv = PartitionedConvolver(ir, BLOCK)
    y = np.vstack([conv.process(x[i:i + BLOCK]) for i in range(0, len(x), BLOCK)])
    ref = np.stack([signal.fftconvolve(x[:, c], ir[:, c])[: len(x)] for c in range(2)], axis=1)
    np.testing.assert_allclose(y, ref, atol=1e-9)


def test_procedural_irs():
    for kind in ("dancehall", "concrete", "outdoor"):
        ir = generate_ir(kind, FS)
        assert ir.shape[1] == 2 and np.all(np.isfinite(ir))
        np.testing.assert_allclose(np.sum(ir**2, axis=0), 1.0, rtol=1e-6)


def _run_echo(store, blocks, **params):
    base = {"echo.wow": 0.0, "echo.glide": 10.0, "echo.drive": 0.0, "echo.hp": 20.0, "echo.lp": 12000.0, "echo.return": 1.0}
    base.update(params)
    store.set_many(base)
    echo = TapeEcho(FS, BLOCK)
    echo.configure(store)
    echo.d = echo.target_d
    x = np.zeros((BLOCK * blocks, 2))
    n = int(0.005 * FS)
    burst = 0.05 * np.sin(2 * np.pi * 1000 * np.arange(n) / FS) * np.hanning(n)
    x[:n] = burst[:, None]
    return np.vstack([echo.process(x[i:i + BLOCK]) for i in range(0, len(x), BLOCK)])


def test_echo_repeats_at_expected_time(store):
    y = _run_echo(store, 120, **{"echo.time": 250.0, "echo.feedback": 0.5})
    d = int(0.25 * FS)
    n = int(0.005 * FS)
    burst = np.sin(2 * np.pi * 1000 * np.arange(n) / FS) * np.hanning(n)
    energies = []
    for k in (1, 2, 3):
        seg = y[k * d - 400:k * d + n + 400, 0]
        onset = int(np.argmax(np.abs(np.correlate(seg, burst, "valid")))) + k * d - 400
        assert abs(onset - k * d) <= 2
        energies.append(np.sqrt(np.sum(seg**2)))
    assert abs(energies[1] / energies[0] - 0.5) < 0.03
    assert abs(energies[2] / energies[1] - 0.5) < 0.03


def test_echo_bpm_sync(store):
    store.set_many({"echo.sync": 3, "echo.bpm": 120.0})
    echo = TapeEcho(FS, BLOCK)
    echo.configure(store)
    assert abs(echo.target_d - 0.5 * FS) < 1


def test_echo_self_oscillation_is_bounded(store):
    y = _run_echo(store, 400, **{"echo.time": 60.0, "echo.feedback": 1.2, "echo.drive": 0.5})
    assert np.all(np.isfinite(y)) and np.max(np.abs(y)) < 2.0


def test_spring_decays_and_crash(store):
    spring = SpringReverb(FS, BLOCK)
    spring.configure(store)
    x = np.zeros((BLOCK * 200, 2))
    x[0] = 1.0
    y = np.vstack([spring.process(x[i:i + BLOCK]) for i in range(0, len(x), BLOCK)])
    assert np.all(np.isfinite(y))
    early = np.sqrt(np.mean(y[: FS // 4] ** 2))
    late = np.sqrt(np.mean(y[-FS // 4:] ** 2))
    assert late < early * 0.05
    store.set("spring.crash", True)
    spring.configure(store)
    assert np.max(np.abs(spring.process(np.zeros((BLOCK, 2))))) > 0


def test_siren_trigger_and_release(store):
    siren = DubSiren(FS)
    siren.configure(store)
    assert siren.process(BLOCK) is None
    store.set("siren.trigger", True)
    siren.configure(store)
    for wave in range(4):
        siren.wave = wave
        y = siren.process(BLOCK)
        assert y.shape == (BLOCK, 2) and np.max(np.abs(y)) > 0.05
    store.set("siren.trigger", False)
    siren.configure(store)
    for _ in range(200):
        y = siren.process(BLOCK)
    assert y is None


def test_limiter_never_exceeds_threshold():
    rng = np.random.default_rng(3)
    lim = LookaheadLimiter(FS, BLOCK, 2, threshold_db=-3.0)
    thr = 10 ** (-3 / 20)
    for i in range(200):
        x = rng.standard_normal((BLOCK, 2)) * (0.1 if i % 7 else 4.0)
        y = lim.process(x)
        assert np.max(np.abs(y)) <= thr + 1e-12
