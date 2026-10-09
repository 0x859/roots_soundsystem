"""Rejestr parametrów: zakresy, normalizacja, powiadomienia, kompletność specyfikacji."""

import math

import pytest

from dsp.graph import all_specs
from engine.params import ParamSpec, ParamStore


def test_all_defaults_are_valid():
    for s in all_specs():
        assert s.clamp(s.default) == s.default, f"{s.key}: wartość domyślna poza zakresem/krokiem"
        if s.kind in ("float", "int"):
            assert s.min < s.max, s.key
            if s.scale == "log":
                assert s.min > 0, f"{s.key}: skala log wymaga min > 0"


@pytest.mark.parametrize("spec", [s for s in all_specs() if s.kind in ("float", "int")], ids=lambda s: s.key)
def test_norm_roundtrip(spec):
    for norm in (0.0, 0.25, 0.5, 0.75, 1.0):
        v = spec.from_norm(norm)
        tol = (spec.step or 1e-9) if spec.kind == "float" else 1.0
        span = spec.max - spec.min
        assert spec.from_norm(spec.to_norm(v)) == pytest.approx(v, abs=max(tol, 1e-9 * span))


def test_clamp_step_nan_and_kinds():
    s = ParamSpec("x", "X", 0.0, -10.0, 10.0, "dB", step=0.5)
    assert s.clamp(3.26) == 3.5
    assert s.clamp(99) == 10.0
    assert s.clamp(float("nan")) == 0.0
    c = ParamSpec("c", "C", 0, kind="choice", choices=("a", "b", "c"))
    assert c.clamp(7) == 2 and c.clamp(-3) == 0
    b = ParamSpec("b", "B", False, kind="bool")
    assert b.clamp(1) is True and b.from_norm(0.4) is False


def test_format_units():
    assert ParamSpec("f", "F", 1000.0, 20.0, 20000.0, "Hz").format(1500.0) == "1.50 kHz"
    assert ParamSpec("f", "F", 100.0, 20.0, 20000.0, "Hz").format(100.0) == "100 Hz"
    k = ParamSpec("g", "G", 0.0, -60.0, 6.0, "dB", kill_floor=-60.0)
    assert k.format(-60.0) == "KILL" and k.format(3.0) == "+3.0 dB"


def test_duplicate_key_rejected():
    with pytest.raises(ValueError):
        ParamStore([ParamSpec("a", "A", 0.0), ParamSpec("a", "A", 0.0)])


def test_listeners_prefix_and_change_only():
    store = ParamStore([ParamSpec("a.x", "X", 0.0), ParamSpec("b.y", "Y", 0.0)])
    got_all, got_a = [], []
    store.subscribe(lambda ch, src: got_all.append(ch))
    store.subscribe(lambda ch, src: got_a.append(ch), prefix="a.")
    store.set("b.y", 0.5)
    store.set("b.y", 0.5)  # bez zmiany – bez powiadomienia
    store.set("a.x", 0.2)
    store.set("nieznany", 1.0)  # ignorowany
    assert got_all == [{"b.y": 0.5}, {"a.x": 0.2}]
    assert got_a == [{"a.x": 0.2}]


def test_snapshot_skips_momentary_and_non_scene(store):
    snap = store.snapshot(scene_only=True)
    for k in snap:
        assert store.specs[k].scene and not store.specs[k].momentary
    assert len(store.snapshot(scene_only=False)) == len(store.specs)


def test_log_scale_midpoint_is_geometric():
    s = ParamSpec("f", "F", 100.0, 20.0, 20000.0, "Hz", scale="log")
    assert s.from_norm(0.5) == pytest.approx(math.sqrt(20.0 * 20000.0))
