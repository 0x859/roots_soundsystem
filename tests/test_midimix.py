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
    assert len(p.shift_mapping) == 24 + 8 + 4  # gałki, rząd Mute przy SOLO, Rec Arm 1-3 i 6
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


def test_actions_cover_interface_actions():
    from ui.layout_profile import ACTIONS as UI_ACTIONS

    assert set(UI_ACTIONS) <= set(ACTIONS)  # każdą akcję z interfejsu można przypisać do kontrolera


def test_midimix_layout_covers_mapping():
    p = PROFILES["Akai MIDImix"]
    strips = p.layout
    assert len(strips) == 9 and strips[-1].name == "MASTER"
    ids = {e.id for s in strips for e in s.elements} | {e.shift_id for s in strips for e in s.elements if e.shift_id}
    assert set(p.mapping) <= ids and set(p.shift_mapping) <= ids
    assert p.shift in ids
    kinds = [e.kind for e in strips[0].elements]
    assert kinds == ["knob", "knob", "knob", "button", "button", "fader"]
    mute = strips[0].elements[3]
    assert (mute.id, mute.shift_id, mute.led) == ("note:0:1", "note:0:2", True)


def test_assign_and_unassign(mix, store):
    mix.assign("cc:0:16", "echo.feedback")
    assert mix.mapping["cc:0:16"] == "echo.feedback"
    mix.pickup = False
    mix.handle(cc(16, 127))
    assert store["echo.feedback"] == pytest.approx(store.specs["echo.feedback"].max)
    mix.assign("cc:0:16", "room.mix", shift=True)
    assert mix.shift_mapping["cc:0:16"] == "room.mix"
    mix.assign("note:0:3", "action:dsp_toggle")
    assert mix.mapping["note:0:3"] == "action:dsp_toggle"
    with pytest.raises(KeyError):
        mix.assign("cc:0:16", "nie.istnieje")
    mix.unassign("cc:0:16")
    assert "cc:0:16" not in mix.mapping and mix.shift_mapping["cc:0:16"] == "room.mix"
    mix.unassign("cc:0:16", shift=True)
    assert "cc:0:16" not in mix.shift_mapping


def test_assign_bool_to_led_button_updates_led(mix, store):
    store.set("preamp.mono", True, source="gui")
    mix.assign("note:0:1", "preamp.mono")  # Mute 1 (z diodą)
    mix.flush_leds()
    assert (1, 127) in mix.out_port.sent


def test_activity_and_hw_position(mix):
    before = mix.activity.get("cc:0:19", 0)
    mix.handle(cc(19, 64))
    assert mix.activity["cc:0:19"] == before + 1
    assert mix.hw_position("cc:0:19") == pytest.approx(64 / 127)
    assert mix.last_event == ("cc:0:19", pytest.approx(64 / 127))
    mix.handle(note(27, True))  # SOLO (SHIFT) też jest aktywnością
    assert mix.activity["note:0:27"] == 1


def test_element_names():
    from engine.midi import element_name

    assert element_name("cc:0:19") == "CC 19"
    assert element_name("note:0:27") == "Nuta 27"
    assert element_name("cc:3:7") == "CC 7 · kan. 4"
    assert element_name("pw:0") == "Pitch bend"


class FakeMido:
    """Podmiana mido: lista portów zmienia się jak przy podłączaniu/odłączaniu kontrolera."""

    def __init__(self, names):
        self.names = list(names)
        self.opened = []

    def get_input_names(self):
        return list(self.names)

    def get_output_names(self):
        return list(self.names)

    def open_input(self, name):
        self.opened.append(name)
        return SimpleNamespace(iter_pending=lambda: [], close=lambda: None)

    def open_output(self, name):
        return FakeOut()


def test_ensure_connected_follows_plugging(store, monkeypatch):
    import engine.midi as em

    fake = FakeMido([])
    monkeypatch.setattr(em, "mido", fake)
    m = MidiController(store)
    m.backend = "fake"
    events = []
    m.on_status = events.append
    assert m.ensure_connected("MIDI Mix 0") is False and m.port is None
    fake.names = ["Microsoft GS", "MIDI Mix 1"]  # Windows nadał inny numer
    assert m.ensure_connected("MIDI Mix 0") is True
    assert m.port_name == "MIDI Mix 1" and m.profile_name == "Akai MIDImix"
    fake.names = ["Microsoft GS"]  # odłączony
    assert m.ensure_connected("MIDI Mix 0") is False and m.port is None
    assert events == ["connected", "disconnected"]


def test_ensure_connected_auto_detects_known_controller(store, monkeypatch):
    import engine.midi as em

    fake = FakeMido(["Launchpad", "MIDI Mix"])
    monkeypatch.setattr(em, "mido", fake)
    m = MidiController(store)
    m.backend = "fake"
    assert m.ensure_connected(None) is True and m.port_name == "MIDI Mix"
    m2 = MidiController(store)
    m2.backend = "fake"
    assert m2.ensure_connected("") is False  # pusty = świadomie „bez kontrolera”


def test_shift_layer_on_rec_arm(mix, store):
    """SOLO + Rec Arm: FX PANIC, THROW MIC, SWELL, MONO; bez SOLO Rec Arm 6 to DRY CUT."""
    fired = []
    mix.on_action = fired.append
    mix.handle(note(27, True))  # SOLO = SHIFT
    mix.handle(note(3, True))
    assert store["out.fx_panic"] is True and store["echo.throw"] is False
    mix.handle(note(3, False))
    assert store["out.fx_panic"] is False
    for n, key in ((6, "mic.throw"), (9, "echo.swell")):
        mix.handle(note(n, True))
        assert store[key] is True
        mix.handle(note(n, False))
        assert store[key] is False
    mix.handle(note(18, True))
    mix.handle(note(18, False))
    assert store["preamp.mono"] is True and store["preamp.cut"] is False
    mix.handle(note(12, True))  # Rec Arm 4 bez własnej warstwy SHIFT: dalej TAP
    assert fired == ["action:tap"]
    mix.handle(note(12, False))
    mix.handle(note(27, False))
    mix.handle(note(18, True))
    assert store["preamp.cut"] is True
    mix.handle(note(18, False))
    assert store["preamp.cut"] is False and store["preamp.mono"] is True


@pytest.mark.parametrize("shift_first", [True, False])
def test_momentary_released_in_other_layer(mix, store, shift_first):
    """Puszczenie przycisku chwilowego po zmianie warstwy (SOLO puszczone lub wciśnięte w trakcie) zwalnia ten sam cel."""
    if shift_first:
        mix.handle(note(27, True))
    mix.handle(note(3, True))
    mix.handle(note(27, not shift_first))
    mix.handle(note(3, False))
    assert store["out.fx_panic"] is False and store["echo.throw"] is False
