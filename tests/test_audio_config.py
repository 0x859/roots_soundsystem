"""Konfiguracja audio bez widżetów i robocza konfiguracja dla QML (bez prawdziwych urządzeń)."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from engine.audio_engine import DeviceInfo, EngineConfig  # noqa: E402
from ui import audio_config as ac  # noqa: E402

DEVICES = [
    DeviceInfo(1, "CABLE Output (VB-Audio Virtual Cable)", "Windows WASAPI", 2, 0, 48000),
    DeviceInfo(2, "Analogue 1 + 2 (Focusrite USB Audio)", "Windows WASAPI", 6, 0, 48000),
    DeviceInfo(3, "Speakers (Focusrite USB Audio)", "Windows WASAPI", 0, 4, 48000),
    DeviceInfo(4, "Głośniki (Realtek(R) Audio)", "Windows WASAPI", 0, 2, 48000),
    DeviceInfo(5, "CABLE Input (VB-Audio Virtual Cable)", "Windows WASAPI", 0, 2, 48000),
]


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def settings(tmp_path):
    return QSettings(str(tmp_path / "s.ini"), QSettings.IniFormat)


def test_items_and_matching():
    assert [v for _, v in ac.music_items(DEVICES)] == [1, 2]
    assert ac.output_items(DEVICES)[0] == ("Speakers (Focusrite USB Audio) [Windows WASAPI] (4 kan.)", 3)
    assert ac.mic_items(DEVICES)[0] == (ac.NO_MIC, None)
    items = [("Alfa [X]", 1), ("Beta [X]", 2)]
    assert ac.match_item(items, "Beta") == 2
    assert ac.match_item(items, "Gamma", fallback=2) == 2
    assert ac.match_item(items, None) == 1
    assert ac.match_item([], "x") is None


def test_resolve_and_persist_roundtrip(settings, monkeypatch):
    monkeypatch.setattr(ac, "wasapi_default_output", lambda: 5)  # domyślne wyjście = CABLE Input → pomijane
    music, out, mic = ac.resolve_devices(DEVICES, settings)
    assert music == 1  # CABLE Output jako źródło muzyki
    assert out == 3 and mic is None
    cfg = EngineConfig(music_in=2, output=4, mic_in=2, mode="multi", block=1024, channel_map={"bass": (0, 1)},
                       sim_mirror=True, music_offset=4, mic_channel=1)
    ac.persist(settings, cfg, DEVICES)
    assert ac.resolve_devices(DEVICES, settings) == (2, 4, 2)
    assert settings.value("audio/music_offset") in (4, "4")
    assert settings.value("audio/mode") == "multi"


def test_hints():
    tips = ac.hints(DEVICES, 2, 3, 4)
    assert any("Loopback" in t for t in tips)
    two_ch = [DeviceInfo(9, "Focusrite USB", "WASAPI", 0, 2, 48000)]
    assert any("Kwadrofoniczne" in t for t in ac.hints(two_ch, None, 9, 0, "notatka"))


def test_qml_audio_draft(app, store):
    from ui.quick import QmlAudio

    a = QmlAudio(store, lambda: DEVICES)
    a.load(DEVICES, EngineConfig(music_in=1, output=4, mic_in=None))
    assert not a.property("dirty")
    assert a.property("mic") == -1 and a.property("channelCount") == 2
    assert len(a.property("presets")) == 1  # 2 kanały: brak gotowych układów
    assert not a.property("mirrorAvailable")

    a.setOutput(3)
    assert a.property("channelCount") == 4 and a.property("mirrorAvailable")
    assert len(a.property("presets")) > 1
    a.applyPreset("multi4_mono")
    assert a.property("mode") == "multi" and a.pending_ways == 2
    assert [w["way"] for w in a.property("ways")] == ["sub", "bass", "mid", "top"]
    assert a.property("problems") == []
    a.setChannel("top", "left", 1)
    assert any("Kanał 2" in p for p in a.property("problems"))
    a.setChannel("top", "left", 3)
    a.setMusic(2)
    assert [p["value"] for p in a.property("musicPairs")] == [0, 2, 4]
    a.setMusicOffset(4)
    assert any("Loopback" in t for t in a.property("tips"))
    a.setMic(2)
    a.setMicChannel(1)
    a.setBlock(256)
    a.setBlock(999)  # spoza listy – ignorowane
    assert a.property("dirty")

    cfg = a.config(48000)
    assert (cfg.output, cfg.mode, cfg.block, cfg.music_offset, cfg.mic_in, cfg.mic_channel) == (3, "multi", 256, 4, 2, 1)
    assert cfg.channel_map["top"] == (3, -1)

    a.revert()
    assert not a.property("dirty") and a.pending_ways is None
    applied = []
    a.applyRequested.connect(lambda: applied.append(1))
    a.apply()
    assert applied == [1]


def test_qml_audio_refresh_drops_missing_devices(app, store):
    from ui.quick import QmlAudio

    current = list(DEVICES)
    a = QmlAudio(store, lambda: current)
    a.load(current, EngineConfig(music_in=1, output=3, mic_in=2))
    current.pop(1)  # odłączony interfejs z mikrofonem
    a.refresh()
    assert a.property("mic") == -1 and a.property("output") == 3
