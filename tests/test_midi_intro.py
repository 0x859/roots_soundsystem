"""Animacja powitalna diod kontrolera po podłączeniu (bez sprzętu: atrapa mido i portu wyjściowego)."""

from types import SimpleNamespace

import pytest

from engine.midi import MidiController
from engine.midi_intro import FRAME_S, LedIntro, intro_frames, led_columns
from engine.midi_profiles import PROFILES

MUTE = [1, 4, 7, 10, 13, 16, 19, 22]
REC = [3, 6, 9, 12, 15, 18, 21, 24]


class FakeOut:
    def __init__(self):
        self.sent = []
        self.fail = False

    def send(self, msg):
        if self.fail:
            raise OSError("port zniknął")
        self.sent.append((msg.note, msg.velocity))

    def close(self):
        pass


class FakeMido:
    def __init__(self, names, with_output=True):
        self.names = list(names)
        self.with_output = with_output
        self.outs = []

    def get_input_names(self):
        return list(self.names)

    def get_output_names(self):
        return list(self.names) if self.with_output else []

    def open_input(self, name):
        return SimpleNamespace(iter_pending=lambda: [], close=lambda: None)

    def open_output(self, name):
        self.outs.append(FakeOut())
        return self.outs[-1]

    @staticmethod
    def Message(kind, **fields):  # noqa: N802 – jak mido.Message
        return SimpleNamespace(type=kind, **fields)


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


@pytest.fixture
def rig(store, monkeypatch):
    import engine.midi as em

    fake = FakeMido(["MIDI Mix 0"])
    monkeypatch.setattr(em, "mido", fake)
    m = MidiController(store)
    m.backend = "fake"
    m.clock = Clock()
    return m, fake


def _state(sent):
    """Ostatnia wysłana wartość każdej diody."""
    out = {}
    for n, v in sent:
        out[n] = v
    return out


def _run(m, seconds):
    end = m.clock.t + seconds
    while m.clock.t < end:
        m.clock.t += 0.005
        m.poll()


# --- logika klatek (bez kontrolera) ---
def test_columns_follow_midimix_layout():
    p = PROFILES["Akai MIDImix"]
    cols = led_columns(p.layout, set(p.feedback))
    assert cols == [[f"note:0:{m}", f"note:0:{r}"] for m, r in zip(MUTE, REC, strict=True)]
    # bez układu (np. mapa z learn): każda dioda to osobna kolumna, w kolejności numerów
    assert led_columns((), {"note:0:10", "note:0:2", "cc:0:5"}) == [["note:0:2"], ["note:0:10"]]
    assert led_columns(p.layout, set()) == []


def test_frames_wave_and_flash():
    p = PROFILES["Akai MIDImix"]
    frames = intro_frames(led_columns(p.layout, set(p.feedback)))
    mids = set(p.feedback)
    assert all(set(f) == mids for f in frames)  # każda klatka opisuje wszystkie diody
    lit = [{k for k, v in f.items() if v} for f in frames]
    assert lit[0] == {"note:0:1"}  # fala zaczyna od MUTE 1
    assert lit[1] == {"note:0:1", "note:0:3", "note:0:4"}  # po przekątnej: REC o krok za MUTE
    assert lit[8] == mids  # wypełnione
    assert lit[17] == set()  # fala przeszła w prawo
    assert lit[-1] == set() and mids in lit[18:]  # błysk całości, koniec zgaszony
    assert 0.8 < len(frames) * FRAME_S < 1.6  # krótka: około sekundy
    assert intro_frames([]) == []


def test_led_intro_timing_starts_on_first_call():
    intro = LedIntro([{"a": 1}, {"a": 0}], frame_s=0.1)
    assert intro.frame(50.0) == {"a": 1}  # start liczony od pierwszego kroku (np. po wolnym starcie okna)
    assert intro.frame(50.15) == {"a": 0}
    assert intro.frame(50.2) is None and intro.done
    assert intro.mids == {"a"}


# --- integracja z kontrolerem ---
def test_intro_plays_after_connect_and_restores_state(rig, store):
    m, fake = rig
    store.set("echo.enabled", True, source="gui")  # MUTE 6 świeci
    store.set("iso.kill.sub", False, source="gui")
    assert m.ensure_connected(None) is True
    out = m.out_port
    assert m.intro_running
    m.poll()
    assert _state(out.sent) == {n: (127 if n == 1 else 0) for n in MUTE + REC}  # pierwsza klatka
    store.set("iso.kill.sub", True, source="gui")  # zmiana w trakcie: steruje, dioda poczeka
    _run(m, 0.3)
    assert m.intro_running and store["iso.kill.sub"] is True
    _run(m, 2.0)
    assert not m.intro_running
    final = _state(out.sent)
    assert final[1] == 127 and final[16] == 127  # kill sub i echo z ParamStore
    expected = {n: m._led_value(f"note:0:{n}") for n in MUTE + REC}
    assert final == expected
    n = len(out.sent)
    _run(m, 0.5)
    assert len(out.sent) == n  # po animacji cisza


def test_intro_disabled_sends_state_at_once(rig, store):
    m, fake = rig
    m.intro_enabled = False
    store.set("echo.enabled", True, source="gui")
    m.ensure_connected(None)
    assert not m.intro_running
    m.poll()
    assert _state(m.out_port.sent) == {n: m._led_value(f"note:0:{n}") for n in MUTE + REC}
    assert _state(m.out_port.sent)[16] == 127


def test_no_intro_without_output_port(store, monkeypatch):
    import engine.midi as em

    monkeypatch.setattr(em, "mido", FakeMido(["MIDI Mix 0"], with_output=False))
    m = MidiController(store)
    m.backend = "fake"
    assert m.ensure_connected(None) is True and m.out_port is None
    assert not m.intro_running
    m.poll()


def test_reconnect_restarts_intro(rig):
    m, fake = rig
    m.ensure_connected(None)
    _run(m, 0.4)
    first = m.out_port
    fake.names = []  # odłączony w trakcie animacji
    assert m.ensure_connected(None) is False
    assert not m.intro_running and _state(first.sent) == {n: 0 for n in MUTE + REC}
    m.poll()
    fake.names = ["MIDI Mix 1"]
    assert m.ensure_connected(None) is True and m.intro_running
    m.poll()
    assert _state(m.out_port.sent) == {n: (127 if n == 1 else 0) for n in MUTE + REC}  # od początku


def test_open_during_intro_starts_over(rig):
    m, fake = rig
    m.ensure_connected(None)
    _run(m, 0.5)
    m.open("MIDI Mix 0")  # ręczny wybór portu w trakcie animacji
    assert m.intro_running
    m.poll()
    assert _state(m.out_port.sent)[1] == 127 and _state(m.out_port.sent)[22] == 0


@pytest.mark.parametrize("how", ["profile", "json", "clear"])
def test_profile_change_interrupts_intro(rig, store, how):
    m, fake = rig
    store.set("echo.enabled", True, source="gui")
    m.ensure_connected(None)
    _run(m, 0.4)  # część diod zapalona przez animację
    out = m.out_port
    if how == "profile":
        m.apply_profile("Akai MIDImix")
    elif how == "json":
        m.load_json(m.to_json())
    else:
        m.clear()
    assert not m.intro_running
    m.poll()
    state = _state(out.sent)
    expected = {n: m._led_value(f"note:0:{n}") for n in MUTE + REC} if how != "clear" else {n: 0 for n in MUTE + REC}
    assert state == expected  # bez diod zawieszonych przez animację


def test_send_failure_during_intro_stops_quietly(rig):
    m, fake = rig
    m.ensure_connected(None)
    m.poll()
    m.out_port.fail = True
    _run(m, 0.2)
    assert m.out_port is None and not m.intro_running
    _run(m, 0.2)  # bez wyjątków


def test_set_intro_previews_and_stops(rig, store):
    m, fake = rig
    m.intro_enabled = False
    m.ensure_connected(None)
    m.poll()
    m.set_intro(True)  # włączenie = podgląd na sprzęcie
    assert m.intro_running
    _run(m, 0.3)
    m.set_intro(False)
    assert not m.intro_running and not m.intro_enabled
    m.poll()
    assert _state(m.out_port.sent) == {n: m._led_value(f"note:0:{n}") for n in MUTE + REC}
