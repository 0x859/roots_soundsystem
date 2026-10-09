"""Gotowe profile kontrolerów MIDI.

Identyfikatory elementów mają postać ``cc:<kanał>:<numer>`` lub ``note:<kanał>:<numer>``
(kanał liczony od 0, jak w mido). Cel to klucz parametru z ``ParamStore``
albo akcja ``action:<nazwa>`` (lista w ``ACTIONS``).
"""

from __future__ import annotations

from dataclasses import dataclass, field

ACTIONS = {
    "action:scene_prev": "Poprzednia scena",
    "action:scene_next": "Następna scena",
    "action:tap": "Tap tempo",
    "action:siren_mem_next": "Następna pamięć syreny",
    "action:siren_mem:0": "Pamięć syreny M1",
    "action:siren_mem:1": "Pamięć syreny M2",
    "action:siren_mem:2": "Pamięć syreny M3",
    "action:siren_mem:3": "Pamięć syreny M4",
    "action:start_stop": "Start / stop",
    "action:dsp_toggle": "DSP: wszystko wył. / przywróć",
}


@dataclass(frozen=True)
class Element:
    """Fizyczny element kontrolera na mapie (gałka, przycisk, suwak)."""

    id: str  # identyfikator komunikatu, np. "cc:0:16"
    kind: str  # "knob" | "button" | "fader"
    name: str = ""  # napis na sprzęcie, np. "MUTE"
    shift_id: str | None = None  # inny komunikat wysyłany przy trzymanym SHIFT (MIDImix: rząd Mute/Solo)
    led: bool = False


@dataclass(frozen=True)
class Strip:
    """Kolumna elementów kontrolera (kanał lub sekcja master), od góry do dołu."""

    name: str
    elements: tuple[Element, ...]


@dataclass
class MidiProfile:
    name: str
    port_match: tuple[str, ...]
    mapping: dict[str, str]
    shift_mapping: dict[str, str] = field(default_factory=dict)
    shift: str | None = None  # element trzymany jako SHIFT
    feedback: tuple[str, ...] = ()  # elementy z diodą (note-on 127/0)
    pickup: bool = True
    layout: tuple[Strip, ...] = ()  # układ fizyczny do podglądu mapy (pusty = tylko lista)

    def matches(self, port_name: str) -> bool:
        low = port_name.lower()
        return any(m in low for m in self.port_match)


# --- Akai MIDImix (ustawienia fabryczne, kanał 1) ---
_MIX_KNOBS = [(16, 17, 18), (20, 21, 22), (24, 25, 26), (28, 29, 30), (46, 47, 48), (50, 51, 52), (54, 55, 56), (58, 59, 60)]
_MIX_FADERS = [19, 23, 27, 31, 49, 53, 57, 61]
_MIX_MASTER = 62
_MIX_MUTE = [1, 4, 7, 10, 13, 16, 19, 22]
_MIX_SOLO = [2, 5, 8, 11, 14, 17, 20, 23]  # rząd Mute przy trzymanym SOLO
_MIX_REC = [3, 6, 9, 12, 15, 18, 21, 24]
_MIX_BANK_LEFT, _MIX_BANK_RIGHT, _MIX_SOLO_BTN = 25, 26, 27


def _cc(n: int) -> str:
    return f"cc:0:{n}"


def _note(n: int) -> str:
    return f"note:0:{n}"


def _midimix() -> MidiProfile:
    knobs = [
        ("preamp.hp", "preamp.lp", "preamp.res"),
        ("preamp.drive", "preamp.bass", "preamp.treble"),
        ("echo.time", "echo.feedback", "echo.lp"),
        ("preamp.echo_send", "preamp.spring_send", "spring.decay"),
        ("siren.pitch", "siren.lfo_rate", "siren.lfo_depth"),
        ("mic.talkover_depth", "mic.gate", "mic.echo_send"),
        ("room.mix", "sim.bassfeel", "sim.width"),
        ("echo.wow", "echo.glide", "echo.drive"),
    ]
    shift_knobs = [
        ("preamp.gain", "preamp.bias", "preamp.master"),
        ("iso.f1", "iso.f2", "iso.f3"),
        ("echo.hp", "echo.bpm", "echo.sync"),
        ("spring.tone", "iso.f4", "room.size"),
        ("siren.sweep", "siren.sweep_time", "siren.release"),
        ("mic.gain", "mic.comp_thresh", "mic.eq_mid"),
        ("sim.cab_drive", "sim.sub_delay", "room.preset"),
        ("out.limit", "xo.subsonic_hz", "eq.preamp"),
    ]
    faders = [
        "iso.g.sub", "iso.g.bass", "iso.g.lowmid", "iso.g.highmid", "iso.g.top",
        "echo.return", "spring.return", "mic.level",
    ]
    mutes = [
        "iso.kill.sub", "iso.kill.bass", "iso.kill.lowmid", "iso.kill.highmid", "iso.kill.top",
        "echo.enabled", "spring.enabled", "mic.enabled",
    ]
    recs = [
        "echo.throw", "siren.trigger", "spring.crash", "action:tap",
        "mic.talkover", "preamp.cut", "action:siren_mem_next", "out.mute",
    ]
    # SOLO + Rec Arm (bez wpisu = jak bez SOLO): gesty dubowe i MONO przeniesione spod Rec Arm 6
    shift_recs = {0: "out.fx_panic", 1: "mic.throw", 2: "echo.swell", 5: "preamp.mono"}
    mapping: dict[str, str] = {}
    shift_mapping: dict[str, str] = {}
    for ccs, keys, skeys in zip(_MIX_KNOBS, knobs, shift_knobs, strict=True):
        for cc, key, skey in zip(ccs, keys, skeys, strict=True):
            mapping[_cc(cc)] = key
            shift_mapping[_cc(cc)] = skey
    for cc, key in zip(_MIX_FADERS, faders, strict=True):
        mapping[_cc(cc)] = key
    mapping[_cc(_MIX_MASTER)] = "out.master"
    for n, key in zip(_MIX_MUTE, mutes, strict=True):
        mapping[_note(n)] = key
    # przy trzymanym SOLO sprzęt wysyła inne nuty – niech działają jak rząd Mute
    for n, key in zip(_MIX_SOLO, mutes, strict=True):
        shift_mapping[_note(n)] = key
    for n, key in zip(_MIX_REC, recs, strict=True):
        mapping[_note(n)] = key
    for i, key in shift_recs.items():
        shift_mapping[_note(_MIX_REC[i])] = key
    mapping[_note(_MIX_BANK_LEFT)] = "action:scene_prev"
    mapping[_note(_MIX_BANK_RIGHT)] = "action:scene_next"
    return MidiProfile(
        name="Akai MIDImix",
        port_match=("midi mix", "midimix"),
        mapping=mapping,
        shift_mapping=shift_mapping,
        shift=_note(_MIX_SOLO_BTN),
        feedback=tuple(_note(n) for n in _MIX_MUTE + _MIX_REC),
        layout=_midimix_layout(),
    )


def _midimix_layout() -> tuple[Strip, ...]:
    strips = []
    for i in range(8):
        strips.append(Strip(str(i + 1), (
            *(Element(_cc(c), "knob") for c in _MIX_KNOBS[i]),
            Element(_note(_MIX_MUTE[i]), "button", "MUTE", shift_id=_note(_MIX_SOLO[i]), led=True),
            Element(_note(_MIX_REC[i]), "button", "REC ARM", led=True),
            Element(_cc(_MIX_FADERS[i]), "fader"),
        )))
    strips.append(Strip("MASTER", (
        Element(_note(_MIX_BANK_LEFT), "button", "BANK ◀"),
        Element(_note(_MIX_BANK_RIGHT), "button", "BANK ▶"),
        Element(_note(_MIX_SOLO_BTN), "button", "SOLO"),
        Element(_cc(_MIX_MASTER), "fader"),
    )))
    return tuple(strips)


PROFILES: dict[str, MidiProfile] = {p.name: p for p in (_midimix(),)}


def profile_for_port(port_name: str) -> MidiProfile | None:
    for p in PROFILES.values():
        if p.matches(port_name):
            return p
    return None
