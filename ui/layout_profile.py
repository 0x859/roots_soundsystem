"""Profil układu interfejsu QML: karty, kontrolki, pady, skróty i motyw jako dane JSON.

Profil jest czystym słownikiem (bez Qt), więc da się go testować, zapisywać i importować.
Cele kontrolek to klucze `ParamStore`, akcje `action:*` (jak w MIDI) albo widoki `view:*`.
"""

from __future__ import annotations

import copy
import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from engine.params import ParamSpec

VERSION = 1
DEFAULT_NAME = "Domyślny"

CONTROL_TYPES = ("knob", "fader", "button", "pad", "meter", "value")
SIZES = ("S", "M", "L")
VISIBILITY = ("live", "config", "both")
DENSITIES = ("compact", "normal", "touch")
KNOB_STYLES = ("arc", "pointer", "both")
PAD_POSITIONS = ("bottom", "top", "hidden")
NAMED_COLORS = ("auto", "accent", "fx", "kill", "blue", "cream")
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
# przełączniki działające „przy przytrzymaniu” (klawisz, pad), mimo że nie są chwilowe w scenie
HOLD_PREFIXES = ("iso.kill.",)

ACTIONS = {
    "action:tap": "TAP",
    "action:scene_prev": "SCENA ‹",
    "action:scene_next": "SCENA ›",
    "action:start_stop": "START / STOP",
    "action:dsp_toggle": "DSP: WSZYSTKO ON/OFF",
    "action:siren_mem:0": "SYRENA M1",
    "action:siren_mem:1": "SYRENA M2",
    "action:siren_mem:2": "SYRENA M3",
    "action:siren_mem:3": "SYRENA M4",
}
VIEWS = {
    "view:meters": "Mierniki dróg",
    "view:mic_meter": "Miernik mikrofonu",
    "view:siren_memories": "Pamięci syreny",
    "view:response": "Wykres: odpowiedź toru",
    "view:crossover": "Wykres: podział zwrotnicy",
    "view:spectrum": "Wykres: analizator widma",
    "view:devices": "Urządzenia, kanały i tryb wyjścia",
    "view:room_ir": "Własna IR miejsca (plik)",
    "view:eq_presets": "Presety EQ",
    "view:siren_presets": "Presety syreny (brzmienia)",
    "view:midi_map": "MIDI – mapa kontrolera",
}
MAX_SPAN = 4
MAX_ROWS = 3
MAX_COLS = 12
MIN_HEIGHT = 80  # wysokość karty w px przy skali 100% (0 = automatyczna)
MAX_HEIGHT = 2000

DEFAULT_THEME: dict[str, Any] = {
    "colors": {
        "bg": "#100F0D",
        "card": "#1A1916",
        "raised": "#23211D",
        "line": "#2F2C27",
        "text": "#EEE8DC",
        "muted": "#A39A8A",
        "accent": "#E3A52B",
        "fx": "#3FB6A8",
        "kill": "#B8362A",
        "blue": "#9BC9E0",
        "cream": "#D8D2C4",
    },
    "fonts": {"label": "Barlow Condensed", "value": "IBM Plex Mono"},
    "scale": 1.0,
    "density": "normal",
    "knobStyle": "both",
    "pads": {"position": "bottom", "height": 64},
    "minCardWidth": 236,
    "tiles": False,
    "inspectorWidth": 360,
    "autoScale": True,  # skala dopasowana do rozmiaru okna (mnożnik skali użytkownika)
    "autoExpand": True,  # karty same pokazują kontrolki spod „WIĘCEJ”, gdy mieszczą się bez przewijania
}


def _c(param: str, type_: str = "knob", size: str = "M", **extra: Any) -> dict[str, Any]:
    ctl: dict[str, Any] = {"param": param, "type": type_, "size": size}
    ctl.update(extra)
    return ctl


def _card(cid: str, title: str, controls: list[dict], **extra: Any) -> dict[str, Any]:
    card: dict[str, Any] = {
        "id": cid,
        "title": title,
        "color": "accent",
        "span": 1,
        "rows": 1,
        "height": 0,
        "cols": 0,
        "collapsed": False,
        "visible": "live",
        "more": 0,
        "toggle": "",
        "info": "",
        "controls": controls,
    }
    card.update(extra)
    return card


def default_profile() -> dict[str, Any]:
    """Układ zgodny z zatwierdzonymi makietami (LIVE + KONFIGURACJA)."""
    iso = [
        _c(f"iso.g.{b}", "fader", "M", label=lab, kill=f"iso.kill.{b}")
        for b, lab in (("sub", "SUB"), ("bass", "BASS"), ("lowmid", "L-MID"), ("highmid", "H-MID"), ("top", "TOP"))
    ]
    eq = [_c(f"eq.b{i}", "fader", "S") for i in range(12)]
    ways = ("sub", "bass", "mid", "top")
    cards = [
        _card("preamp", "PREAMP", [
            _c("preamp.hp", "knob", "L"),
            _c("preamp.lp", "knob", "L"),
            _c("preamp.drive", "knob", "S", color="kill"),
            _c("preamp.bass", "knob", "S"),
            _c("preamp.treble", "knob", "S"),
            _c("preamp.gain", "knob", "S"),
            _c("preamp.bias", "knob", "S"),
            _c("preamp.res", "knob", "S"),
            _c("preamp.echo_send", "knob", "S", label="Echo", color="fx"),
            _c("preamp.spring_send", "knob", "S", label="Spring", color="fx"),
            _c("preamp.master", "knob", "S"),
            _c("preamp.mono", "button", "S"),
        ], more=5, toggle="preamp.enabled"),
        _card("echo", "ECHO", [
            _c("echo.time", "knob", "L"),
            _c("echo.feedback", "knob", "L", label="Sprzężenie", color="kill"),
            _c("echo.swell", "button", "S", label="SWELL", color="kill"),
            _c("echo.lp", "knob", "S", label="LP"),
            _c("echo.wow", "knob", "S", label="Wow"),
            _c("echo.return", "knob", "S"),
            _c("echo.sync", "value", "M"),
            _c("echo.bpm", "knob", "S"),
            _c("echo.hp", "knob", "S", label="HP"),
            _c("echo.drive", "knob", "S", label="Taśma"),
            _c("echo.glide", "knob", "S"),
            _c("action:tap", "button", "S"),
        ], color="fx", more=6, toggle="echo.enabled", info="echo.sync"),
        _card("spring", "SPRĘŻYNA", [
            _c("spring.decay", "knob", "L"),
            _c("spring.tone", "knob", "S"),
            _c("spring.return", "knob", "S"),
        ], color="fx", toggle="spring.enabled"),
        _card("siren", "SYRENA", [
            _c("siren.pitch", "knob", "L", label="Pitch"),
            _c("siren.lfo_rate", "knob", "L", label="Tempo LFO"),
            _c("siren.lfo_depth", "knob", "S", label="Głęb."),
            _c("siren.sweep", "knob", "S"),
            _c("siren.level", "knob", "S"),
            _c("view:siren_memories", "meter", "M"),
            _c("view:siren_presets", "meter", "M"),
            _c("siren.wave", "value", "M"),
            _c("siren.lfo_shape", "value", "M"),
            _c("siren.sweep_time", "knob", "S"),
            _c("siren.release", "knob", "S"),
            _c("siren.echo_send", "knob", "S"),
        ], color="fx", more=7, info="siren.wave"),
        _card("iso", "IZOLATOR", iso, toggle="iso.enabled", info="iso.slope"),
        _card("mic", "MIKROFON", [
            _c("mic.level", "knob", "L"),
            _c("mic.talkover_depth", "knob", "L", label="Talkover"),
            _c("mic.gate", "knob", "S"),
            _c("mic.echo_send", "knob", "S", label="Echo", color="fx"),
            _c("view:mic_meter", "meter", "S"),
            _c("mic.talkover", "button", "L", color="fx"),
            _c("mic.throw", "button", "M", label="THROW MIC", color="fx"),
            _c("mic.gain", "knob", "S"),
            _c("mic.hp", "button", "S"),
            _c("mic.comp_thresh", "knob", "S"),
            _c("mic.comp_ratio", "knob", "S"),
            _c("mic.eq_low", "knob", "S"),
            _c("mic.eq_mid", "knob", "S"),
            _c("mic.eq_high", "knob", "S"),
        ], more=7, toggle="mic.enabled"),
        _card("out", "WYJŚCIE", [
            _c("view:meters", "meter", "L"),
            _c("out.master", "knob", "L"),
            _c("out.mute", "button", "L", color="kill"),
            _c("out.fx_panic", "button", "M", label="FX PANIC", color="kill"),
        ]),
        # --- KONFIGURACJA ---
        _card("devices", "URZĄDZENIA I KANAŁY", [_c("view:devices", "meter", "M")], span=2, visible="config"),
        _card("plots", "WYKRESY", [
            _c("view:response", "meter", "M"),
            _c("view:crossover", "meter", "M"),
            _c("view:spectrum", "meter", "M"),
        ], span=2, visible="config"),
        _card("xo", "ZWROTNICA", [
            _c("xo.ways", "value", "M"),
            _c("xo.slope", "value", "M"),
            _c("xo.f1", "knob", "M"),
            _c("xo.f2", "knob", "M"),
            _c("xo.f3", "knob", "M"),
            *[_c(f"xo.gain.{w}", "knob", "S") for w in ways],
            *[_c(f"xo.delay.{w}", "knob", "S") for w in ways],
            *[_c(f"xo.invert.{w}", "button", "M", label=f"Ø {w}") for w in ways],
            *[_c(f"xo.mute.{w}", "button", "M", label=f"Mute {w}", color="kill") for w in ways],
            _c("xo.subsonic", "button", "M"),
            _c("xo.subsonic_hz", "knob", "S"),
        ], span=2, visible="config"),
        _card("limits", "LIMITERY", [
            _c("out.limit", "knob", "M", label="Master"),
            *[_c(f"out.limit.{w}", "knob", "S", label=w.capitalize()) for w in ways],
        ], visible="config"),
        _card("eq", "EQ 12 PASM", [_c("view:eq_presets", "meter", "M"), _c("eq.preamp", "fader", "S", label="PRE"), *eq],
              span=2, visible="config", toggle="eq.enabled"),
        _card("room", "KOLUMNY I MIEJSCE", [
            _c("room.preset", "value", "M"),
            _c("room.mix", "knob", "M"),
            _c("room.size", "knob", "M"),
            *[_c(f"sim.cab.{w}", "value", "M") for w in ways],
            _c("sim.cab_drive", "knob", "S"),
            _c("sim.width", "knob", "S"),
            _c("sim.sub_delay", "knob", "S"),
            _c("sim.bassfeel", "knob", "S"),
            _c("sim.mono_bass", "button", "S"),
            _c("sim.enabled", "button", "S", label="Modele"),
            _c("view:room_ir", "meter", "M"),
        ], visible="config", toggle="room.enabled"),
        _card("midi", "MIDI – KONTROLER", [_c("view:midi_map", "meter", "M")], span=4, visible="config"),
        _card("iso_cfg", "IZOLATOR – PODZIAŁ", [
            _c("iso.position", "value", "M"),
            _c("iso.slope", "value", "M"),
            _c("iso.f1", "knob", "S", label="Sub/bass"),
            _c("iso.f2", "knob", "S", label="Bass/L-mid"),
            _c("iso.f3", "knob", "S", label="L/H-mid"),
            _c("iso.f4", "knob", "S", label="H-mid/top"),
        ], visible="config"),
    ]
    pads = [
        {"param": "iso.kill.sub", "label": "KILL SUB"},
        {"param": "iso.kill.bass", "label": "KILL BASS"},
        {"param": "iso.kill.lowmid", "label": "KILL L-MID"},
        {"param": "iso.kill.highmid", "label": "KILL H-MID"},
        {"param": "iso.kill.top", "label": "KILL TOP"},
        {"param": "echo.throw", "label": "THROW"},
        {"param": "preamp.cut", "label": "DRY CUT"},
        {"param": "siren.trigger", "label": "SYRENA"},
        {"param": "spring.crash", "label": "CRASH"},
        {"param": "action:tap", "label": "TAP"},
    ]
    shortcuts = {
        "1": "iso.kill.sub",
        "2": "iso.kill.bass",
        "3": "iso.kill.lowmid",
        "4": "iso.kill.highmid",
        "5": "iso.kill.top",
        "Space": "echo.throw",
        "C": "preamp.cut",
        "V": "mic.throw",
        "W": "echo.swell",
        "S": "siren.trigger",
        "D": "spring.crash",
        "T": "action:tap",
        "M": "out.mute",
        "P": "out.fx_panic",
        "F5": "action:siren_mem:0",
        "F6": "action:siren_mem:1",
        "F7": "action:siren_mem:2",
        "F8": "action:siren_mem:3",
    }
    return {
        "version": VERSION,
        "name": DEFAULT_NAME,
        "cards": cards,
        "pads": pads,
        "shortcuts": shortcuts,
        "theme": copy.deepcopy(DEFAULT_THEME),
    }


# --- walidacja ---
def is_hold(spec: ParamSpec) -> bool:
    """Przełącznik aktywny tylko przy przytrzymaniu klawisza lub padu (kill, throw, syrena, crash)."""
    return spec.kind == "bool" and (spec.momentary or spec.key.startswith(HOLD_PREFIXES))


def is_target(target: str, specs: dict[str, ParamSpec]) -> bool:
    return target in specs or target in ACTIONS or target in VIEWS


def target_label(target: str, specs: dict[str, ParamSpec]) -> str:
    if target in specs:
        return specs[target].label
    return ACTIONS.get(target) or VIEWS.get(target) or target


def allowed_types(target: str, specs: dict[str, ParamSpec]) -> tuple[str, ...]:
    """Typy kontrolek sensowne dla danego celu (pierwszy = domyślny)."""
    if target in VIEWS:
        return ("meter",)
    if target in ACTIONS:
        return ("button", "pad")
    spec = specs[target]
    if spec.kind == "bool":
        return ("button", "pad", "value")
    if spec.kind == "choice":
        return ("value", "knob", "fader")
    return ("knob", "fader", "value")


def _pick(value: Any, options: Iterable[str], default: str) -> str:
    return value if value in tuple(options) else default


def _color(value: Any, default: str = "auto") -> str:
    if isinstance(value, str) and (value in NAMED_COLORS or HEX_RE.match(value)):
        return value
    return default


def _num(value: Any, lo: float, hi: float, default: float) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    if v != v:  # NaN
        return default
    return max(lo, min(hi, v))


def _control(raw: Any, specs: dict[str, ParamSpec]) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    target = raw.get("param")
    if not isinstance(target, str) or not is_target(target, specs):
        return None
    types = allowed_types(target, specs)
    ctl: dict[str, Any] = {
        "param": target,
        "type": _pick(raw.get("type"), types, types[0]),
        "size": _pick(raw.get("size"), SIZES, "M"),
    }
    label = raw.get("label")
    if isinstance(label, str) and label.strip():
        ctl["label"] = label.strip()[:40]
    color = _color(raw.get("color"))
    if color != "auto":
        ctl["color"] = color
    kill = raw.get("kill")
    if isinstance(kill, str) and kill in specs and specs[kill].kind == "bool":
        ctl["kill"] = kill
    return ctl


def _height(value: Any) -> int:
    h = int(_num(value, 0, MAX_HEIGHT, 0))
    return 0 if h < MIN_HEIGHT else h


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return s or "karta"


def _card_norm(raw: Any, specs: dict[str, ParamSpec], used_ids: set[str]) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    title = str(raw.get("title") or "KARTA").strip()[:40] or "KARTA"
    cid = str(raw.get("id") or _slug(title))
    base, n = cid, 2
    while cid in used_ids:
        cid = f"{base}_{n}"
        n += 1
    used_ids.add(cid)
    controls = [c for c in (_control(x, specs) for x in raw.get("controls") or []) if c is not None]
    toggle = raw.get("toggle")
    info = raw.get("info")
    return {
        "id": cid,
        "title": title,
        "color": _color(raw.get("color"), "accent"),
        "span": int(_num(raw.get("span"), 1, MAX_SPAN, 1)),
        "rows": int(_num(raw.get("rows"), 1, MAX_ROWS, 1)),
        "height": _height(raw.get("height")),
        "cols": int(_num(raw.get("cols"), 0, MAX_COLS, 0)),
        "collapsed": raw.get("collapsed") is True,
        "visible": _pick(raw.get("visible"), VISIBILITY, "live"),
        "more": int(_num(raw.get("more"), 0, 99, 0)),
        "toggle": toggle if isinstance(toggle, str) and toggle in specs and specs[toggle].kind == "bool" else "",
        "info": info if isinstance(info, str) and info in specs else "",
        "controls": controls,
    }


def _theme_norm(raw: Any) -> dict[str, Any]:
    base = copy.deepcopy(DEFAULT_THEME)
    if not isinstance(raw, dict):
        return base
    colors = raw.get("colors")
    if isinstance(colors, dict):
        for k in base["colors"]:
            v = colors.get(k)
            if isinstance(v, str) and HEX_RE.match(v):
                base["colors"][k] = v.upper()
    fonts = raw.get("fonts")
    if isinstance(fonts, dict):
        for k in base["fonts"]:
            v = fonts.get(k)
            if isinstance(v, str) and v.strip():
                base["fonts"][k] = v.strip()[:64]
    base["scale"] = round(_num(raw.get("scale"), 0.8, 1.6, 1.0), 2)
    base["density"] = _pick(raw.get("density"), DENSITIES, "normal")
    base["knobStyle"] = _pick(raw.get("knobStyle"), KNOB_STYLES, "both")
    base["minCardWidth"] = int(_num(raw.get("minCardWidth"), 180, 480, 236))
    base["tiles"] = raw.get("tiles") is True
    base["autoScale"] = raw.get("autoScale") is not False
    base["autoExpand"] = raw.get("autoExpand") is not False
    base["inspectorWidth"] = int(_num(raw.get("inspectorWidth"), 280, 640, 360))
    pads = raw.get("pads")
    if isinstance(pads, dict):
        base["pads"]["position"] = _pick(pads.get("position"), PAD_POSITIONS, "bottom")
        base["pads"]["height"] = int(_num(pads.get("height"), 40, 120, 64))
    return base


def normalize_shortcut(key: Any) -> str:
    """Nazwa klawisza w postaci jak w QKeySequence: '1', 'S', 'Space', 'F5'."""
    if not isinstance(key, str):
        return ""
    k = key.strip()
    if not k:
        return ""
    low = k.lower()
    if low in ("space", "spacja", " "):
        return "Space"
    if re.fullmatch(r"f([1-9]|1[0-2])", low):
        return low.upper()
    if len(k) == 1 and k.isprintable():
        return k.upper()
    return ""


def normalize(raw: Any, specs: dict[str, ParamSpec]) -> dict[str, Any]:
    """Uzupełnia i czyści profil (nieznane parametry są pomijane, braki – z wartości domyślnych)."""
    if not isinstance(raw, dict):
        return normalize(default_profile(), specs)
    used: set[str] = set()
    cards = [c for c in (_card_norm(x, specs, used) for x in raw.get("cards") or []) if c is not None]
    pads = []
    for p in raw.get("pads") or []:
        if isinstance(p, dict) and isinstance(p.get("param"), str) and is_target(p["param"], specs) and p["param"] not in VIEWS:
            label = p.get("label")
            pads.append({
                "param": p["param"],
                "label": label.strip()[:24] if isinstance(label, str) and label.strip() else target_label(p["param"], specs).upper(),
            })
    shortcuts: dict[str, str] = {}
    raw_sc = raw.get("shortcuts")
    if isinstance(raw_sc, dict):
        for key, target in raw_sc.items():
            nk = normalize_shortcut(key)
            if nk and isinstance(target, str) and is_target(target, specs) and target not in VIEWS:
                shortcuts[nk] = target
    name = raw.get("name")
    return {
        "version": VERSION,
        "name": name.strip()[:60] if isinstance(name, str) and name.strip() else DEFAULT_NAME,
        "cards": cards,
        "pads": pads,
        "shortcuts": shortcuts,
        "theme": _theme_norm(raw.get("theme")),
    }


def shortcut_for(profile: dict[str, Any], target: str) -> str:
    return next((k for k, t in profile.get("shortcuts", {}).items() if t == target), "")


# --- pliki ---
def layouts_dir() -> Path:
    from presets.store import app_dir

    d = app_dir() / "layouts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", name).strip() or "uklad"


def list_profiles() -> list[str]:
    names = sorted(p.stem for p in layouts_dir().glob("*.json"))
    if DEFAULT_NAME not in names:
        names.insert(0, DEFAULT_NAME)
    return names


def load_profile(name: str, specs: dict[str, ParamSpec]) -> dict[str, Any]:
    path = layouts_dir() / f"{_safe(name)}.json"
    if not path.is_file():
        prof = normalize(default_profile(), specs)
        prof["name"] = name
        return prof
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raw = default_profile()
    prof = normalize(raw, specs)
    prof["name"] = name
    return prof


def save_profile(profile: dict[str, Any]) -> Path:
    path = layouts_dir() / f"{_safe(profile['name'])}.json"
    path.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def delete_profile(name: str) -> None:
    path = layouts_dir() / f"{_safe(name)}.json"
    if path.exists():
        path.unlink()


def export_profile(profile: dict[str, Any], path: str | Path) -> None:
    Path(path).write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")


def import_profile(path: str | Path, specs: dict[str, ParamSpec]) -> dict[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return normalize(raw, specs)
