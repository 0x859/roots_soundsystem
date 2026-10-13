"""TOR SYGNAŁU („dlaczego cisza?”): powody cięcia i bloki schematu z samych wartości parametrów."""

import pytest

from dsp.graph import DSP_SWITCHES
from dsp.isolator import BANDS, KILL_DB
from engine import signal_flow as sf


@pytest.fixture
def on(store):
    """Tor z włączonymi wszystkimi modułami (bez czystego startu)."""
    store.set_many({k: True for k in DSP_SWITCHES})
    return store


def _keys(flow, level=None):
    return [r["key"] for r in flow["reasons"] if level is None or r["level"] == level]


def _block(flow, bid):
    return next(b for b in flow["blocks"] if b["id"] == bid)


def test_switches_cover_every_dsp_module():
    assert set(sf.SWITCHES) == set(DSP_SWITCHES)


def test_clean_chain_has_no_reasons(on):
    flow = sf.analyze(on)
    assert flow["reasons"] == [] and flow["cut"] == {}
    assert [b["id"] for b in flow["blocks"]] == ["in", "preamp", "mix", "eq", "iso", "xo", "sim", "room", "out"]
    assert all(b["state"] == "on" for b in flow["blocks"])


def test_clean_start_modules_are_off_not_cut(store):
    store.set_many({k: False for k in DSP_SWITCHES})
    flow = sf.analyze(store)
    assert set(_keys(flow)) == set(DSP_SWITCHES) and set(_keys(flow, "off")) == set(DSP_SWITCHES)
    assert flow["cut"] == {}  # wyłączone moduły to przejście bez zmian, nie cisza
    states = {b["id"]: b["state"] for b in flow["blocks"]}
    assert states == {"in": "on", "preamp": "off", "mix": "on", "eq": "off", "iso": "off", "xo": "on",
                      "sim": "off", "room": "off", "out": "on"}
    store.set("iso.kill.sub", True)  # kill przy wyłączonym izolatorze nic nie tnie
    assert "iso.kill" not in _keys(sf.analyze(store))


@pytest.mark.parametrize(("running", "has_input", "key"), [(False, True, "stopped"), (False, False, "stopped"),
                                                         (True, False, "no_input")])
def test_engine_state(on, running, has_input, key):
    flow = sf.analyze(on, running=running, has_input=has_input)
    assert _keys(flow) == [key] and flow["cut"]["key"] == key and flow["cut"]["level"] == "silent"
    assert _block(flow, "in")["state"] == "cut"


@pytest.mark.parametrize(("values", "key", "level", "target", "block"), [
    ({"out.mute": True}, "out.mute", "silent", "out.mute", "out"),
    ({"out.master": -60.0}, "out.master", "silent", "out.master", "out"),
    ({"preamp.cut": True}, "preamp.cut", "music", "preamp.cut", "preamp"),
    ({"out.fx_panic": True}, "out.fx_panic", "partial", "out.fx_panic", "mix"),
    ({"iso.kill.bass": True}, "iso.kill", "partial", "iso.kill.bass", "iso"),
    ({"iso.g.top": KILL_DB}, "iso.kill", "partial", "iso.g.top", "iso"),
    ({"xo.mute.top": True}, "xo.mute", "partial", "xo.mute.top", "xo"),
    ({"mic.talkover": True}, "mic.talkover", "partial", "mic.talkover", "mix"),
    ({"echo.enabled": False}, "echo.enabled", "off", "echo.enabled", "mix"),
])
def test_each_reason(on, values, key, level, target, block):
    on.set_many(values)
    flow = sf.analyze(on)
    assert _keys(flow) == [key]
    r = flow["reasons"][0]
    assert (r["level"], r["target"], r["block"]) == (level, target, block) and r["text"]
    assert flow["cut"] == (r if level in sf.CUTS else {})
    if level in sf.CUTS or level == "partial":
        assert _block(flow, block)["state"] in ("cut", "partial") or block == "mix"


def test_full_cuts(on):
    on.set_many({f"iso.kill.{b}": True for b in BANDS})
    flow = sf.analyze(on)
    assert flow["cut"]["key"] == "iso.kill" and flow["cut"]["level"] == "silent"  # izolator na sumie
    assert _block(flow, "iso")["state"] == "cut" and _block(flow, "iso")["note"] == "SUMA"
    on.set("iso.position", 1)  # przed efektami: muzyka ucięta, MC/syrena/ogony zostają
    flow = sf.analyze(on)
    assert flow["cut"]["level"] == "music"
    assert [b["id"] for b in flow["blocks"]][:3] == ["in", "preamp", "iso"]
    on.set_many({f"iso.kill.{b}": False for b in BANDS} | {"xo.ways": 0, "xo.mute.bass": True, "xo.mute.top": True,
                                                           "xo.mute.sub": False})
    flow = sf.analyze(on)
    assert flow["cut"]["key"] == "xo.mute" and _block(flow, "xo")["state"] == "cut"
    assert [i["label"] for i in _block(flow, "xo")["items"]] == ["B", "T"]  # tylko drogi bieżącego podziału


def test_priority_order(on):
    """Najpierw to, co wycisza wszystko, potem muzykę, na końcu częściowe i wyłączone moduły."""
    on.set_many({"preamp.cut": True, "out.mute": True, "iso.kill.sub": True, "eq.enabled": False})
    flow = sf.analyze(on, running=True, has_input=False)
    assert _keys(flow) == ["no_input", "out.mute", "preamp.cut", "iso.kill", "eq.enabled"]
    assert flow["cut"]["key"] == "no_input"
    assert _block(flow, "preamp")["state"] == "cut" and _block(flow, "preamp")["note"] == "DRY CUT"


def test_mic_without_input_and_talkover(on):
    on.set("mic.talkover", True)
    flow = sf.analyze(on, mic_input=False)
    assert _keys(flow) == ["mic.input"]  # talkover bez mikrofonu nie ścisza muzyki
    mic = next(i for i in _block(flow, "mix")["items"] if i["label"] == "MIC")
    assert mic["state"] == "off"
    on.set("mic.enabled", False)
    assert _keys(sf.analyze(on, mic_input=False)) == ["mic.enabled"]


def test_multi_mode_blocks(on):
    on.set_many({"xo.ways": 2, "xo.mute.mid": True, "sim.enabled": False, "room.enabled": False})
    cmap = {"sub": (0, -1), "bass": (1, -1), "mid": (2, -1), "top": (3, -1)}
    flow = sf.analyze(on, mode="multi", channel_map=cmap)
    ids = [b["id"] for b in flow["blocks"]]
    assert ids[-2:] == ["limits", "out"] and "sim" not in ids and "room" not in ids
    out = _block(flow, "out")
    assert out["label"] == "KANAŁY" and [i["label"] for i in out["items"]] == ["S 1", "B 2", "M 3", "T 4"]
    assert [i["state"] for i in out["items"]] == ["on", "on", "cut", "on"]
    assert _keys(flow) == ["xo.mute"]  # modele kolumn i miejsce nie grają w Multi – bez uwag
    assert flow["mode"] == "multi"
