"""Interfejs QML: most parametrów, model układu, sesja, ładowanie QML i okno w trybie QML."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6.QtQuick")

from PySide6.QtCore import QSettings, QUrl, qInstallMessageHandler  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from ui import layout_profile as lp  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def appdata(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    return tmp_path


@pytest.fixture
def bridge(app, store):
    from ui.binding import ParamBridge

    return ParamBridge(store)


@pytest.fixture
def params(bridge):
    from ui.quick import QmlParams

    return QmlParams(bridge)


@pytest.fixture
def layout(store, appdata):
    from ui.quick import LayoutModel

    return LayoutModel(store.specs)


# --- parametry ---
def test_param_object_follows_store(params, store):
    p = params.get("preamp.drive")
    assert p is params.get("preamp.drive")
    assert p.property("label") == "Drive"
    hits = []
    p.changed.connect(lambda: hits.append(1))
    store.set("preamp.drive", 0.9)
    assert hits and p.property("text") == "90%"
    assert p.property("norm") == pytest.approx(0.9)
    assert params.get("nie.ma") is None


def test_param_object_sets_store(params, store, bridge):
    touched = []
    bridge.touched.connect(touched.append)
    p = params.get("preamp.hp")
    p.setNorm(1.0)
    assert store["preamp.hp"] == 1000.0
    assert touched == ["preamp.hp"]
    p.reset()
    assert store["preamp.hp"] == store.specs["preamp.hp"].default

    sync = params.get("echo.sync")
    sync.setValue(0)
    sync.step(-1)
    assert store["echo.sync"] == len(store.specs["echo.sync"].choices) - 1
    mute = params.get("out.mute")
    mute.toggle()
    assert store["out.mute"] is True and mute.property("on") is True
    assert params.get("iso.kill.sub").property("hold") is True
    assert params.get("iso.g.sub").property("originNorm") == pytest.approx(40 / 46)


def test_param_search_and_types(params):
    keys = [h["key"] for h in params.search("kill")]
    assert "iso.kill.sub" in keys
    assert [h["key"] for h in params.search("tap")] == ["action:tap"]
    assert params.typesFor("echo.throw")[0] == "button"
    assert params.typesFor("zly.cel") == []
    assert params.labelOf("view:meters") == lp.VIEWS["view:meters"]


# --- model układu ---
def test_layout_edit_undo_redo(layout):
    titles = [c["title"] for c in layout.cards]
    layout.moveCard(0, 2)
    assert [c["title"] for c in layout.cards][2] == titles[0]
    assert layout.canUndo and not layout.canRedo
    layout.undo()
    assert [c["title"] for c in layout.cards] == titles
    layout.redo()
    assert [c["title"] for c in layout.cards][2] == titles[0]

    k = layout.addControl(0, "echo.wow")
    assert layout.cards[0]["controls"][k]["param"] == "echo.wow"
    layout.setControlProp(0, k, "size", "L")
    layout.setControlProp(0, k, "label", "Taśma")
    assert layout.cards[0]["controls"][k] == {"param": "echo.wow", "type": "knob", "size": "L", "label": "Taśma"}
    layout.setControlProp(0, k, "param", "echo.throw")
    assert layout.cards[0]["controls"][k]["type"] == "button"  # typ dopasowany do przełącznika
    layout.moveControl(0, k, 1, 0)
    assert layout.cards[1]["controls"][0]["param"] == "echo.throw"
    layout.removeControl(1, 0)
    assert layout.addControl(0, "zly.cel") == -1


def test_layout_cards_pads_shortcuts(layout):
    n = len(layout.cards)
    ci = layout.addCard("MOJA", "config")
    assert ci == n and layout.cards[ci]["visible"] == "config"
    layout.setCardProp(ci, "span", 2)
    dup = layout.duplicateCard(ci)
    assert layout.cards[dup]["id"] != layout.cards[ci]["id"]
    layout.removeCard(dup)
    layout.removeCard(ci)
    assert len(layout.cards) == n

    layout.addPad("out.mute")
    assert layout.pads[-1] == {"param": "out.mute", "label": "MUTE"}
    layout.movePad(len(layout.pads) - 1, 0)
    assert layout.pads[0]["param"] == "out.mute"
    layout.removePad(0)
    layout.addPad("view:meters")
    assert all(p["param"] != "view:meters" for p in layout.pads)

    # klawisz zajęty przez inny cel zostaje przejęty
    assert layout.setShortcut("out.mute", "space")
    assert layout.shortcuts["Space"] == "out.mute"
    assert layout.shortcutFor("echo.throw") == ""
    from PySide6.QtCore import Qt

    assert layout.shortcut_map()[Qt.Key_Space.value] == "out.mute"
    assert not layout.setShortcut("out.mute", "Ctrl+X")
    assert layout.setShortcut("out.mute", "")
    assert layout.shortcutFor("out.mute") == ""


def test_layout_card_height(layout):
    layout.setCardBox(0, 2, 1, 320)
    assert (layout.cards[0]["span"], layout.cards[0]["height"]) == (2, 320)
    layout.setCardBox(0, 2, 1, -1)  # -1 = wysokość bez zmian
    assert layout.cards[0]["height"] == 320
    layout.setCardBox(0, 2, 1, 30)  # poniżej minimum → automatyczna
    assert layout.cards[0]["height"] == 0
    layout.setCardProp(0, "height", 5000)
    assert layout.cards[0]["height"] == lp.MAX_HEIGHT
    layout.undo()
    layout.undo()
    assert layout.cards[0]["height"] == 320


def test_layout_card_size_and_state(layout):
    layout.setCardSize(0, 3, 2)
    assert (layout.cards[0]["span"], layout.cards[0]["rows"]) == (3, 2)
    layout.undo()
    assert (layout.cards[0]["span"], layout.cards[0]["rows"]) == (1, 1)  # jedna zmiana w historii
    layout.setCardSize(0, 9, 0)
    assert (layout.cards[0]["span"], layout.cards[0]["rows"]) == (lp.MAX_SPAN, 1)
    layout.setCardProp(0, "cols", 4)
    assert layout.cards[0]["cols"] == 4

    undo_before = layout.canUndo
    layout._undo.clear()
    layout.historyChanged.emit()
    layout.setCardState(0, "collapsed", True)
    assert layout.cards[0]["collapsed"] is True and not layout.canUndo  # zwinięcie nie trafia do historii
    layout.setThemeQuiet("inspectorWidth", 500)
    assert layout.theme.property("inspectorWidth") == 500 and not layout.canUndo
    layout.setTheme("tiles", True)
    assert layout.theme.property("tiles") is True and layout.canUndo
    assert undo_before


def test_layout_theme(layout):
    th = layout.theme
    changed = []
    th.changed.connect(lambda: changed.append(1))
    layout.setTheme("colors.accent", "#112233")
    layout.setTheme("scale", 1.5)
    layout.setTheme("pads.position", "top")
    assert changed
    assert th.property("accent") == "#112233"
    assert th.property("scale") == 1.5
    assert th.property("padPosition") == "top"
    assert th.color("fx", "accent") == lp.DEFAULT_THEME["colors"]["fx"]
    assert th.color("auto", "kill") == lp.DEFAULT_THEME["colors"]["kill"]
    assert th.color("#ABCDEF", "accent") == "#ABCDEF"
    assert th.raw("pads.height") == "64"
    layout.setTheme("colors.accent", "nie-kolor")
    assert th.property("accent") == lp.DEFAULT_THEME["colors"]["accent"]
    layout.resetTheme()
    assert th.property("scale") == 1.0
    assert th.property("labelFont")  # zawsze jakaś dostępna czcionka


def test_layout_profiles_files(layout, appdata):
    layout.setCardProp(0, "title", "MÓJ PREAMP")
    layout.flush()
    path = appdata / "RootsSoundsystem" / "layouts" / f"{lp.DEFAULT_NAME}.json"
    assert path.is_file()

    assert layout.saveAs("Plener")
    assert layout.profileName == "Plener" and "Plener" in layout.profiles
    assert not layout.canUndo
    layout.setCardProp(0, "title", "PLENER")
    layout.switchProfile(lp.DEFAULT_NAME)
    assert layout.cards[0]["title"] == "MÓJ PREAMP"
    layout.switchProfile("Plener")
    assert layout.cards[0]["title"] == "PLENER"
    layout.deleteProfile()
    assert layout.profileName == lp.DEFAULT_NAME and "Plener" not in layout.profiles

    out = appdata / "eksport.json"
    assert layout.exportTo(QUrl.fromLocalFile(str(out)))
    layout.resetProfile()
    assert layout.cards[0]["title"] == "PREAMP"
    assert layout.importFrom(QUrl.fromLocalFile(str(out)))
    assert layout.cards[0]["title"] == "MÓJ PREAMP"
    assert not layout.importFrom(QUrl.fromLocalFile(str(appdata / "brak.json")))


# --- sesja ---
class _Tap:
    def __init__(self, peak):
        self.peak = peak


class _Chain:
    def __init__(self):
        self.tap_in = _Tap(0.5)
        self.tap_out = _Tap(1.0)
        self.taps = {w: _Tap(0.1) for w in ("sub", "bass", "mid", "top")}

        class XO:
            ways = ("bass", "top")

        self.xo = XO()


def test_session_meters_and_status(app):
    from ui.quick import QmlSession

    s = QmlSession()
    s.set_meters(_Chain(), mic_db=-6.0, mic_gr=3.0)
    levels = s.property("levels")
    assert levels[0] == pytest.approx((20 * __import__("math").log10(0.5) + 60) / 60)
    assert s.property("meterActive") == [True, False, True, False, True, True]
    assert s.property("clips")[5] is True and s.property("clips")[0] is False
    assert s.property("micLevel") == pytest.approx(0.9)
    s.set_meters(None)
    assert 0 < s.property("levels")[0] < levels[0]  # łagodne opadanie
    s.set_status(["SYMULACJA"], "12%")
    assert s.property("chips") == ["SYMULACJA"] and s.property("cpu") == "12%"
    s.set_scenes(["A", "B"], "B")
    assert s.property("scene") == "B"
    s.setProperty("screen", "config")
    assert s.property("screen") == "config"
    s.setProperty("screen", "zly")
    assert s.property("screen") == "config"
    got = []
    s.requested.connect(lambda a, arg: got.append((a, arg)))
    s.requestWith("scene", "A")
    assert got == [("scene", "A")]


def test_session_devices_and_pickup(app):
    from ui.quick import QmlSession

    s = QmlSession()
    hits = []
    s.pickupChanged.connect(lambda: hits.append(1))
    s.set_pickup({"echo.time": 0.12345})
    s.set_pickup({"echo.time": 0.12346})  # bez zmiany po zaokrągleniu – bez sygnału
    assert s.property("pickup") == {"echo.time": 0.123} and len(hits) == 1
    s.set_devices({"music": "CABLE", "mode": "sim"})
    assert s.property("devices")["music"] == "CABLE"


def test_plots_curves(app, store):
    from dsp.graph import SignalChain
    from ui.quick import QmlPlots

    plots = QmlPlots()
    chain = SignalChain(store, 48000, 512, "sim")
    try:
        plots.update_response(chain)
    finally:
        chain.dispose()
    resp, xo = plots.property("response"), plots.property("crossover")
    assert resp[-1]["name"] == "Cały tor" and len(resp) >= 3
    assert xo[-1]["name"] == "Suma" and len(xo) == len(resp)
    pts = resp[-1]["points"]
    assert len(pts) == 256 and all(0 <= q.x() <= 1.0001 and 0 <= q.y() <= 1 for q in pts)
    # suma zwrotnicy przy 1 kHz jest płaska (0 dB) → y = 12 / 60 dla zakresu -48..12
    mid = min(xo[-1]["points"], key=lambda q: abs(q.x() - 1 / 3 * __import__("math").log10(50)))
    assert mid.y() == pytest.approx(12 / 60, abs=0.02)

    class Tap:
        def latest(self, n):
            t = __import__("numpy").arange(n) / 48000
            return 0.5 * __import__("numpy").sin(2 * 3.141592653589793 * 1000 * t)

    fake = _Chain()
    for name in ("tap_out",):
        setattr(fake, name, Tap())
    fake.taps = {w: Tap() for w in ("sub", "bass", "mid", "top")}
    assert not plots.active
    plots.watch(1)
    assert plots.active
    plots.update_spectrum(fake, 48000)
    spec = plots.property("spectrum")
    assert [c["name"] for c in spec] == ["Bass", "Top", "Wyjście"]
    top = min(spec[-1]["points"], key=lambda q: q.y())  # najwyższy punkt widma ≈ 1 kHz
    assert abs(10 ** (top.x() * 3) * 20 - 1000) < 120
    plots.update_spectrum(None, 48000)
    assert plots.property("spectrum") == []
    plots.watch(-5)
    assert not plots.active


def test_midi_label():
    from ui.quick.session import midi_label

    mapping = {"cc:0:19": "iso.g.sub", "note:0:1": "iso.kill.sub", "cc:1:7": "iso.g.sub"}
    shift = {"cc:0:16": "iso.g.sub"}
    assert midi_label(mapping, shift, "iso.g.sub") == "CC 19, CC 7 · kan. 2, SHIFT + CC 16"
    assert midi_label(mapping, {}, "iso.kill.sub") == "Nuta 1"
    assert midi_label(mapping, {}, "echo.time") == ""


def test_tap_tempo(store):
    from ui.dub_actions import TapTempo

    tap = TapTempo(store)
    store.set("echo.sync", 0)
    assert tap.tap(10.0) is None
    assert tap.tap(10.5) == pytest.approx(120.0)
    assert store["echo.bpm"] == pytest.approx(120.0)
    assert store["echo.time"] == pytest.approx(500.0)
    assert tap.tap(20.0) is None  # przerwa > 2 s zaczyna od nowa


# --- QML ---
@pytest.fixture
def desk(app, params, layout):
    from ui.quick import QmlSession
    from ui.quick.view import QuickDesk

    session = QmlSession()
    d = QuickDesk(params, layout, session)
    d.resize(1280, 900)
    d.show()
    app.processEvents()
    yield d
    d.hide()
    d.deleteLater()


def _pump(app, n=4):
    for _ in range(n):
        app.processEvents()


def test_qml_loads_and_runs_without_warnings(app, desk, layout, store):
    msgs = []
    qInstallMessageHandler(lambda _mode, _ctx, msg: msgs.append(msg))
    try:
        assert desk.ok, desk.error_text()
        root = desk.rootObject()
        assert root.property("columns") >= 3
        session = desk.session
        store.set("iso.kill.top", True)
        session.set_meters(_Chain())
        session.setProperty("screen", "config")
        _pump(app)
        session.setProperty("screen", "live")
        session.setProperty("editing", True)
        _pump(app)
        root.selectControl(1, 1)
        _pump(app)
        inspector = root.findChild(type(root), "inspector")
        for tab in ("card", "pads", "theme", "control"):
            inspector.setProperty("tab", tab)
            _pump(app)
        root.selectCard(2)
        root.selectPad(0)
        layout.moveCard(0, 3)
        layout.addControl(0, "view:meters")
        layout.setTheme("scale", 1.4)
        layout.setTheme("knobStyle", "arc")
        layout.setTheme("pads.position", "top")
        _pump(app)
        layout.undo()
        layout.resetProfile()
        _pump(app)

        # menu karty i zmiana rozmiaru przez uchwyt (funkcje hosta)
        root.openCardMenu(0, root)
        _pump(app)
        root.beginResize(0, "wh", root)
        root.cancelResize()
        root.selectCard(0)
        _pump(app)
        from PySide6.QtCore import QEvent, Qt
        from PySide6.QtGui import QKeyEvent

        win = desk.quickWindow()
        title0 = layout.cards[0]["title"]
        for key, mods in ((Qt.Key_Right, Qt.NoModifier), (Qt.Key_Right, Qt.ShiftModifier)):
            QApplication.sendEvent(win, QKeyEvent(QEvent.KeyPress, key, mods))
            _pump(app)
        if layout.cards[1]["title"] == title0:  # fokus klawiatury dostępny w trybie offscreen
            assert layout.cards[1]["span"] == 2
            QApplication.sendEvent(win, QKeyEvent(QEvent.KeyPress, Qt.Key_Z, Qt.ControlModifier))
            QApplication.sendEvent(win, QKeyEvent(QEvent.KeyPress, Qt.Key_Z, Qt.ControlModifier))
            _pump(app)
            assert layout.cards[0]["title"] == title0
        layout.setTheme("tiles", True)
        layout.setCardBox(0, 1, 1, 120)  # stała wysokość mniejsza niż treść → przewijanie w karcie
        _pump(app)
        card = root.cardItem(0)
        assert abs(card.height() - 120) < 1
        root.nudgeHeight(0, 40)
        assert layout.cards[0]["height"] == 160
        root.autoHeight(0)
        assert layout.cards[0]["height"] == 0
        root.beginResize(0, "h", root.cardItem(0))
        root.moveResize(root.cardItem(0), 10, 300)
        root.endResize()
        assert layout.cards[0]["height"] == 300
        session.set_pickup({"echo.time": 0.5, "iso.g.sub": 0.2})
        session.setProperty("screen", "config")
        _pump(app)
        session.setProperty("screen", "live")
        session.setProperty("editing", False)
        desk.resize(700, 900)
        _pump(app)
        assert root.property("columns") <= 2
    finally:
        qInstallMessageHandler(None)
    bad = [m for m in msgs if "qml" in m.lower() or "TypeError" in m or "ReferenceError" in m]
    assert bad == []


# --- okno główne w trybie QML ---
def _make_window(app, tmp_path, monkeypatch):
    from dsp.graph import all_specs
    from engine.params import ParamStore
    from ui.main_window import MainWindow

    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: 0))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: QMessageBox.No))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: 0))
    monkeypatch.setattr(MainWindow, "open_audio_settings", lambda self: None)
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.IniFormat)
    settings.setValue("audio/output", "Speakers")
    win = MainWindow(ParamStore(all_specs()), settings)
    for t in (win.scaler._timer, win._midi_timer):
        t.stop()
    win.show()
    app.processEvents()
    return win


@pytest.fixture
def qml_window(app, tmp_path, monkeypatch):
    win = _make_window(app, tmp_path, monkeypatch)
    yield win
    for t in (win.scaler._timer, win._meter_timer, win._status_timer, win._midi_timer, win._resp_timer):
        t.stop()
    win.midi.close()
    win.engine.stop()
    win.preview.dispose()
    win.hide()
    win.deleteLater()


def test_window_defaults_to_qml_and_switches(qml_window, app):
    win = qml_window
    assert win.quick is not None and win.view == "qml"
    win.set_view("classic")
    assert win.view == "classic"
    win.session.setProperty("editing", True)
    win.set_view("qml")
    win._edit_layout()
    assert win.session.property("editing") is True
    win.set_view("classic")
    assert win.session.property("editing") is False
    win.set_view("qml")
    win._update_meters()
    win._update_status()
    assert win.session.property("chips")[0] == "SYMULACJA"


def test_window_profile_shortcuts(qml_window):
    win, store = qml_window, qml_window.store
    assert win._trigger("iso.kill.sub", True) and store["iso.kill.sub"] is True
    assert win._trigger("iso.kill.sub", False) and store["iso.kill.sub"] is False
    win._trigger("out.mute", True)
    win._trigger("out.mute", False)
    assert store["out.mute"] is True
    assert not win._trigger("echo.time", True)
    # zmiana skrótu w profilu działa od razu
    win.layout_model.setShortcut("out.mute", "Q")
    from PySide6.QtCore import Qt

    assert win._shortcuts[Qt.Key_Q.value] == "out.mute"
    win.session.setProperty("editing", True)
    store.set("echo.throw", False)
    win._trigger("echo.throw", True)
    win.session.setProperty("editing", False)
    assert store["echo.throw"] is False  # zwolnione przy wejściu/wyjściu z edycji


def test_window_audio_from_qml(qml_window, monkeypatch):
    from engine.audio_engine import DeviceInfo

    win = qml_window
    devs = [DeviceInfo(1, "CABLE Output", "WASAPI", 2, 0, 48000), DeviceInfo(3, "Scarlett 4i4", "WASAPI", 0, 4, 48000)]
    win.devices = devs
    win.qaudio.load(devs, win._config())
    a = win.qaudio
    a.setOutput(3)
    a.applyPreset("multi4_mono")
    a.setBlock(1024)
    a.apply()
    assert win.mode == "multi" and win.block == 1024 and win.preview.block == 1024
    assert win.output == 3 and win.store["xo.ways"] == 2
    assert win.channel_map["sub"] == (0, -1)
    assert win.settings.value("audio/output").startswith("Scarlett 4i4")
    assert not a.property("dirty")
    assert win.session.property("devices")["mode"] == "multi"
    a.setMode("sim")
    a.setBlock(512)
    a.apply()
    assert win.mode == "sim" and win.block == 512
    assert win.qplots.property("response")


def test_window_dsp_eq_ir(qml_window, monkeypatch, tmp_path):
    from dsp.graph import DSP_SWITCHES

    win, store = qml_window, qml_window.store
    store.set_many({"echo.enabled": True, "eq.enabled": True, "iso.enabled": False}, source="gui")
    win._on_midi_action("action:dsp_toggle")
    assert not any(store[k] for k in DSP_SWITCHES)
    assert win.session.property("dspOn") == 0 and win.session.property("dspTotal") == len(DSP_SWITCHES)
    win._on_midi_action("action:dsp_toggle")  # przywraca dokładnie poprzedni zestaw
    assert store["echo.enabled"] and store["eq.enabled"] and not store["iso.enabled"]
    assert win.session.property("dspOn") == sum(bool(store[k]) for k in DSP_SWITCHES)

    win._on_qml_request("startup_dsp", "last")
    assert win.settings.value("startup/dsp") == "last" and win.session.property("devices")["startup"] == "last"
    win._on_qml_request("startup_dsp", "clean")
    assert win.settings.value("startup/dsp") == "clean"

    names = [p["value"] for p in win.session.property("eqPresets")]
    assert "Flat" in names
    win._on_qml_request("eq_apply", "Bass Boost")
    assert store["eq.b0"] == 6.0
    win._on_qml_request("eq_save", "Mój dół")
    assert any(p["value"] == "Mój dół" and not p["builtin"] for p in win.session.property("eqPresets"))
    win._on_qml_request("eq_reset", None)
    assert store["eq.b0"] == 0.0
    win._on_qml_request("eq_apply", "Mój dół")
    assert store["eq.b0"] == 6.0
    win._on_qml_request("eq_delete", "Flat")  # wbudowany – zostaje
    win._on_qml_request("eq_delete", "Mój dół")
    names = [p["value"] for p in win.session.property("eqPresets")]
    assert "Flat" in names and "Mój dół" not in names

    import numpy as np
    import soundfile as sf

    ir = tmp_path / "sala.wav"
    sf.write(str(ir), np.exp(-np.arange(4800) / 400.0)[:, None] * np.ones((1, 2)) * 0.5, 48000)
    monkeypatch.setattr("ui.main_window.QFileDialog.getOpenFileName", staticmethod(lambda *a, **k: (str(ir), "")))
    win._on_qml_request("ir_load", None)
    assert win.ir_path == str(ir) and win.session.property("devices")["ir"] == "sala.wav"


def test_window_qml_requests(qml_window):
    win, store = qml_window, qml_window.store
    win._on_qml_request("scene", "Steppers heavy")
    assert store["iso.g.sub"] == 3.0
    assert win.session.property("scene") == "Steppers heavy"
    win._on_qml_request("scene_next", None)
    assert win.session.property("scene") != "Steppers heavy"
    win._on_qml_request("scene", "Neutralny")
    assert store["iso.g.sub"] == 0.0
    store.set("siren.pitch", 777.0)
    win._on_qml_request("siren_store", 2)
    store.set("siren.pitch", 300.0)
    win._on_qml_request("action", "action:siren_mem:2")
    assert store["siren.pitch"] == pytest.approx(777.0)
    assert win.session.hasMemory(2) and not win.session.hasMemory(3)
    win._on_qml_request("classic", None)
    assert win.view == "classic"


@pytest.mark.parametrize("close_first", [True, False])
def test_window_close_without_qml_errors(app, tmp_path, monkeypatch, close_first):
    """Zamknięcie lub zniszczenie okna nie może zostawiać wiązań QML odwołujących się do usuniętych obiektów."""
    from PySide6.QtCore import QCoreApplication, QEvent

    qml_window = _make_window(app, tmp_path, monkeypatch)
    for t in (qml_window._meter_timer, qml_window._status_timer, qml_window._resp_timer):
        t.stop()
    msgs = []
    qInstallMessageHandler(lambda _mode, _ctx, msg: msgs.append(msg))
    try:
        qml_window.session.setProperty("editing", True)
        app.processEvents()
        monkey_quit = QApplication.quit
        QApplication.instance().quit = lambda: None
        try:
            if close_first:
                qml_window.close()
            else:
                qml_window.engine.stop()
                qml_window.midi.close()
        finally:
            QApplication.instance().quit = monkey_quit
        qml_window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        app.processEvents()
    finally:
        qInstallMessageHandler(None)
    bad = [m for m in msgs if "TypeError" in m or "of null" in m]
    assert bad == []
