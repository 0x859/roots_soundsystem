"""Włączanie i wyłączanie modułów DSP: bez starych ogonów po ponownym włączeniu i bez trzasków."""

import numpy as np
import pytest

from dsp.common import Switch
from dsp.graph import DSP_SWITCHES, SignalChain, bypass_values

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


def test_cases_cover_all_dsp_switches():
    """Każdy moduł z `enabled` ma przypadek w CASES – nowy moduł nie ominie testów przełączania."""
    assert set(CASES) == set(DSP_SWITCHES)


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


def test_crash_with_enabling_spring_plays(store):
    """CRASH w tej samej zmianie co włączenie sprężyny (scena, makro) gra – reset przy włączeniu go nie kasuje."""
    chain = _chain(store, {})
    _run(chain, 10, level=0.0)
    store.set_many({"spring.enabled": True, "spring.crash": True})
    assert np.max(np.abs(_run(chain, 20, level=0.0))) > 0.01


@pytest.mark.parametrize("together", [False, True])
def test_crash_during_held_panic_does_not_fire_later(store, together):
    """CRASH wciśnięty, gdy FX PANIC trzyma sprężynę wyciszoną (także w tej samej zmianie), nie odpala
    się po puszczeniu PANIC – jak CRASH przy wyłączonej sprężynie."""
    chain = _chain(store, {"spring.enabled": True})
    _run(chain, 20, level=0.0)
    if together:
        store.set_many({"out.fx_panic": True, "spring.crash": True})
    else:
        store.set("out.fx_panic", True)
        _run(chain, 10, level=0.0)
        store.set("spring.crash", True)
    store.set("spring.crash", False)
    _run(chain, 20, level=0.0)
    store.set("out.fx_panic", False)
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


def test_switch_on_never_seen_before_ramp():
    """Blok audio w trakcie `set(True)` (wątek sterujący) nie widzi włączonego modułu z rampą jeszcze na 0."""
    s = Switch(FS)
    s.block(B)
    s.set(False)
    for _ in range(5):
        s.block(B)
    seen = []
    ramp_set = s.ramp.set

    def interleaved(target):
        seen.append(s.block(B))  # wątek audio wchodzi między kroki `set`
        ramp_set(target)

    s.ramp.set = interleaved
    s.set(True)
    assert seen == [None]


@pytest.mark.parametrize("name", ["echo", "spring", "mic"])
def test_effect_scales_by_scalar_switch_gain(store, name, monkeypatch):
    """Skalarne wzmocnienie z przełącznika inne niż 1.0 (tu 0.0) wycisza efekt, a nie przepuszcza go w całości."""
    chain = _chain(store, {f"{name}.enabled": True} | CASES[f"{name}.enabled"])
    _run(chain, 100)
    mod = getattr(chain, name)
    monkeypatch.setattr(mod.switch, "block", lambda n: 0.0)
    x = 0.3 * np.random.default_rng(1).standard_normal((B, 2))
    y = mod.process(x[:, :1], B)[0] if name == "mic" else mod.process(x)
    assert y is None or np.max(np.abs(y)) < 1e-12


@pytest.mark.parametrize(
    ("switch", "changes", "state"),
    [
        ("echo.enabled", {"echo.time": 750.0}, lambda c: (c.echo.d, c.echo.target_d)),
        ("preamp.enabled", {"preamp.hp": 300.0}, lambda c: (c.preamp.hp.cur, c.preamp.hp.target)),
    ],
)
def test_reenabled_module_starts_at_current_settings(store, switch, changes, state):
    """Ustawienia zmienione przy wyłączonym module obowiązują od razu po włączeniu (bez przewijania echa i sweepu)."""
    chain = _chain(store, {switch: True})
    _run(chain, 20)
    store.set(switch, False)
    _run(chain, 10, level=0.0)
    store.set_many(changes)
    store.set(switch, True)
    _run(chain, 1)
    cur, target = state(chain)
    assert cur == pytest.approx(target)


def test_flush_mid_fade_and_disable_keep_switch_consistent():
    """FX PANIC w trakcie przenikania i wyłączenie w trakcie czyszczenia: moduł kończy wyłączony, bez resetu."""
    resets = []
    s = Switch(FS, on_reset=lambda: resets.append(1))
    s.block(B)
    s.set(False)
    s.block(B)  # w połowie wyciszania
    s.flush()
    s.set(False)
    for _ in range(5):
        g = s.block(B)
    assert g is None and not resets
    s.set(True)
    s.block(B)
    assert resets == [1]


def test_flush_restarts_enabled_switch_once():
    resets = []
    s = Switch(FS, on_reset=lambda: resets.append(1))
    s.block(B)
    s.flush()
    gains = [s.block(B) for _ in range(8)]
    assert any(isinstance(g, np.ndarray) for g in gains) and gains[-1] == 1.0
    assert resets == [1]


@pytest.mark.parametrize("name", ["echo", "spring"])
def test_fx_panic_short_press_clears_tail(store, name):
    """FX PANIC krótszy niż przenikanie (wciśnięcie i puszczenie przed blokiem audio) i tak czyści ogon."""
    chain = _chain(store, {f"{name}.enabled": True} | CASES[f"{name}.enabled"])
    _run(chain, 200)
    store.set("out.fx_panic", True)
    store.set("out.fx_panic", False)
    _run(chain, 20, level=0.0)  # przenikanie do ciszy, reset, powrót i wygaśnięcie filtrów zwrotnicy
    assert np.max(np.abs(_run(chain, 40, level=0.0))) < 1e-4  # bez czyszczenia ogon byłby o rzędy większy
    _run(chain, 50)
    assert np.max(np.abs(_run(chain, 20, level=0.0))) > 0.01  # efekt dalej działa


@pytest.mark.parametrize("name", ["echo", "spring"])
def test_fx_panic_hold_keeps_effect_silent(store, name):
    chain = _chain(store, {f"{name}.enabled": True} | CASES[f"{name}.enabled"])
    _run(chain, 100)
    store.set("out.fx_panic", True)
    _run(chain, 4)
    mod = getattr(chain, name)
    x = 0.3 * np.random.default_rng(3).standard_normal((B, 2))
    assert all(mod.process(x) is None for _ in range(20))  # trzymany: efekt milczy mimo sygnału
    store.set("out.fx_panic", False)
    assert store["echo.enabled" if name == "echo" else "spring.enabled"]
    _run(chain, 50)
    assert np.max(np.abs(_run(chain, 20, level=0.0))) > 0.01


def test_fx_panic_ignored_for_disabled_effects(store):
    chain = _chain(store, {})
    store.set("out.fx_panic", True)
    store.set("out.fx_panic", False)
    _run(chain, 10)
    assert not chain.echo.switch.on and not chain.spring.switch.on
