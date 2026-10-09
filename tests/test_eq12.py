import numpy as np
from conftest import FS
from scipy import signal

from dsp.eq12 import BANDS, Equalizer, peaking_sos


def test_flat_eq_is_identity(store):
    eq = Equalizer(FS)
    eq.configure(store)
    x = np.random.default_rng(0).standard_normal((4096, 2))
    np.testing.assert_allclose(eq.process(x), x, atol=1e-12)


def test_plus_6db_at_1khz():
    sos = peaking_sos(1000, 6.0, 1.4, FS)[None, :]
    _, h = signal.sosfreqz(sos, worN=[1000.0], fs=FS)
    assert abs(20 * np.log10(abs(h[0])) - 6.0) < 0.05


def test_slider_changes_only_one_row(store):
    eq = Equalizer(FS)
    eq.configure(store)
    before = eq.sos.copy()
    store.set("eq.b5", 6.0)
    eq.configure(store)
    changed = np.where(np.any(eq.sos != before, axis=1))[0]
    assert list(changed) == [5]
    h = eq.response(np.array([float(BANDS[5])]))
    assert abs(20 * np.log10(abs(h[0])) - 6.0) < 0.1
