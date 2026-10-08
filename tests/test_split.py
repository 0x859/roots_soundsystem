import numpy as np
import pytest

from conftest import FS
from dsp.crossover import Crossover
from dsp.isolator import BANDS, Isolator


def _db(h):
    return 20 * np.log10(np.abs(h) + 1e-15)


@pytest.mark.parametrize("slope", [0, 1])
def test_isolator_flat_sum(store, freqs, slope):
    store.set("iso.slope", slope)
    iso = Isolator(FS)
    iso.configure(store)
    assert np.max(np.abs(_db(iso.response(freqs)))) < 0.1


def test_isolator_flat_sum_time_domain(store):
    iso = Isolator(FS)
    iso.configure(store)
    x = np.zeros((8192, 2))
    x[0] = 1.0
    y = iso.process(x)
    h = np.fft.rfft(y[:, 0])
    f = np.fft.rfftfreq(len(y), 1 / FS)
    band = (f > 20) & (f < 20000)
    assert np.max(np.abs(_db(h[band]))) < 0.1


def _band_center(store, b):
    edges = [20.0] + [store[f"iso.f{i}"] for i in range(1, 5)] + [20000.0]
    i = BANDS.index(b)
    return float(np.sqrt(edges[i] * edges[i + 1]))


@pytest.mark.parametrize("band", BANDS)
def test_isolator_kill_depth(store, band):
    """Kill przy 48 dB/okt: tłumienie w geometrycznym środku pasma.

    Granicę wyznacza nachylenie sąsiednich filtrów: pasma są wąskie (ok. 2 oktawy),
    więc przy LR8 osiągalne jest ok. 38-50 dB, a nie 60 dB.
    """
    store.set(f"iso.kill.{band}", True)
    iso = Isolator(FS)
    iso.configure(store)
    f0 = _band_center(store, band)
    att = -_db(iso.response(np.array([f0])))[0]
    assert att >= 35.0, f"{band}: {att:.1f} dB @ {f0:.0f} Hz"


def test_isolator_kill_ramp_is_smooth(store):
    iso = Isolator(FS)
    iso.configure(store)
    t = np.arange(4 * 512) / FS
    x = np.repeat(np.sin(2 * np.pi * 30 * t)[:, None], 2, axis=1)
    iso.process(x[:512])
    store.set("iso.kill.sub", True)
    iso.configure(store)
    y = iso.process(x[512:1024])
    assert np.max(np.abs(np.diff(y[:, 0]))) < 0.05


@pytest.mark.parametrize("ways", [0, 1, 2])
@pytest.mark.parametrize("slope", [0, 1])
def test_crossover_flat_sum(store, freqs, ways, slope):
    store.set_many({"xo.ways": ways, "xo.slope": slope, "xo.subsonic": False})
    xo = Crossover(FS)
    xo.configure(store)
    total = sum(xo.responses(freqs).values())
    assert np.max(np.abs(_db(total))) < 0.1


def test_crossover_polarity_and_delay(store):
    store.set_many({"xo.subsonic": False, "xo.invert.top": True, "xo.delay.sub": 2.0})
    xo = Crossover(FS)
    xo.configure(store)
    x = np.zeros((4096, 2))
    x[0] = 1.0
    out = xo.process(x)
    assert np.argmax(np.abs(out["sub"][:, 0])) >= int(0.002 * FS)
    ref = Crossover(FS)
    store.set_many({"xo.invert.top": False, "xo.delay.sub": 0.0})
    ref.configure(store)
    np.testing.assert_allclose(out["top"], -ref.process(x)["top"], atol=1e-12)


def test_crossover_top_is_highpassed(store):
    xo = Crossover(FS)
    xo.configure(store)
    h = xo.responses(np.array([50.0]))["top"]
    assert _db(h)[0] < -60
