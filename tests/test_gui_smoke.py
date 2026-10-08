import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QSettings, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    from ui.theme import apply_theme

    apply_theme(a)
    return a


@pytest.fixture(scope="module")
def window(app, tmp_path_factory):
    import os

    from dsp.graph import all_specs
    from engine.params import ParamStore
    from ui.main_window import MainWindow

    tmp = tmp_path_factory.mktemp("gui")
    os.environ["APPDATA"] = str(tmp)
    QMessageBox.exec = lambda self: 0
    QMessageBox.information = staticmethod(lambda *a, **k: 0)
    QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.No)
    QMessageBox.critical = staticmethod(lambda *a, **k: 0)
    MainWindow.open_audio_settings = lambda self: None

    settings = QSettings(str(tmp / "settings.ini"), QSettings.IniFormat)
    settings.setValue("audio/output", "Speakers")
    win = MainWindow(ParamStore(all_specs()), settings)
    win.scaler._timer.stop()
    win._midi_timer.stop()
    win.show()
    app.processEvents()
    win.scaler._timer.stop()
    yield win
    for t in (win.scaler._timer, win._meter_timer, win._status_timer, win._midi_timer, win._resp_timer):
        t.stop()
    win.midi.close()
    win.engine.stop()
    win.preview.dispose()
    win.hide()


def test_window_builds_and_reacts(window, app):
    store = window.store
    from ui.widgets import Knob, MomentaryButton, ParamSlider

    knobs = window.findChildren(Knob)
    sliders = window.findChildren(ParamSlider)
    assert len(knobs) > 60 and len(sliders) >= 18
    store.set("preamp.drive", 0.9)
    app.processEvents()
    k = next(k for k in knobs if k.key == "preamp.drive")
    assert k.value_label.text() == "90%"

    eq = next(s for s in sliders if s.key == "eq.b4")
    eq.slider.setValue(1000)
    assert store["eq.b4"] == 12.0
    eq.reset()
    assert store["eq.b4"] == 0.0

    btn = next(b for b in window.findChildren(MomentaryButton) if b.key == "siren.trigger")
    assert btn.property("active") == "false"
    store.set("siren.trigger", True)
    app.processEvents()
    assert btn.property("active") == "true"
    store.set("siren.trigger", False)


def test_keyboard_momentary(window, app):
    store = window.store
    window.activateWindow()
    app.processEvents()
    if QApplication.activeWindow() is not window:
        pytest.skip("brak aktywnego okna w trybie offscreen")
    app.sendEvent(window, QKeyEvent(QEvent.KeyPress, Qt.Key_1, Qt.NoModifier))
    assert store["iso.kill.sub"] is True
    app.sendEvent(window, QKeyEvent(QEvent.KeyRelease, Qt.Key_1, Qt.NoModifier))
    assert store["iso.kill.sub"] is False


def test_scenes_and_plots(window, app):
    store = window.store
    idx = window.scene_combo.findData("Steppers heavy")
    window._apply_scene(idx)
    assert store["iso.g.sub"] == 3.0
    window.plots.update_response()
    idx = window.scene_combo.findData("Neutralny")
    window._apply_scene(idx)
    assert store["iso.g.sub"] == 0.0


def test_mode_switch_and_channel_map(window, app):
    store = window.store
    from ui.widgets import ChannelMapEditor

    window.mode = "multi"
    window.output_panel.set_mode("multi")
    window._rebuild_preview()
    assert window.mode == "multi" and window.preview.mode == "multi"
    editor = ChannelMapEditor(window.bridge)
    editor.set_mode("multi")
    editor.set_device_channels(8)
    assert editor.problems_list() == []
    editor.set_device_channels(2)
    assert editor.problems_list()
    window.mode = "sim"
    window.output_panel.set_mode("sim")
    window._rebuild_preview()


def test_live_knobs_sync_with_panels(window, app):
    store = window.store
    from ui.widgets import Knob

    live_hp = window.live.hp
    others = [k for k in window.findChildren(Knob) if k.key == "preamp.hp" and k is not live_hp]
    assert others
    store.set("preamp.hp", 200.0)
    app.processEvents()
    assert live_hp.value_label.text() == others[0].value_label.text()


def test_audio_settings_mapping_and_mode(window, app):
    from ui.dialogs.audio_settings import MODES, BLOCKS
    from ui.widgets import ChannelMapEditor

    assert ("sim", "Symulacja (stereo)") in MODES
    assert 512 in BLOCKS
    editor = ChannelMapEditor(window.bridge, n_channels=8)
    editor.set_mode("sim")
    assert editor.problems_list() == [] or editor.mode == "sim"
    editor.set_mode("multi")
    editor.set_device_channels(8)
    assert editor.problems_list() == []
    cfg_map = editor.channel_map()
    assert "sub" in cfg_map and "top" in cfg_map


def _no_hscroll(scroll) -> bool:
    bar = scroll.horizontalScrollBar()
    return bar.maximum() == 0 or bar.maximum() <= scroll.viewport().width() * 0.02


def _apply_scale(window, app, width, height):
    window.scaler._timer.stop()
    window.resize(width, height)
    app.processEvents()
    window.scaler.natural_w = 0
    window.scaler.natural_h = 0
    window.scaler.apply()
    window.scaler._timer.stop()


def test_layout_fits_1920(window, app):
    from ui.theme import apply_scaled_stylesheet

    apply_scaled_stylesheet(app, 1.0)
    _apply_scale(window, app, 1920, 1080)
    assert window.scaler.scale >= 0.95
    assert _no_hscroll(window.desk_scroll) or window.scaler.scale >= 0.95


def test_layout_fits_1366(window, app):
    from ui.theme import apply_scaled_stylesheet

    apply_scaled_stylesheet(app, 1.0)
    _apply_scale(window, app, 1366, 768)
    assert window.scaler.scale < 1.0
    assert window.scaler.scale >= 0.7
    vw = window.desk_scroll.viewport().width()
    scaled_w = window.scaler.natural_w * window.scaler.scale
    assert scaled_w <= vw + 40 or window.desk_scroll.horizontalScrollBar().maximum() == 0
