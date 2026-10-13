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
    assert lp.list_profiles() == list(lp.TEMPLATES)  # gotowe układy są zawsze na liście
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


def _targets(prof):
    out = {ctl["param"] for card in prof["cards"] for ctl in card["controls"]}
    return out | {p["param"] for p in prof["pads"]} | set(prof["shortcuts"].values())


def _strip(prof, targets):
    """Profil bez podanych celów, jak zapisany przed ich dodaniem do układu domyślnego."""
    old = copy.deepcopy(prof)
    for card in old["cards"]:
        kept = [c for c in card["controls"] if c["param"] not in targets]
        visible = card["controls"][: card["more"]]
        if card["more"]:
            card["more"] -= sum(1 for c in visible if c["param"] in targets)
        card["controls"] = kept
    old["pads"] = [p for p in old["pads"] if p["param"] not in targets]
    old["shortcuts"] = {k: t for k, t in old["shortcuts"].items() if t not in targets}
    return old


def test_old_profile_gets_controls_added_to_default(store):
    """Zapisany wcześniej profil dostaje nowe kontrolki układu domyślnego – w tym samym miejscu."""
    default = lp.normalize(lp.default_profile(), store.specs)
    added = {t for v in lp.ADDED for t in lp.ADDED[v]}
    old = _strip(default, added)
    old["version"] = 1
    assert not added & _targets(old)
    assert lp.normalize(old, store.specs) == default


def test_migration_keeps_user_choices(store):
    default = lp.normalize(lp.default_profile(), store.specs)
    old = _strip(default, set(lp.ADDED[2]))
    old["version"] = 1
    old["cards"] = [c for c in old["cards"] if c["id"] != "out"]  # karta usunięta przez użytkownika
    old["cards"][0]["controls"].append({"param": "mic.throw", "type": "button", "size": "S"})
    old["shortcuts"]["C"] = "out.mute"  # klawisz zajęty przez użytkownika
    prof = lp.normalize(old, store.specs)
    where = [(c["id"], x["param"]) for c in prof["cards"] for x in c["controls"]]
    assert where.count(("preamp", "mic.throw")) == 1 and ("mic", "mic.throw") not in where  # bez duplikatu
    assert ("out", "out.fx_panic") in where  # brakująca karta wraca tylko z nową kontrolką
    assert [x["param"] for x in next(c for c in prof["cards"] if c["id"] == "out")["controls"]] == ["out.fx_panic"]
    assert prof["shortcuts"]["C"] == "out.mute" and "preamp.cut" not in prof["shortcuts"].values()
    assert prof["shortcuts"]["P"] == "out.fx_panic"
    # w aktualnej wersji usunięta kontrolka nie wraca
    cur = _strip(default, {"echo.swell"})
    assert "echo.swell" not in _targets(lp.normalize(cur, store.specs))


def test_new_default_controls_are_registered(store):
    """Nowa kontrolka w układzie domyślnym wymaga wpisu w `lp.ADDED` i podbicia `lp.VERSION`
    (inaczej nie trafi do profili zapisanych wcześniej) – potem zaktualizuj tę liczbę."""
    default = lp.normalize(lp.default_profile(), store.specs)
    assert max(lp.ADDED) == lp.VERSION
    assert {t for v in lp.ADDED for t in lp.ADDED[v]} <= _targets(default)
    assert len(_targets(default)) == 144


def test_migration_v3_adds_signal_flow_card(store):
    """Profil v3 dostaje kartę TOR SYGNAŁU na KONFIGURACJI w miejscu z układu domyślnego (przed URZĄDZENIAMI);
    karty LIVE i ustawienia użytkownika zostają bez zmian, usunięta w v4 karta nie wraca."""
    default = lp.normalize(lp.default_profile(), store.specs)
    card = next(c for c in default["cards"] if c["id"] == "signal_flow")
    assert card["visible"] == "config" and card["span"] == 4 and card["title"] == "TOR SYGNAŁU"
    old = copy.deepcopy(default)
    old["cards"] = [c for c in old["cards"] if c["id"] != "signal_flow"]
    old["cards"][0]["title"] = "MÓJ PREAMP"
    old["version"] = 3
    prof = lp.normalize(old, store.specs)
    assert prof == default | {"cards": [dict(c, title="MÓJ PREAMP") if c["id"] == "preamp" else c
                                        for c in default["cards"]]}
    ids = [c["id"] for c in prof["cards"]]
    assert ids.index("signal_flow") == ids.index("devices") - 1
    cur = copy.deepcopy(default)
    cur["cards"] = [c for c in cur["cards"] if c["id"] != "signal_flow"]
    assert "view:signal_flow" not in _targets(lp.normalize(cur, store.specs))


@pytest.mark.parametrize("name", [lp.COMPACT_NAME, lp.COMPACT_FX_NAME])
def test_migration_v3_compact_copy_keeps_live(store, name):
    """Zapisana kopia szablonu kompaktowego z v3: TOR SYGNAŁU tylko na KONFIGURACJI, karty LIVE bez zmian."""
    fresh = lp.normalize(lp.template_profile(name), store.specs)
    assert any(c["id"] == "signal_flow" and c["visible"] == "config" for c in fresh["cards"])
    old = copy.deepcopy(fresh)
    old["cards"] = [c for c in old["cards"] if c["id"] != "signal_flow"]
    old["version"] = 3
    prof = lp.normalize(old, store.specs)
    live = [c for c in prof["cards"] if c["visible"] != "config"]
    assert live == [c for c in fresh["cards"] if c["visible"] != "config"]
    assert [c["id"] for c in prof["cards"]] == [c["id"] for c in fresh["cards"]]


def test_param_groups_cover_every_param(store):
    groups = lp.param_groups(store.specs)
    keys = [k for _g, _t, ks in groups for k in ks]
    assert sorted(keys) == sorted(store.specs) and len(keys) == len(set(keys))
    titles = {g: t for g, t, _ks in groups}
    assert titles["preamp"] == "PREAMP" and titles["echo"] == "ECHO" and titles["xo"] == "ZWROTNICA"
    assert all(t for t in titles.values())
    assert groups[0][0] == "preamp"  # kolejność jak w torze (`all_specs`)
    # widok wszystkich parametrów jest w konfiguracji układu domyślnego
    default = lp.normalize(lp.default_profile(), store.specs)
    card = next(c for c in default["cards"] if any(x["param"] == "view:all_params" for x in c["controls"]))
    assert card["visible"] == "config"


def test_card_height(store):
    raw = {"cards": [{"title": "A", "height": 300}, {"title": "B", "height": 99999}, {"title": "C", "height": "x"}]}
    prof = lp.normalize(raw, store.specs)
    assert [c["height"] for c in prof["cards"]] == [300, lp.MAX_HEIGHT, 0]


# --- gotowe układy (szablony) ---
LIVE_MUST_HAVE = ("out.master", "out.mute", "out.fx_panic", "echo.feedback", "echo.time", "spring.decay",
                  "siren.pitch", "mic.level", "mic.talkover", "preamp.hp", "preamp.lp")


@pytest.mark.parametrize("name", list(lp.TEMPLATES))
def test_templates_normalize_without_loss(store, name):
    raw = lp.template_profile(name)
    prof = lp.normalize(raw, store.specs)
    assert prof["name"] == name
    assert lp.normalize(prof, store.specs) == prof  # stabilny po zapisie i wczytaniu
    # żadna kontrolka, pad ani skrót nie wypada przy walidacji (tylko istniejące cele i typy)
    assert [len(c["controls"]) for c in prof["cards"]] == [len(c["controls"]) for c in raw["cards"]]
    for rc, nc in zip(raw["cards"], prof["cards"], strict=True):
        assert [c["param"] for c in nc["controls"]] == [c["param"] for c in rc["controls"]]
        assert [c["type"] for c in nc["controls"]] == [c["type"] for c in rc["controls"]]
        assert [c["size"] for c in nc["controls"]] == [c["size"] for c in rc["controls"]]
        for key in ("span", "cols", "more", "toggle", "info", "visible"):
            assert nc[key] == rc[key], (rc["title"], key)
    assert len(prof["pads"]) == len(raw["pads"]) and len(prof["shortcuts"]) == len(raw["shortcuts"])
    assert prof["theme"] == lp.normalize({"theme": raw["theme"]}, store.specs)["theme"]
    assert len({c["id"] for c in prof["cards"]}) == len(prof["cards"])


@pytest.mark.parametrize("name", [lp.COMPACT_NAME, lp.COMPACT_FX_NAME])
def test_compact_templates_keep_live_functions(store, name):
    prof = lp.normalize(lp.template_profile(name), store.specs)
    default = lp.normalize(lp.default_profile(), store.specs)
    live = [c for c in prof["cards"] if c["visible"] in ("live", "both")]
    targets = {x["param"] for c in live for x in c["controls"]}
    kills = {x.get("kill") for c in live for x in c["controls"]}
    assert set(LIVE_MUST_HAVE) <= targets
    assert {f"iso.kill.{b}" for b in ("sub", "bass", "lowmid", "highmid", "top")} <= kills  # kill izolatora
    assert prof["pads"] == default["pads"] and prof["shortcuts"] == default["shortcuts"]
    # kompaktowy: mniej kart LIVE niż domyślny (efekty w jednej karcie); KONFIGURACJA bez zmian w obu
    if name == lp.COMPACT_NAME:
        assert len(live) < len([c for c in default["cards"] if c["visible"] == "live"])
    assert [c for c in prof["cards"] if c["visible"] == "config"] == [c for c in default["cards"] if c["visible"] == "config"]
    theme = prof["theme"]
    assert theme["density"] == "compact" and theme["scale"] < 1.0
    assert theme["minCardWidth"] < lp.DEFAULT_THEME["minCardWidth"]
    assert theme["pads"]["height"] < lp.DEFAULT_THEME["pads"]["height"]


def test_templates_files(store, appdata):
    """Szablon bez pliku = świeży szablon; zapisana kopia ma pierwszeństwo, po usunięciu wraca szablon."""
    fresh = lp.load_profile(lp.COMPACT_NAME, store.specs)
    assert fresh == lp.normalize(lp.template_profile(lp.COMPACT_NAME), store.specs)
    assert lp.is_template(lp.COMPACT_FX_NAME) and not lp.is_template("Plener")
    edited = dict(fresh, cards=fresh["cards"][:3])
    lp.save_profile(edited)
    assert lp.list_profiles() == list(lp.TEMPLATES)  # bez duplikatu zapisanego szablonu
    assert len(lp.load_profile(lp.COMPACT_NAME, store.specs)["cards"]) == 3
    lp.delete_profile(lp.COMPACT_NAME)
    assert lp.load_profile(lp.COMPACT_NAME, store.specs) == fresh
    # nowy profil bez pliku i zepsuty plik szablonu – układ domyślny / szablon
    assert lp.load_profile("Nowy", store.specs)["cards"] == lp.normalize(lp.default_profile(), store.specs)["cards"]
    (lp.layouts_dir() / f"{lp.COMPACT_FX_NAME}.json").write_text("{ zepsuty", encoding="utf-8")
    assert lp.load_profile(lp.COMPACT_FX_NAME, store.specs)["cards"] == lp.normalize(
        lp.template_profile(lp.COMPACT_FX_NAME), store.specs)["cards"]
