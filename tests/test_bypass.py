"""Czysty tor: wyłączone moduły DSP (start domyślny) przepuszczają muzykę bez zmiany barwy."""

import numpy as np
from conftest import BLOCK, FS

from dsp.graph import DSP_SWITCHES, SignalChain, bypass_values


def test_dsp_switches_cover_all_modules(store):
    assert set(DSP_SWITCHES) == {k for k in store.specs if k.endswith(".enabled")}
    assert {"preamp.enabled", "eq.enabled", "iso.enabled", "sim.enabled", "room.enabled", "echo.enabled"} <= set(DSP_SWITCHES)
    assert all(v is False for v in bypass_values().values())


def test_cabinets_bypass_sums_ways(store):
    store.set("sim.enabled", False)
    chain = SignalChain(store, FS, BLOCK, "sim")
    try:
        cabs = chain.cabs
        rng = np.random.default_rng(3)
        ways = {w: rng.standard_normal((BLOCK, 2)) * 0.1 for w in ("sub", "bass", "mid", "top")}
        out = cabs.process(ways, BLOCK)
        np.testing.assert_allclose(out, sum(ways.values()), atol=1e-12)
        freqs = np.geomspace(20, 20000, 64)
        assert all(np.allclose(h, 1.0) for h in cabs.responses(freqs).values())
    finally:
        chain.dispose()


def test_clean_chain_is_flat(store):
    """Wszystkie moduły wyłączone: odpowiedź płaska (±0.2 dB) powyżej ochronnego subsonic HP, poziom zachowany."""
    store.set_many(bypass_values())
    chain = SignalChain(store, FS, BLOCK, "sim")
    try:
        freqs = np.geomspace(60, 16000, 200)
        mag = 20 * np.log10(np.abs(chain.response(freqs)["total"]))
        assert np.max(np.abs(mag)) < 0.2
        # subsonic (ochrona) zostaje także w czystym torze
        sub = 20 * np.log10(np.abs(chain.response(np.array([15.0]))["total"]))
        assert sub[0] < -3

        t = np.arange(BLOCK * 200) / FS  # dłużej niż narastanie głośności przy starcie (1,5 s)
        x = 0.2 * np.sin(2 * np.pi * 1000 * t)[:, None] * np.ones((1, 2))
        y = chain.process(x)
        tail = slice(BLOCK * 160, None)
        rms_in = np.sqrt(np.mean(x[tail] ** 2))
        rms_out = np.sqrt(np.mean(y[tail] ** 2))
        assert abs(20 * np.log10(rms_out / rms_in)) < 0.3
    finally:
        chain.dispose()


def test_restore_state_startup_modes(store):
    import json

    from presets.store import restore_state

    saved = json.dumps({"echo.enabled": True, "eq.enabled": True, "echo.feedback": 0.9})
    restore_state(store, saved, "clean")
    assert store["echo.feedback"] == 0.9  # ustawienia zostają
    assert not any(store[k] for k in DSP_SWITCHES)  # ale moduły są wyłączone
    restore_state(store, saved, "last")
    assert store["echo.enabled"] is True and store["eq.enabled"] is True
    restore_state(store, "{zepsute", "clean")
    assert store["echo.enabled"] is False
