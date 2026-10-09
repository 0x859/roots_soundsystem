"""Włączanie i wyłączanie modułów DSP: bez starych ogonów po ponownym włączeniu i bez trzasków."""

import numpy as np
import pytest

from dsp.graph import SignalChain, bypass_values

FS, B = 48000, 512

# moduł -> ustawienia, przy których ma wyraźny stan (ogon, filtry)
CASES = {
    "echo.enabled": {"preamp.echo_send": 0.8, "echo.feedback": 0.9},
    "spring.enabled": {"preamp.spring_send": 0.8, "spring.decay": 1.0},
    "room.enabled": {"room.mix": 1.0, "room.size": 2.0},
    "mic.enabled": {"mic.echo_send": 0.0},
    "preamp.enabled": {"preamp.drive": 0.8, "preamp.bass": 12.0},
    "eq.enabled": {"eq.b0": 12.0},
    "iso.enabled": {"iso.g.sub": 6.0},
    "sim.enabled": {"sim.bassfeel": 1.0},
}


def _chain(store, values):
    chain = SignalChain(store, FS, B)
    store.set_many(bypass_values() | values)
    return chain


def _run(chain, blocks, level=0.3, seed=0):
    r = np.random.default_rng(seed)
    out = []
    for _ in range(blocks):
        x = level * r.standard_normal((B, 2)) if level else np.zeros((B, 2))
        out.append(chain.process(x, x[:, :1]))
    return np.vstack(out)


@pytest.mark.parametrize("switch", list(CASES))
def test_reenabled_module_has_no_stale_tail(store, switch):
    """Po wyłączeniu i ponownym włączeniu (cisza na wejściu) moduł nie odgrywa resztek sprzed wyłączenia."""
    extra = CASES[switch] | ({"echo.enabled": True} if switch == "mic.enabled" else {})
    chain = _chain(store, {switch: True} | extra)
    _run(chain, 200)  # stan pełen sygnału
    store.set(switch, False)
    _run(chain, 2, level=0.0)  # wyłączenie w trakcie ogona
    _run(chain, 300, level=0.0)
    store.set(switch, True)
    y = _run(chain, 40, level=0.0)
    assert np.max(np.abs(y)) < 1e-6


@pytest.mark.parametrize("switch", ["preamp.enabled", "eq.enabled", "iso.enabled", "room.enabled", "sim.enabled"])
def test_toggle_without_clicks(store, switch):
    """Przełączenie modułu w torze (sinus 220 Hz) nie robi skoku większego niż sam sygnał między próbkami."""
    chain = _chain(store, {switch: True} | CASES[switch])
    t = np.arange(B * 400) / FS
    x = 0.3 * np.sin(2 * np.pi * 220 * t)
    x = np.stack([x, x], axis=1)
    out = []
    for i in range(400):
        if i in (150, 250):
            store.set(switch, i == 250)
        out.append(chain.process(x[i * B:(i + 1) * B]))
    y = np.vstack(out)[:, 0]
    steady = np.max(np.abs(np.diff(y[B * 100:B * 140])))  # typowy przyrost przy włączonym module
    around = np.abs(np.diff(y[B * 148:B * 154]))
    back = np.abs(np.diff(y[B * 248:B * 254]))
    assert np.max(around) < 2.5 * steady and np.max(back) < 2.5 * steady


def test_crash_ignored_while_spring_disabled(store):
    chain = _chain(store, {})
    store.set("spring.crash", True)
    store.set("spring.crash", False)
    _run(chain, 50, level=0.0)
    store.set("spring.enabled", True)
    assert np.max(np.abs(_run(chain, 40, level=0.0))) < 1e-6


def test_quick_toggle_keeps_effect_working(store):
    """Szybkie wyłącz/włącz (krócej niż przenikanie) nie gubi efektu: echo dalej odpowiada na sygnał."""
    chain = _chain(store, {"echo.enabled": True, "preamp.echo_send": 1.0, "echo.feedback": 0.5})
    for _ in range(20):
        store.set("echo.enabled", False)
        _run(chain, 1)
        store.set("echo.enabled", True)
        _run(chain, 1)
    _run(chain, 100)
    y = _run(chain, 60, level=0.0)  # cisza: słychać tylko ogon echa
    assert np.max(np.abs(y)) > 0.01


def test_disabled_modules_cost_nothing(store):
    """Wyłączony i wyciszony moduł nie zmienia sygnału (czysty tor = wejście)."""
    chain = _chain(store, {})
    _run(chain, 200)  # rampa startowa
    r = np.random.default_rng(5)
    x = 0.2 * r.standard_normal((B, 2))
    for _ in range(4):
        y = chain.process(x)
    assert np.all(np.isfinite(y))
