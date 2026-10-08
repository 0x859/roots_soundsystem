import pytest

mido = pytest.importorskip("mido")

from engine.midi import MidiController  # noqa: E402


def test_learn_and_map_cc(store):
    midi = MidiController(store)
    learned = []
    midi.on_learned = lambda mid, key: learned.append((mid, key))
    midi.learning = True
    midi.arm("preamp.hp")
    midi.handle(mido.Message("control_change", channel=0, control=21, value=10))
    assert learned == [("cc:0:21", "preamp.hp")]
    midi.learning = False
    midi.handle(mido.Message("control_change", channel=0, control=21, value=127))
    assert store["preamp.hp"] == pytest.approx(1000.0)
    midi.handle(mido.Message("control_change", channel=0, control=21, value=0))
    assert store["preamp.hp"] == pytest.approx(20.0)


def test_note_momentary_and_toggle(store):
    midi = MidiController(store)
    midi.mapping = {"note:9:36": "siren.trigger", "note:9:37": "preamp.mono"}
    midi.handle(mido.Message("note_on", channel=9, note=36, velocity=100))
    assert store["siren.trigger"] is True
    midi.handle(mido.Message("note_off", channel=9, note=36))
    assert store["siren.trigger"] is False
    midi.handle(mido.Message("note_on", channel=9, note=37, velocity=100))
    midi.handle(mido.Message("note_off", channel=9, note=37))
    assert store["preamp.mono"] is True
    midi.handle(mido.Message("note_on", channel=9, note=37, velocity=100))
    assert store["preamp.mono"] is False


def test_mapping_roundtrip(store):
    midi = MidiController(store)
    midi.mapping = {"cc:0:1": "echo.feedback", "cc:0:2": "nie.istnieje"}
    other = MidiController(store)
    other.load_json(midi.to_json())
    assert other.mapping == {"cc:0:1": "echo.feedback"}
