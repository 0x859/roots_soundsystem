"""Preamp (nasycenie, półki) i zwrotnica w dziedzinie czasu."""

import numpy as np
import pytest
from conftest import BLOCK, FS

from dsp.crossover import WAYS_BY_COUNT, Crossover
from dsp.preamp import Preamp, tube_shape


def _harmonics(y, f0, n=4):
    spec = np.abs(np.fft.rfft(y * np.hanning(len(y))))
    k = int(round(f0 * len(y) / FS))
    return [spec[k * h - 2 : k * h + 3].max() for h in range(1, n + 1)]


def test_tube_shape_bias_adds_even_harmonics():
    t = np.arange(FS) / FS
    x = 0.5 * np.sin(2 * np.pi * 1000 * t)
    sym = _harmonics(tube_shape(x, 0.6, 0.0), 1000)
    asym = _harmonics(tube_shape(x, 0.6, 1.0), 1000)
    assert sym[1] / sym[0] < 1e-3  # bez asymetrii: brak 2. harmonicznej
    assert asym[1] / asym[0] > 1e-2  # asymetria: wyraźna 2. harmoniczna
    assert np.max(np.abs(tube_shape(10 * x, 1.0, 1.0))) < 10  # ograniczone


def test_tube_shape_zero_in_zero_out():
    assert np.allclose(tube_shape(np.zeros(4), 0.8, 0.7), 0.0, atol=1e-12)


def _gain_db(h):
    return 20 * np.log10(np.abs(h))


def test_preamp_shelves(store):
    pre = Preamp(FS)
    store.set_many({"preamp.bass": 12.0, "preamp.treble": -12.0})
    pre.configure(store)
    f = np.array([30.0, 1000.0, 18000.0])
    g = _gain_db(pre.response(f))
    assert g[0] > 9.0 and abs(g[1]) < 2.0 and g[2] < -9.0


def test_preamp_mono_sums_channels(store):
    pre = Preamp(FS)
    store.set_many({"preamp.mono": True, "preamp.drive": 0.0})
    pre.configure(store)
    x = np.zeros((BLOCK, 2))
    x[:, 0] = np.sin(np.arange(BLOCK) * 0.05)
    y = np.vstack([pre.process(x) for _ in range(4)])
    assert np.allclose(y[:, 0], y[:, 1])


@pytest.mark.parametrize("count", [2, 3, 4])
def test_crossover_ways_sum_to_allpass_in_time(store, count):
    """Suma dróg dla impulsu ma płaskie widmo amplitudowe (LR = allpass)."""
    store.set_many({"xo.ways": count - 2, "xo.slope": 1, "xo.subsonic": False})
    xo = Crossover(FS)
    xo.configure(store)
    n = 8 * BLOCK
    x = np.zeros((n, 2))
    x[0] = 1.0
    out = [xo.process(x[i : i + BLOCK]) for i in range(0, n, BLOCK)]
    assert set(out[0]) == set(WAYS_BY_COUNT[count])
    total = np.vstack([sum(o.values()) for o in out])[:, 0]
    mag = np.abs(np.fft.rfft(total))
    f = np.fft.rfftfreq(n, 1 / FS)
    band = (f > 30) & (f < 16000)
    assert np.max(np.abs(20 * np.log10(mag[band]))) < 0.2


def test_crossover_mute_and_gain(store):
    store.set_many({"xo.ways": 0, "xo.mute.top": True, "xo.gain.bass": -6.0, "xo.subsonic": False})
    xo = Crossover(FS)
    xo.configure(store)
    t = np.arange(BLOCK * 20) / FS
    x = np.repeat(np.sin(2 * np.pi * 60 * t)[:, None], 2, axis=1)
    y = {w: [] for w in WAYS_BY_COUNT[2]}
    for i in range(0, len(x), BLOCK):
        for w, b in xo.process(x[i : i + BLOCK]).items():
            y[w].append(b)
    top = np.vstack(y["top"])
    bass = np.vstack(y["bass"])[-BLOCK * 5 :, 0]
    assert np.max(np.abs(top[-BLOCK * 5 :])) < 1e-6
    assert 20 * np.log10(np.sqrt(2) * np.std(bass)) == pytest.approx(-6.0, abs=0.5)
