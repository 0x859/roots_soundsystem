import copy

import pytest

from ui import layout_profile as lp


@pytest.fixture
def appdata(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    return tmp_path


def test_default_profile_is_valid_and_stable(store):
    raw = lp.default_profile()
    prof = lp.normalize(raw, store.specs)
    # nic nie zostało odrzucone przy walidacji
    assert [len(c["controls"]) for c in prof["cards"]] == [len(c["controls"]) for c in raw["cards"]]
    assert len(prof["pads"]) == len(raw["pads"])
    assert prof["shortcuts"] == raw["shortcuts"]
    # normalizacja jest idempotentna
    assert lp.normalize(copy.deepcopy(prof), store.specs) == prof
    ids = [c["id"] for c in prof["cards"]]
    assert len(ids) == len(set(ids))


def test_default_profile_covers_live_and_config(store):
    prof = lp.normalize(lp.default_profile(), store.specs)
    live = [c["title"] for c in prof["cards"] if c["visible"] in ("live", "both")]
    config = [c["title"] for c in prof["cards"] if c["visible"] in ("config", "both")]
    assert {"PREAMP", "ECHO", "SPRĘŻYNA", "SYRENA", "IZOLATOR", "MIKROFON", "WYJŚCIE"} <= set(live)
    assert {"URZĄDZENIA I KANAŁY", "WYKRESY", "ZWROTNICA", "EQ 12 PASM"} <= set(config)
    plots = next(c for c in prof["cards"] if c["id"] == "plots")
    assert plots["span"] == 2 and plots["rows"] == 1
    pads = [p["param"] for p in prof["pads"]]
    assert pads[:5] == [f"iso.kill.{b}" for b in ("sub", "bass", "lowmid", "highmid", "top")]
    assert prof["shortcuts"]["Space"] == "echo.throw"


def test_normalize_drops_invalid_and_coerces(store):
    raw = {
        "name": "  Test  ",
        "cards": [
            {"title": "X", "span": 9, "rows": 0, "height": 40, "cols": 40, "collapsed": "tak", "visible": "nowhere", "color": "zielony", "controls": [
                {"param": "nie.istnieje"},
                {"param": "echo.time", "type": "pad", "size": "XL", "color": "#12ab34"},
                {"param": "echo.throw", "type": "knob"},
                {"param": "iso.g.sub", "type": "fader", "kill": "echo.time"},
                {"param": "view:meters", "type": "knob"},
                "śmieci",
            ]},
            {"title": "X", "controls": []},
            42,
        ],
        "pads": [{"param": "view:meters"}, {"param": "echo.throw"}, {"param": "zly"}],
        "shortcuts": {"spacja": "echo.throw", "f5": "action:tap", "Ctrl+Q": "out.mute", "x": "zly.cel"},
        "theme": {"scale": 9, "density": "ogromna", "colors": {"accent": "#abcdef", "bg": "red"}, "pads": {"height": 5}},
    }
    prof = lp.normalize(raw, store.specs)
    assert prof["name"] == "Test"
    card = prof["cards"][0]
    assert card["span"] == lp.MAX_SPAN and card["visible"] == "live" and card["color"] == "accent"
    assert card["rows"] == 1 and card["cols"] == lp.MAX_COLS and card["collapsed"] is False
    assert card["height"] == 0
    ctls = card["controls"]
    assert [c["param"] for c in ctls] == ["echo.time", "echo.throw", "iso.g.sub", "view:meters"]
    assert ctls[0] == {"param": "echo.time", "type": "knob", "size": "M", "color": "#12ab34"}
    assert ctls[1]["type"] == "button"  # bool nie może być gałką
    assert "kill" not in ctls[2]  # kill musi być przełącznikiem
    assert ctls[3]["type"] == "meter"
    assert prof["cards"][1]["id"] != card["id"]  # unikalne identyfikatory
    assert prof["pads"] == [{"param": "echo.throw", "label": "THROW"}]
    assert prof["shortcuts"] == {"Space": "echo.throw", "F5": "action:tap"}
    th = prof["theme"]
    assert th["scale"] == 1.6 and th["density"] == "normal" and th["pads"]["height"] == 40
    assert th["tiles"] is False and th["inspectorWidth"] == 360
    assert th["colors"]["accent"] == "#ABCDEF" and th["colors"]["bg"] == lp.DEFAULT_THEME["colors"]["bg"]


def test_normalize_garbage_gives_default(store):
    assert lp.normalize(None, store.specs) == lp.normalize(lp.default_profile(), store.specs)


def test_allowed_types_and_hold(store):
    s = store.specs
    assert lp.allowed_types("echo.time", s)[0] == "knob"
    assert lp.allowed_types("echo.sync", s)[0] == "value"
    assert lp.allowed_types("out.mute", s)[0] == "button"
    assert lp.allowed_types("action:tap", s) == ("button", "pad")
    assert lp.allowed_types("view:meters", s) == ("meter",)
    assert lp.is_hold(s["echo.throw"]) and lp.is_hold(s["iso.kill.sub"])
    assert not lp.is_hold(s["out.mute"]) and not lp.is_hold(s["echo.time"])


def test_shortcut_names():
    assert lp.normalize_shortcut(" space ") == "Space"
    assert lp.normalize_shortcut("f12") == "F12"
    assert lp.normalize_shortcut("m") == "M"
    assert lp.normalize_shortcut("F13") == ""
    assert lp.normalize_shortcut("Ctrl+M") == ""
    assert lp.normalize_shortcut(None) == ""


def test_save_load_list_delete(store, appdata):
    assert lp.list_profiles() == [lp.DEFAULT_NAME]
    prof = lp.normalize(lp.default_profile(), store.specs)
    prof["name"] = "Sesja: plener"
    prof["theme"]["scale"] = 1.25
    path = lp.save_profile(prof)
    assert path.parent == appdata / "RootsSoundsystem" / "layouts"
    assert "Sesja_ plener.json" == path.name
    assert "Sesja_ plener" in lp.list_profiles()
    loaded = lp.load_profile("Sesja: plener", store.specs)
    assert loaded == prof
    lp.delete_profile("Sesja: plener")
    assert lp.load_profile("Sesja: plener", store.specs)["theme"]["scale"] == 1.0


def test_load_corrupted_file_falls_back(store, appdata):
    d = lp.layouts_dir()
    (d / "Zepsuty.json").write_text("{ to nie json", encoding="utf-8")
    prof = lp.load_profile("Zepsuty", store.specs)
    assert prof["name"] == "Zepsuty" and prof["cards"]


def test_export_import(store, tmp_path):
    prof = lp.normalize(lp.default_profile(), store.specs)
    prof["cards"] = prof["cards"][:2]
    out = tmp_path / "uklad.json"
    lp.export_profile(prof, out)
    back = lp.import_profile(out, store.specs)
    assert back["cards"] == prof["cards"]


def test_card_height(store):
    raw = {"cards": [{"title": "A", "height": 300}, {"title": "B", "height": 99999}, {"title": "C", "height": "x"}]}
    prof = lp.normalize(raw, store.specs)
    assert [c["height"] for c in prof["cards"]] == [300, lp.MAX_HEIGHT, 0]
