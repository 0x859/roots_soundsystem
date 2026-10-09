"""Podgląd i edycja mapy MIDI dla QML (`QmlMidi`) oraz obsługa w oknie głównym – bez sprzętu."""

import json
import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from engine.midi import MidiController  # noqa: E402


def cc(num, value):
    return SimpleNamespace(type="control_change", channel=0, control=num, value=value)


def note(num, on=True):
    return SimpleNamespace(type="note_on" if on else "note_off", channel=0, note=num, velocity=127 if on else 0)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def qmidi(app, store):
    from ui.quick import QmlMidi

    ctl = MidiController(store)
    ctl.apply_profile("Akai MIDImix")
    return QmlMidi(ctl)


def _element(qmidi, mid):
    return next(e for s in qmidi.property("strips") for e in s["elements"] if e["id"] == mid)


def test_strips_describe_mapping(qmidi):
    strips = qmidi.property("strips")
    assert [s["name"] for s in strips] == [*map(str, range(1, 9)), "MASTER"]
    knob = _element(qmidi, "cc:0:16")
    assert knob["kind"] == "knob" and knob["code"] == "CC 16"
    assert knob["normal"]["target"] == "preamp.hp" and knob["normal"]["module"] == "PREAMP"
    assert knob["shift"]["target"] == "preamp.gain" and knob["shiftOwn"]
    mute = _element(qmidi, "note:0:1")
    assert mute["sid"] == "note:0:2" and mute["normal"]["tone"] == "kill" and mute["normal"]["bool"]
    rec = _element(qmidi, "note:0:3")
    assert not rec["shiftOwn"] and rec["shift"]["target"] == "echo.throw"  # w SHIFT działa jak bez SHIFT
    solo = _element(qmidi, "note:0:27")
    assert solo["isShift"]
    assert qmidi.property("others") == []
    assert qmidi.property("mappedCount") == len(qmidi.ctl.mapping) + len(qmidi.ctl.shift_mapping)


def test_assign_unassign_and_others(qmidi):
    changed = []
    qmidi.stateChanged.connect(lambda: changed.append(1))
    qmidi.assign("cc:0:16", "echo.feedback", False)
    assert _element(qmidi, "cc:0:16")["normal"]["label"] == "Feedback" and changed
    qmidi.assign("note:0:3", "action:dsp_toggle", True)
    rec = _element(qmidi, "note:0:3")
    assert rec["shiftOwn"] and rec["shift"]["action"] and rec["shift"]["module"] == "AKCJA"
    qmidi.assign("cc:0:16", "nie.istnieje", False)  # ignorowane
    assert qmidi.ctl.mapping["cc:0:16"] == "echo.feedback"
    qmidi.unassign("cc:0:16", False)
    assert _element(qmidi, "cc:0:16")["normal"]["target"] == ""
    qmidi.ctl.assign("cc:1:7", "out.master")  # element spoza MIDImix (np. drugi kontroler)
    qmidi.tick()
    others = qmidi.property("others")
    assert others == [others[0]] and others[0]["name"] == "CC 7 · kan. 2" and others[0]["target"] == "out.master"


def test_live_state(qmidi):
    live = []
    qmidi.liveChanged.connect(lambda: live.append(1))
    qmidi.ctl.handle(cc(19, 64))
    qmidi.tick()
    assert live and qmidi.property("hw")["cc:0:19"] == pytest.approx(64 / 127)
    assert qmidi.property("activity")["cc:0:19"] == 1
    assert qmidi.property("lastEvent") == "CC 19 = 64 → Sub"
    n = len(live)
    qmidi.tick()
    assert len(live) == n  # bez nowych komunikatów – bez sygnału
    qmidi.ctl.handle(note(27, True))
    qmidi.tick()
    assert qmidi.property("hwShift")


def test_selection_and_layer(qmidi):
    qmidi.select("cc:0:20")
    qmidi.setShiftView(True)
    assert qmidi.property("selected") == "cc:0:20" and qmidi.property("shiftView")


def test_search_targets(qmidi):
    found = qmidi.search("syrena")
    assert found and all(f["module"] == "SYRENA" or "syren" in f["value"] or "yren" in f["label"].lower() for f in found)
    assert any(f["value"] == "action:siren_mem:0" for f in qmidi.search("pamięć"))
    assert len(qmidi.search("")) == 40


def test_profile_learning_pickup_slots(qmidi):
    qmidi.setLearning(True)
    assert qmidi.ctl.learning and qmidi.property("learning")
    qmidi.setPickup(False)
    assert not qmidi.ctl.pickup and not qmidi.property("pickup")
    qmidi.clearMapping()
    assert qmidi.property("strips") == [] and qmidi.property("mappedCount") == 0
    qmidi.applyProfile("Akai MIDImix")
    assert len(qmidi.property("strips")) == 9


# --- okno główne ---
@pytest.fixture
def window(app, tmp_path, monkeypatch):
    from tests.test_quick import _make_window

    win = _make_window(app, tmp_path, monkeypatch)
    yield win
    for t in (win.scaler._timer, win._meter_timer, win._status_timer, win._midi_timer, win._resp_timer, win._midi_watch):
        t.stop()
    if win.quick is not None:
        win.quick.shutdown()
    win.midi.close()
    win.engine.stop()
    win.preview.dispose()
    win.hide()


def test_window_midi_map_and_files(window, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    win = window
    toasts = []
    win.session.toast.connect(toasts.append)
    win._on_qml_request("midi_map", None)
    assert win.view == "qml" and win.session.property("screen") == "config"

    win.midi.apply_profile("Akai MIDImix")
    win.midi.assign("cc:0:16", "echo.feedback")
    path = tmp_path / "mapa.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(path), "")))
    win._midi_file("export")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["version"] == 2 and data["mapping"]["cc:0:16"] == "echo.feedback"

    win.midi.clear()
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(path), "")))
    win._midi_file("import")
    assert win.midi.mapping["cc:0:16"] == "echo.feedback" and win.midi.profile_name == "Akai MIDImix"
    bad = tmp_path / "zla.json"
    bad.write_text("{nie json", encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(bad), "")))
    win._midi_file("import")
    assert win.midi.mapping["cc:0:16"] == "echo.feedback" and "Nie udało się" in toasts[-1]

    win.qmidi.tick()
    assert win.qmidi.property("profileName") == "Akai MIDImix"


def test_window_midi_status_saves_port(window):
    win = window
    toasts = []
    win.session.toast.connect(toasts.append)
    win.midi.port_name = "MIDI Mix 1"
    win._on_midi_status("connected")
    assert win.settings.value("midi/port") == "MIDI Mix 1" and "podłączono" in toasts[-1]
    win.midi.port_name = None
    win._on_midi_status("disconnected")
    assert "odłączony" in toasts[-1]
