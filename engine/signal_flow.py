"""TOR SYGNAŁU – „dlaczego cisza?”: powody cięcia i stan bloków schematu, bez Qt.

Wszystko wynika z wartości `ParamStore` i stanu silnika (gra / są dane z wejścia), bez nowych punktów
pomiaru w wątku audio. Kolejność bloków jak w `SignalChain._process_block`: muzyka → preamp →
(izolator przed efektami) → miks (mikrofon, syrena, powroty echa i sprężyny) → EQ12 → (izolator na
sumie) → zwrotnica → kolumny i miejsce (Symulacja) albo limitery i kanały (Multi) → wyjście.

Poziomy powodów (`LEVELS`): `silent` – z wyjścia nic nie wychodzi; `music` – muzyka nie dociera do
wyjścia (MC, syrena i ogony mogą grać); `partial` – ucięta część toru (pasmo, droga, efekty, MC);
`off` – moduł wyłączony (przejście bez zmian albo milczące źródło lub efekt).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dsp.crossover import WAY_LABELS, WAYS_BY_COUNT
from dsp.graph import OUT_PARAMS
from dsp.isolator import BANDS, KILL_DB

LEVELS = ("silent", "music", "partial", "off")
CUTS = ("silent", "music")  # cięcie całego toru muzyki → ostrzeżenie „CISZA” w nagłówku LIVE
MASTER_MIN_DB = next(s.min for s in OUT_PARAMS if s.key == "out.master")
BAND_SHORT = {"sub": "S", "bass": "B", "lowmid": "L", "highmid": "H", "top": "T"}
BAND_NAMES = {"sub": "SUB", "bass": "BASS", "lowmid": "L-MID", "highmid": "H-MID", "top": "TOP"}
# przełącznik modułu → (blok schematu, nazwa, opis po wyłączeniu); test pilnuje zgodności z DSP_SWITCHES
SWITCHES = {
    "preamp.enabled": ("preamp", "PREAMP", "PREAMP wyłączony – przejście bez zmian"),
    "mic.enabled": ("mix", "MIKROFON", "MIKROFON wyłączony"),
    "echo.enabled": ("mix", "ECHO", "ECHO wyłączone"),
    "spring.enabled": ("mix", "SPRĘŻYNA", "SPRĘŻYNA wyłączona"),
    "eq.enabled": ("eq", "EQ12", "EQ12 wyłączony – przejście bez zmian"),
    "iso.enabled": ("iso", "IZOLATOR", "IZOLATOR wyłączony – przejście bez zmian (kill nie działa)"),
    "sim.enabled": ("sim", "MODELE KOLUMN", "MODELE KOLUMN wyłączone – przejście bez zmian"),
    "room.enabled": ("room", "MIEJSCE", "MIEJSCE wyłączone – przejście bez zmian"),
}
SIM_ONLY = ("sim", "room")  # bloki tylko w trybie Symulacja


def active_ways(values: Mapping[str, Any]) -> tuple[str, ...]:
    """Drogi zwrotnicy w bieżącym ustawieniu `xo.ways` (2/3/4)."""
    return WAYS_BY_COUNT[(2, 3, 4)[int(values["xo.ways"])]]


def band_killed(values: Mapping[str, Any], band: str) -> bool:
    """Pasmo izolatora wycięte przyciskiem KILL albo suwakiem skręconym do KILL (jak `QmlParam.killed`)."""
    return bool(values[f"iso.kill.{band}"]) or float(values[f"iso.g.{band}"]) <= KILL_DB


def _reason(key: str, level: str, text: str, target: str, block: str, name: str = "") -> dict[str, str]:
    return {"key": key, "level": level, "text": text, "target": target, "block": block, "name": name}


def _block(bid: str, label: str, state: str, note: str = "", target: str = "",
           items: list[dict[str, str]] | None = None) -> dict[str, Any]:
    return {"id": bid, "label": label, "state": state, "note": note, "target": target, "items": items or []}


def analyze(values: Mapping[str, Any], *, running: bool = True, has_input: bool = True, mode: str = "sim",
            channel_map: Mapping[str, tuple[int, int]] | None = None, mic_input: bool = True) -> dict[str, Any]:
    """Powody ciszy i cięć (od najpoważniejszych) oraz bloki schematu toru.

    `values` – wartości parametrów (`ParamStore` albo słownik), `running` – silnik gra, `has_input` –
    są dane z wejścia muzyki, `mode` – "sim" | "multi", `channel_map` – drogi → kanały (Multi),
    `mic_input` – wybrano wejście mikrofonu. Wynik: {"reasons": [...], "blocks": [...], "cut": powód
    pierwszego cięcia całego toru albo {}, "mode": mode}.
    """
    v = values
    ways = active_ways(v)
    iso_on = bool(v["iso.enabled"])
    iso_pre = int(v["iso.position"]) == 1
    killed = [b for b in BANDS if iso_on and band_killed(v, b)]
    muted = [w for w in ways if v[f"xo.mute.{w}"]]
    mute = bool(v["out.mute"])
    master_min = float(v["out.master"]) <= MASTER_MIN_DB
    mic_on = bool(v["mic.enabled"])
    panic = bool(v["out.fx_panic"])
    cut = bool(v["preamp.cut"])

    reasons: list[dict[str, str]] = []
    add = reasons.append
    if not running:
        add(_reason("stopped", "silent", "Silnik zatrzymany – START", "", "in"))
    elif not has_input:
        add(_reason("no_input", "silent", "Brak danych z wejścia muzyki", "view:devices", "in"))
    if mute:
        add(_reason("out.mute", "silent", "MUTE wyjścia", "out.mute", "out"))
    if master_min:
        add(_reason("out.master", "silent", "MASTER na minimum", "out.master", "out"))
    if muted and len(muted) == len(ways):
        add(_reason("xo.mute", "silent", "Wszystkie drogi zwrotnicy wyciszone", f"xo.mute.{muted[0]}", "xo"))
    kill_target = ""
    if killed:
        b = killed[0]
        kill_target = f"iso.kill.{b}" if v[f"iso.kill.{b}"] else f"iso.g.{b}"
    if len(killed) == len(BANDS):
        if iso_pre:
            add(_reason("iso.kill", "music", "IZOLATOR przed efektami: wszystkie pasma KILL", kill_target, "iso"))
        else:
            add(_reason("iso.kill", "silent", "IZOLATOR: wszystkie pasma KILL", kill_target, "iso"))
    if cut:
        add(_reason("preamp.cut", "music", "DRY CUT trzymany", "preamp.cut", "preamp"))
    if panic:
        add(_reason("out.fx_panic", "partial", "FX PANIC – echo i sprężyna wyciszone", "out.fx_panic", "mix"))
    if killed and len(killed) < len(BANDS):
        names = ", ".join(BAND_NAMES[b] for b in killed)
        add(_reason("iso.kill", "partial", f"IZOLATOR: KILL {names}", kill_target, "iso"))
    if muted and len(muted) < len(ways):
        names = ", ".join(WAY_LABELS[w].upper() for w in muted)
        add(_reason("xo.mute", "partial", f"ZWROTNICA: wyciszona droga {names}", f"xo.mute.{muted[0]}", "xo"))
    if mic_on and not mic_input:
        add(_reason("mic.input", "partial", "MIKROFON bez wejścia – wybierz je w AUDIO", "view:devices", "mix"))
    if mic_on and mic_input and v["mic.talkover"]:
        add(_reason("mic.talkover", "partial", "TALKOVER – muzyka ściszana pod głos MC", "mic.talkover", "mix"))
    for key, (block, name, text) in SWITCHES.items():
        if not v[key] and not (mode == "multi" and block in SIM_ONLY):
            add(_reason(key, "off", text, key, block, name))

    def state(enabled: bool) -> str:
        return "on" if enabled else "off"

    blocks: list[dict[str, Any]] = []
    in_note = "STOP" if not running else ("BRAK WEJŚCIA" if not has_input else "")
    blocks.append(_block("in", "MUZYKA", "cut" if in_note else "on", in_note, "view:devices"))
    blocks.append(_block("preamp", "PREAMP", "cut" if cut else state(bool(v["preamp.enabled"])),
                         "DRY CUT" if cut else "", "preamp.cut" if cut else "preamp.enabled"))
    if iso_on:
        iso_state = "cut" if len(killed) == len(BANDS) else ("partial" if killed else "on")
    else:
        iso_state = "off"
    iso = _block("iso", "IZOLATOR", iso_state, "PRZED FX" if iso_pre else "SUMA", kill_target or "iso.enabled",
                 [{"label": BAND_SHORT[b], "state": ("cut" if b in killed else "on") if iso_on else "off",
                   "target": f"iso.kill.{b}"} for b in BANDS])
    if iso_pre:
        blocks.append(iso)
    mic_state = "off" if not mic_on or not mic_input else "on"
    fx_items = [
        {"label": "MIC", "kind": "in", "state": mic_state, "target": "mic.enabled"},
        {"label": "SYRENA", "kind": "in", "state": "on", "target": "siren.trigger"},
        {"label": "ECHO", "kind": "fx", "state": "cut" if panic else state(bool(v["echo.enabled"])),
         "target": "out.fx_panic" if panic else "echo.enabled"},
        {"label": "SPRĘŻYNA", "kind": "fx", "state": "cut" if panic else state(bool(v["spring.enabled"])),
         "target": "out.fx_panic" if panic else "spring.enabled"},
    ]
    blocks.append(_block("mix", "MIKS", "on", "PANIC" if panic else "", "out.fx_panic" if panic else "mic.level",
                         fx_items))
    blocks.append(_block("eq", "EQ12", state(bool(v["eq.enabled"])), "", "eq.enabled"))
    if not iso_pre:
        blocks.append(iso)
    xo_state = "cut" if muted and len(muted) == len(ways) else ("partial" if muted else "on")
    blocks.append(_block("xo", "ZWROTNICA", xo_state, f"{len(ways)} DROGI", f"xo.mute.{muted[0]}" if muted else "xo.ways",
                         [{"label": WAY_LABELS[w][0], "state": "cut" if w in muted else "on", "target": f"xo.mute.{w}"}
                          for w in ways]))
    out_note = "MUTE" if mute else ("MASTER MIN" if master_min else "")
    out_target = "out.mute" if mute else "out.master"
    if mode == "multi":
        blocks.append(_block("limits", "LIMITERY", "on", "", "out.limit"))
        cmap = channel_map or {}
        chans = []
        for w in ways:
            ch = [c + 1 for c in cmap.get(w, (-1, -1)) if c >= 0]
            chans.append({"label": f"{WAY_LABELS[w][0]} {'/'.join(map(str, ch)) or '–'}",
                          "state": "cut" if (w in muted or not ch) else "on", "target": f"out.limit.{w}"})
        blocks.append(_block("out", "KANAŁY", "cut" if out_note else "on", out_note, out_target, chans))
    else:
        blocks.append(_block("sim", "KOLUMNY", state(bool(v["sim.enabled"])), "", "sim.enabled"))
        blocks.append(_block("room", "MIEJSCE", state(bool(v["room.enabled"])), "", "room.enabled"))
        blocks.append(_block("out", "WYJŚCIE", "cut" if out_note else "on", out_note, out_target))
    first = next((r for r in reasons if r["level"] in CUTS), None)
    return {"reasons": reasons, "blocks": blocks, "cut": dict(first) if first else {}, "mode": mode}
