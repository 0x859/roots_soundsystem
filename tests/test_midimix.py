"""Profil Akai MIDImix: mapowanie, SHIFT, akcje, przejęcie wartości i diody (bez sprzętu i bez mido)."""

from types import SimpleNamespace

import pytest

from engine.midi import MidiController, match_output
from engine.midi_profiles import ACTIONS, PROFILES, profile_for_port


def cc(num, value, ch=0):
    return SimpleNamespace(type="control_change", channel=ch, control=num, value=value)


def note(num, on=True, ch=0):
    return SimpleNamespace(type="note_on" if on else "note_off", channel=ch, note=num, velocity=127 if on else 0)


class FakeOut:
    def __init__(self):
        self.sent = []

    def send(self, msg):
        self.sent.append((msg.note, msg.velocity))

    def close(self):
        pass


@pytest.fixture
def mix(store):
    m = MidiController(store)
    m.apply_profile("Akai MIDImix")
    m.out_port = FakeOut()
    m.flush_leds()
    m.out_port.sent.clear()
    return m


def test_profile_targets_exist(store):
    p = PROFILES["Akai MIDImix"]
    for layer in (p.mapping, p.shift_mapping):
        for mid, target in layer.items():
            assert target in store.specs or target in ACTIONS, f"{mid} -> {target}"
    assert len(p.mapping) == 24 + 9 + 16 + 2
    assert len(p.shift_mapping) == 24 + 8
    assert len(p.feedback) == 16


def test_port_detection():
    assert profile_for_port("MIDI Mix 0").name == "Akai MIDImix"
    assert profile_for_port("Launchpad") is None
    assert match_output("MIDI Mix 0", ["Microsoft GS", "MIDI Mix 1"]) == "MIDI Mix 1"
    assert match_output("MIDI Mix", ["MIDI Mix"]) == "MIDI Mix"


def test_fader_needs_pickup_then_follows(mix, store):
    store.set("echo.return", store.specs["echo.return"].from_norm(0.5), source="gui")
    mix.handle(cc(53, 0))  # suwak 6 na dole, wartość w połowie – brak skoku
    assert store.specs["echo.return"].to_norm(store["echo.return"]) == pytest.approx(0.5, abs=0.01)
    assert "echo.return" in mix.pickup_pending()
    mix.handle(cc(53, 80))  # minął 0.5 -> przejęty
    assert store.specs["echo.return"].to_norm(store["echo.return"]) == pytest.approx(80 / 127, abs=0.01)
    mix.handle(cc(53, 20))
    assert store.specs["echo.return"].to_norm(store["echo.return"]) == pytest.approx(20 / 127, abs=0.01)
    assert "echo.return" not in mix.pickup_pending()


def test_scene_change_releases_pickup(mix, store):
    mix.handle(cc(62, 0))
    mix.handle(cc(62, 127))  # przejęty
    store.set("out.master", store.specs["out.master"].from_norm(0.2), source="gui")  # np. scena
    mix.handle(cc(62, 120))
    assert store.specs["out.master"].to_norm(store["out.master"]) == pytest.approx(0.2, abs=0.01)


def test_pickup_can_be_disabled(mix, store):
    mix.pickup = False
    mix.handle(cc(16, 127))
    assert store["preamp.hp"] == pytest.approx(store.specs["preamp.hp"].max)


def test_shift_layer(mix, store):
    mix.pickup = False
    mix.handle(note(27, True))  # SOLO trzymane
    assert mix.shift_held
    mix.handle(cc(20, 0))  # gałka 2 górna w warstwie SHIFT = iso.f1
    assert store["iso.f1"] == pytest.approx(store.specs["iso.f1"].min)
    drive = store["preamp.drive"]
    mix.handle(note(27, False))
    mix.handle(cc(20, 127))  # bez SHIFT = preamp.drive
    assert store["preamp.drive"] != drive and store["preamp.drive"] == pytest.approx(1.0)


def test_kill_toggle_and_led(mix, store):
    mix.handle(note(1, True))
    mix.handle(note(1, False))
    assert store["iso.kill.sub"] is True
    mix.flush_leds()
    assert (1, 127) in mix.out_port.sent
    mix.handle(note(1, True))
    mix.handle(note(1, False))
    assert store["iso.kill.sub"] is False
    mix.flush_leds()
    assert mix.out_port.sent[-1] == (1, 0)


def test_led_follows_gui_changes(mix, store):
    store.set("echo.enabled", False, source="gui")
    mix.flush_leds()
    assert (16, 0) in mix.out_port.sent
    mix.out_port.sent.clear()
    mix.flush_leds()
    assert mix.out_port.sent == []  # bez zmian – bez komunikatów


def test_momentary_throw_holds(mix, store):
    mix.handle(note(3, True))
    assert store["echo.throw"] is True
    mix.handle(note(3, False))
    assert store["echo.throw"] is False


def test_actions_fire_on_press_only(mix):
    fired = []
    mix.on_action = fired.append
    mix.handle(note(25, True))
    mix.handle(note(25, False))
    mix.handle(note(26, True))
    mix.handle(note(12, True))
    assert fired == ["action:scene_prev", "action:scene_next", "action:tap"]


def test_learn_latches_immediately(store):
    m = MidiController(store)
    m.learning = True
    m.arm("preamp.hp")
    m.handle(cc(99, 10))
    m.learning = False
    m.handle(cc(99, 127))
    assert store["preamp.hp"] == pytest.approx(store.specs["preamp.hp"].max)


def test_json_roundtrip_v2_and_legacy(mix, store):
    other = MidiController(store)
    other.load_json(mix.to_json())
    assert other.mapping == mix.mapping and other.shift_mapping == mix.shift_mapping
    assert other.shift_id == "note:0:27" and other.feedback == mix.feedback
    legacy = MidiController(store)
    legacy.load_json('{"cc:0:1": "echo.feedback", "cc:0:2": "nie.istnieje"}')
    assert legacy.mapping == {"cc:0:1": "echo.feedback"}


def test_leds_off_on_close(mix):
    port = mix.out_port
    mix.close()
    assert len(port.sent) == 16 and all(v == 0 for _, v in port.sent)
