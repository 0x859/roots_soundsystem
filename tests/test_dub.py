"""Gesty dubowe w torze: izolator przed efektami (kill zostawia ogon) i DRY CUT."""

import numpy as np
import pytest

from dsp.graph import SignalChain, bypass_values
from dsp.isolator import BANDS
from ui import layout_profile as lp

FS, B = 48000, 512
PRE, POST = 1, 0  # iso.position: Muzyka (przed efektami) / Suma (po efektach)
KILL_ALL = {f"iso.kill.{b}": True for b in BANDS}
ECHO = {"echo.enabled": True, "preamp.echo_send": 1.0, "echo.feedback": 0.6, "echo.time": 120.0}
SETTLE = 12  # bloki na rampę i wygaśnięcie filtrów zwrotnicy po wyciszeniu
QUIET = 1e-4


def _chain(store, values):
    chain = SignalChain(store, FS, B)
    store.set_many(bypass_values() | values)
    chain.startup.snap(1.0)
    return chain


def _noise(blocks, level=0.3, seed=0):
    return level * np.random.default_rng(seed).standard_normal((B * blocks, 2))


def _sine(blocks, hz=220.0, level=0.3):
    t = np.arange(B * blocks) / FS
    x = level * np.sin(2 * np.pi * hz * t)
    return np.stack([x, x], axis=1)


@pytest.mark.parametrize(("position", "tail"), [(PRE, True), (POST, False)])
def test_kill_before_fx_keeps_echo_tail(store, position, tail):
    """Izolator przed efektami: kill wszystkich pasm ucina muzykę, ale echo wybrzmiewa; na sumie ucina też ogon."""
    chain = _chain(store, ECHO | {"iso.enabled": True, "iso.position": position})
    chain.process(_noise(100))
    store.set_many(KILL_ALL)
    chain.process(_noise(SETTLE, seed=1))  # rampa kill i ogon filtrów zwrotnicy
    y = chain.process(_noise(10, seed=2))
    if tail:
        assert np.max(np.abs(y)) > 0.01
    else:
        assert np.max(np.abs(y)) < QUIET
    chain.dispose()


@pytest.mark.parametrize(("position", "heard"), [(PRE, True), (POST, False)])
def test_mic_not_killed_when_isolator_before_fx(store, position, heard):
    chain = _chain(store, {"mic.enabled": True, "iso.enabled": True, "iso.position": position} | KILL_ALL)
    voice = _sine(60, hz=300.0)[:, :1]
    y = chain.process(np.zeros((B * 60, 2)), voice)[-B * 10:]
    if heard:
        assert np.sqrt(np.mean(y ** 2)) > 0.05
    else:
        assert np.max(np.abs(y)) < 1e-6
    chain.dispose()


def test_isolator_position_change_without_clicks(store):
    """Przeniesienie izolatora w trakcie grania: krótkie przenikanie, bez skoków i bez podwójnego filtrowania."""
    chain = _chain(store, {"iso.enabled": True, "iso.g.sub": 6.0})
    x = _sine(400)
    out = []
    for i in range(400):
        if i in (150, 250):
            store.set("iso.position", PRE if i == 150 else POST)
        out.append(chain.process(x[i * B:(i + 1) * B]))
        if i == 200:
            assert chain.iso.active_pre
    assert not chain.iso.active_pre
    y = np.vstack(out)[:, 0]
    steady = np.max(np.abs(np.diff(y[B * 100:B * 140])))
    for at in (150, 250):
        assert np.max(np.abs(np.diff(y[B * (at - 2):B * (at + 6)]))) < 2.5 * steady
    # po przeniesieniu poziom jak przed nim (izolator działa raz, nie dwa razy i nie wcale)
    rms = [np.sqrt(np.mean(y[B * a:B * (a + 40)] ** 2)) for a in (100, 200, 350)]
    assert rms[1] == pytest.approx(rms[0], rel=0.02) and rms[2] == pytest.approx(rms[0], rel=0.02)
    chain.dispose()


def test_isolator_position_change_works_after_quick_flips(store):
    """Szybkie przełączanie miejsca (krócej niż przenikanie) kończy się aktywnym izolatorem w ostatnio wybranym miejscu."""
    chain = _chain(store, {"iso.enabled": True})
    x = _sine(1)
    for i in range(7):
        store.set("iso.position", PRE if i % 2 == 0 else POST)
        chain.process(x)
    for _ in range(10):
        chain.process(x)
    assert chain.iso.active_pre and chain.iso.switch.on
    store.set_many(KILL_ALL)
    for _ in range(SETTLE):
        chain.process(x)
    assert np.max(np.abs(chain.process(x))) < QUIET
    chain.dispose()


def test_isolator_position_from_start(store):
    """Miejsce ustawione przed pierwszym blokiem obowiązuje od razu (bez przenikania na starcie)."""
    store.set_many(bypass_values() | {"iso.enabled": True, "iso.position": PRE})
    chain = SignalChain(store, FS, B)
    assert chain.iso.active_pre
    chain.dispose()


def test_dry_cut_keeps_effects(store):
    """DRY CUT wycisza suchą muzykę, echo dalej gra; puszczenie przywraca poziom."""
    chain = _chain(store, ECHO)
    before = chain.process(_noise(100))[-B * 20:]
    store.set("preamp.cut", True)
    chain.process(_noise(1, seed=1))
    y = chain.process(_noise(10, seed=2))
    assert np.max(np.abs(y)) > 0.01  # echo
    store.set("echo.enabled", False)
    chain.process(_noise(SETTLE, seed=3))
    assert np.max(np.abs(chain.process(_noise(5, seed=4)))) < QUIET  # bez efektów cisza
    store.set_many({"preamp.cut": False, "echo.enabled": True})
    after = chain.process(_noise(100, seed=5))[-B * 20:]
    assert np.sqrt(np.mean(after ** 2)) == pytest.approx(np.sqrt(np.mean(before ** 2)), rel=0.1)
    chain.dispose()


def test_dry_cut_without_clicks(store):
    chain = _chain(store, {})
    x = _sine(100)
    out = []
    for i in range(100):
        if i in (50, 70):
            store.set("preamp.cut", i == 50)
        out.append(chain.process(x[i * B:(i + 1) * B]))
    y = np.vstack(out)[:, 0]
    steady = np.max(np.abs(np.diff(y[B * 20:B * 40])))
    assert np.max(np.abs(np.diff(y[B * 48:B * 74]))) < 1.5 * steady  # rampa 5 ms zamiast skoku
    assert np.max(np.abs(y[B * (50 + SETTLE):B * 70])) < QUIET
    chain.dispose()


def test_dry_cut_is_a_live_gesture(store):
    spec = store.specs["preamp.cut"]
    assert spec.momentary and not spec.scene and lp.is_hold(spec)
    assert "preamp.cut" not in store.snapshot()
    assert "iso.position" in store.snapshot()
    prof = lp.default_profile()
    assert "preamp.cut" in [p["param"] for p in prof["pads"]]
    assert prof["shortcuts"]["C"] == "preamp.cut"


def test_fx_hot_warns_on_self_oscillation(store):
    """Ostrzeżenie o samooscylacji: sprzężenie >= 100% albo powrót echa blisko przesterowania."""
    chain = _chain(store, ECHO)
    chain.process(_noise(20))
    assert not chain.fx_hot()
    store.set("echo.feedback", 1.05)
    assert chain.fx_hot()
    store.set("echo.enabled", False)
    assert not chain.fx_hot()
    store.set_many({"echo.enabled": True, "echo.feedback": 0.5})
    chain.echo.peak = 0.95
    assert chain.fx_hot()
    chain.dispose()


def test_fx_panic_is_a_live_gesture(store):
    spec = store.specs["out.fx_panic"]
    assert spec.momentary and not spec.scene and lp.is_hold(spec)
    prof = lp.default_profile()
    out = next(c for c in prof["cards"] if c["id"] == "out")
    assert "out.fx_panic" in [c["param"] for c in out["controls"]]
    assert prof["shortcuts"]["P"] == "out.fx_panic"


def test_mic_throw_sends_mic_to_echo(store):
    """THROW MIC: chwilowy send mikrofonu do echa na 100% – ostatnie słowo MC wraca echem."""
    tails = []
    for throw in (False, True):
        chain = _chain(store, ECHO | {"mic.enabled": True, "mic.echo_send": 0.0, "preamp.echo_send": 0.0})
        store.set("mic.throw", throw)
        assert chain.mic_echo_send == (1.0 if throw else 0.0)
        chain.process(np.zeros((B * 30, 2)), _sine(30, hz=300.0)[:, :1])
        store.set("mic.throw", False)
        assert chain.mic_echo_send == 0.0
        y = chain.process(np.zeros((B * 30, 2)), np.zeros((B * 30, 1)))[B * 10:]
        tails.append(np.max(np.abs(y)))
        chain.dispose()
    assert tails[0] < QUIET and tails[1] > 0.01


def test_swell_raises_feedback_and_restores(store):
    from dsp.fx_echo import SWELL_FEEDBACK

    chain = _chain(store, ECHO)
    store.set("echo.swell", True)
    assert chain.echo.fb == SWELL_FEEDBACK and chain.fx_hot()
    store.set("echo.swell", False)
    assert chain.echo.fb == pytest.approx(0.6)
    store.set_many({"echo.feedback": 1.1, "echo.swell": True})
    assert chain.echo.fb == pytest.approx(1.1)  # wyższe sprzężenie użytkownika zostaje
    chain.dispose()


def test_swell_glides_feedback(store):
    """Sprzężenie zmienia się z rampą (SWELL narasta, a nie skacze)."""
    chain = _chain(store, ECHO)
    chain.process(_noise(5))
    store.set("echo.swell", True)
    chain.process(_noise(1))
    assert 0.6 < chain.echo.fb_gain.value < chain.echo.fb
    chain.process(_noise(60))
    assert chain.echo.fb_gain.value == pytest.approx(chain.echo.fb)
    chain.dispose()


@pytest.mark.parametrize("key", ["mic.throw", "echo.swell"])
def test_new_gestures_are_momentary(store, key):
    spec = store.specs[key]
    assert spec.momentary and not spec.scene and lp.is_hold(spec)
