"""Okno główne: interfejs QML (LIVE/KONFIGURACJA) lub stół klasyczny, ustawienia audio, zasobnik, MIDI."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QSettings, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QActionGroup, QKeySequence, QMouseEvent
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QScrollArea,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from dsp.graph import DSP_SWITCHES, SignalChain, bypass_values, default_channel_map
from dsp.room import ROOM_KEYS
from engine.audio_engine import AudioEngine, EngineConfig, EngineError, find_cable_output, list_devices, sd
from engine.midi import MidiController
from engine.midi_profiles import PROFILES
from engine.params import ParamStore
from presets import store as preset_store
from version import APP_NAME, VERSION

from . import audio_config, layout_profile
from .binding import ParamBridge
from .dialogs.audio_settings import AudioSettingsDialog, resolve_saved_devices
from .dub_actions import has_siren_memory
from .panels import (
    CrossoverPanel,
    DubPanel,
    EQ12Panel,
    IsolatorPanel,
    LivePanel,
    MicPanel,
    OutputPanel,
    PreampPanel,
    RoomPanel,
)
from .panels.dub import N_MEMORIES
from .plots import PlotTabs
from .quick import LayoutModel, QmlAudio, QmlParams, QmlPlots, QmlSession
from .quick.session import midi_label
from .scaling import DeskScaler
from .theme import app_icon
from .widgets import PresetBar

PRESET_OPS = ("apply", "save", "delete", "reset")

MODES = (("sim", "Symulacja (stereo)"), ("multi", "Multi (wielokanałowe)"))
BLOCKS = (256, 512, 1024)
DEFAULT_FS = 48000
CPU_WARN = 0.8
VB_CABLE_URL = "https://vb-audio.com/Cable/"

VIEWS = ("qml", "classic")

SHORTCUTS_HELP = """
<b>Skróty klawiszowe</b> (działają, gdy okno jest aktywne; w nowym interfejsie można je zmienić w trybie ✎ UKŁAD):<br><br>
<b>1-5</b> – kill pasm izolatora (sub, bass, low-mid, high-mid, top), aktywny przy przytrzymaniu<br>
<b>Spacja</b> – echo THROW (przytrzymaj)<br>
<b>S</b> – syrena (przytrzymaj)<br>
<b>D</b> – crash sprężyny<br>
<b>T</b> – tap tempo echa<br>
<b>M</b> – mute wyjścia<br>
<b>F5-F8</b> – przywołanie pamięci syreny 1-4 (Ctrl+klik M1-M4 zapisuje)<br>
<b>Ctrl+L</b> – nowy interfejs (QML), <b>Ctrl+K</b> – stół klasyczny<br><br>
Przyciski chwilowe: lewy przycisk myszy = przytrzymanie, prawy = zatrzaśnięcie.<br>
Pokrętła: przeciągaj w pionie lub kółkiem, Shift = precyzyjnie, dwuklik = wartość domyślna.
"""

VB_CABLE_HELP = f"""
<b>Nie znaleziono urządzenia „CABLE Output” (VB-Cable).</b><br><br>
Aplikacja przechwytuje dźwięk systemu przez wirtualny kabel audio:<br>
1. Pobierz i zainstaluj darmowy sterownik <a href="{VB_CABLE_URL}">VB-Cable</a> (jako administrator), uruchom ponownie komputer.<br>
2. W ustawieniach dźwięku Windows ustaw <b>CABLE Input</b> jako domyślne urządzenie odtwarzania.<br>
3. W <b>Ustawieniach audio</b> wybierz <b>CABLE Output</b> jako wejście muzyki i swoje słuchawki/głośniki (lub kartę wielokanałową) jako wyjście.<br><br>
Szczegóły w README.md.
"""


def about_text() -> str:
    """Treść okna „O programie”: wersja aplikacji i bibliotek, przydatna przy zgłaszaniu problemów."""
    import platform

    import numpy
    import PySide6
    from PySide6.QtCore import qVersion

    return (
        f"<b>{APP_NAME} {VERSION}</b><br>Cyfrowy tor soundsystemu roots and culture.<br><br>"
        f"Python {platform.python_version()} · PySide6 {PySide6.__version__} (Qt {qVersion()}) · "
        f"numpy {numpy.__version__}<br>Windows {platform.version()}"
    )


class ClickableLabel(QLabel):
    clicked = Signal()

    def mousePressEvent(self, ev: QMouseEvent) -> None:
        self.clicked.emit()
        super().mousePressEvent(ev)


class MainWindow(QMainWindow):
    def __init__(self, store: ParamStore, settings: QSettings, startup_checks: bool = True):
        super().__init__()
        self.store = store
        self.settings = settings
        self.bridge = ParamBridge(store)
        self.engine = AudioEngine(store)
        self.midi = MidiController(store)
        self.fs = DEFAULT_FS
        self.block = int(settings.value("audio/block", 512))
        if self.block not in BLOCKS:
            self.block = 512
        self.mode = settings.value("audio/mode", "sim")
        if self.mode not in dict(MODES):
            self.mode = "sim"
        self.devices = []
        self.music_in = None
        self.output = None
        self.mic_in = None
        self.channel_map = self._load_channel_map()
        self.sim_mirror = settings.value("audio/sim_mirror", "false") in (True, "true")
        self.music_offset = int(settings.value("audio/music_offset", 0) or 0)
        self.mic_channel = int(settings.value("audio/mic_channel", 0) or 0)
        self._cpu_high = 0
        self._cpu_warned = False
        self._no_input = 0
        self._held_keys: set[str] = set()
        self.ir_path: str | None = settings.value("room/ir_path") or None
        self.preview = SignalChain(store, self.fs, self.block, self.mode)
        self.qparams = QmlParams(self.bridge, self)
        self.layout_model = LayoutModel(store.specs, settings.value("ui/layout_profile") or layout_profile.DEFAULT_NAME, self)
        self.session = QmlSession(self)
        self.qplots = QmlPlots(self)
        self.qaudio = QmlAudio(store, list_devices, self)
        self.qaudio.applyRequested.connect(self._apply_audio_draft)
        self._dsp_memory = self._saved_switches()
        self._spectrum_tick = 0
        self.session.requested.connect(self._on_qml_request)
        self.session.midi_lookup = lambda key: midi_label(self.midi.mapping, self.midi.shift_mapping, key)
        self.session.memory_lookup = lambda i: has_siren_memory(self.settings, i)
        self.quick = None
        self._shortcuts: dict[int, str] = self.layout_model.shortcut_map()
        self.layout_model.shortcutsChanged.connect(lambda: setattr(self, "_shortcuts", self.layout_model.shortcut_map()))

        self.setWindowTitle(f"{APP_NAME} {VERSION} – cyfrowy tor roots and culture")
        self.setWindowIcon(app_icon())
        self._build_central()
        self._build_menus()
        self._build_statusbar()
        self._build_tray()

        self.midi.on_learned = lambda mid, key: self.statusBar().showMessage(f"MIDI: {mid} → {store.specs[key].label}", 4000)
        self.midi.on_action = self._on_midi_action
        self._siren_mem = -1
        self.midi.load_json(settings.value("midi/mapping"))
        self.bridge.touched.connect(self._on_touched)

        self._resp_timer = QTimer(self, singleShot=True, interval=60, timeout=self._update_responses)
        self.bridge.watch_all(lambda _c: self._resp_timer.start())
        self.bridge.watch_all(self._on_params_changed)
        self._meter_timer = QTimer(self, interval=33, timeout=self._update_meters)
        self._meter_timer.start()
        self._status_timer = QTimer(self, interval=500, timeout=self._update_status)
        self._status_timer.start()
        self._midi_timer = QTimer(self, interval=5, timeout=self.midi.poll)
        self._midi_timer.start()

        self.refresh_devices()
        self.output_panel.set_mode(self.mode)
        if self.ir_path:
            self._load_ir(self.ir_path, quiet=True)
        self._restore_geometry()
        self._sync_scene()
        self._update_session_status()
        self._update_dsp_state()
        self._sync_presets()
        self._update_responses()
        QApplication.instance().installEventFilter(self)
        if startup_checks:
            QTimer.singleShot(300, self._startup_checks)

        midi_port = settings.value("midi/port")
        if midi_port and midi_port in self.midi.inputs():
            try:
                self.midi.open(midi_port)
            except Exception:
                pass

    # --- budowa UI ---
    def _build_central(self) -> None:
        b = self.bridge
        self.live = LivePanel(b)
        self.live.startToggled.connect(self._on_start_toggled)
        self.live.settingsClicked.connect(self.open_audio_settings)
        self.live.sceneActivated.connect(self._apply_scene)
        self.live.saveSceneClicked.connect(self._save_scene)
        self.live.deleteSceneClicked.connect(self._delete_scene)
        self.scene_combo = self.live.scene_combo
        self.start_btn = self.live.start_btn

        self.mic_panel = MicPanel(b)
        self.room_panel = RoomPanel(b)
        self.output_panel = OutputPanel(b)
        self.dub_panel = DubPanel(b, self.settings)
        self.plots = PlotTabs(lambda: self.preview, lambda: self.engine.config.fs if self.engine.config else self.fs)
        self.plots.setMinimumWidth(240)
        self.plots.setMaximumHeight(340)

        row1 = QWidget()
        r1 = QHBoxLayout(row1)
        r1.setContentsMargins(4, 2, 4, 2)
        r1.setSpacing(6)
        for panel in (PreampPanel(b), self.mic_panel, self.dub_panel):
            r1.addWidget(panel, 0, Qt.AlignTop)
        r1.addWidget(self.plots, 1)

        row2 = QWidget()
        r2 = QHBoxLayout(row2)
        r2.setContentsMargins(4, 2, 4, 2)
        r2.setSpacing(6)
        for panel in (IsolatorPanel(b), CrossoverPanel(b), EQ12Panel(b), self.room_panel, self.output_panel):
            r2.addWidget(panel, 0, Qt.AlignTop)
        r2.addStretch(1)

        self.desk = QWidget()
        desk_lay = QVBoxLayout(self.desk)
        desk_lay.setContentsMargins(0, 0, 0, 0)
        desk_lay.setSpacing(2)
        desk_lay.addWidget(row1)
        desk_lay.addWidget(row2)

        self.desk_scroll = QScrollArea()
        self.desk_scroll.setWidget(self.desk)
        self.desk_scroll.setWidgetResizable(True)
        self.scaler = DeskScaler(self.desk_scroll.viewport(), self.desk)

        classic = QWidget()
        root_lay = QVBoxLayout(classic)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)
        root_lay.addWidget(self.live)
        root_lay.addWidget(self.desk_scroll, 1)
        self.view_stack = QStackedWidget()
        self.view_stack.addWidget(classic)
        self.setCentralWidget(self.view_stack)

        self.room_panel.irFileChosen.connect(self._load_ir)
        self.room_panel.set_ir_path(self.ir_path)
        self.scene_combo.currentIndexChanged.connect(lambda _i: self._sync_scene())
        self._build_quick()

    def _build_quick(self) -> None:
        """Nowy interfejs QML; przy błędzie ładowania zostaje stół klasyczny."""
        try:
            from .quick.view import QuickDesk

            desk = QuickDesk(self.qparams, self.layout_model, self.session, self.qplots, self.qaudio)
        except Exception as exc:  # brak modułów QtQuick w paczce itp.
            print(f"Interfejs QML niedostępny: {exc}")
            return
        if not desk.ok:
            print("Błędy QML:\n" + desk.error_text())
            desk.deleteLater()
            return
        self.quick = desk
        self.view_stack.addWidget(desk)
        self.session.editingChanged.connect(self._release_held_keys)
        self.layout_model.message.connect(lambda text: self.statusBar().showMessage(text, 3000))

    @property
    def view(self) -> str:
        return "qml" if self.quick is not None and self.view_stack.currentWidget() is self.quick else "classic"

    def set_view(self, view: str) -> None:
        if view == "qml" and self.quick is None:
            view = "classic"
        if view == "classic":
            self.session.editing = False
            self.layout_model.flush()
        self.view_stack.setCurrentWidget(self.quick if view == "qml" else self.view_stack.widget(0))
        if view == "classic":
            QTimer.singleShot(0, self.scaler.apply)
        for act in self.view_group.actions():
            act.setChecked(act.data() == view)

    def _build_menus(self) -> None:
        mb = self.menuBar()
        m_file = mb.addMenu("&Plik")
        m_file.addAction("Zapisz scenę…", self._save_scene)
        m_file.addAction("Wczytaj IR miejsca…", self.room_panel._choose_ir)
        m_file.addSeparator()
        quit_act = QAction("Zakończ", self)
        quit_act.setShortcut(QKeySequence.Quit)
        quit_act.triggered.connect(self.quit)
        m_file.addAction(quit_act)

        m_view = mb.addMenu("&Widok")
        self.view_group = QActionGroup(self)
        for view, text, key in (("qml", "Nowy interfejs (QML)", "Ctrl+L"), ("classic", "Stół klasyczny (Widgets)", "Ctrl+K")):
            act = QAction(text, self, checkable=True)
            act.setData(view)
            act.setShortcut(QKeySequence(key))
            act.setEnabled(view == "classic" or self.quick is not None)
            act.triggered.connect(lambda _=False, v=view: self.set_view(v))
            self.view_group.addAction(act)
            m_view.addAction(act)
        m_view.addSeparator()
        m_view.addAction("Edycja układu…", self._edit_layout)

        m_audio = mb.addMenu("&Audio")
        m_audio.addAction("Ustawienia audio…", self.open_audio_settings)
        m_audio.addAction("Odśwież urządzenia", self.refresh_devices)
        self.tray_act = QAction("Minimalizuj do zasobnika", self, checkable=True)
        self.tray_act.setChecked(self.settings.value("ui/minimize_to_tray", "true") in (True, "true"))
        m_audio.addAction(self.tray_act)
        self.clean_start_act = QAction("Start z czystym torem (moduły DSP wyłączone)", self, checkable=True)
        self.clean_start_act.setChecked(self.settings.value("startup/dsp", "clean") != "last")
        self.clean_start_act.toggled.connect(lambda on: self._set_startup_mode("clean" if on else "last"))
        m_audio.addAction(self.clean_start_act)
        m_audio.addAction("DSP: wszystko wyłącz / przywróć", lambda: self._on_midi_action("action:dsp_toggle"))

        self.m_midi = mb.addMenu("&MIDI")
        self.m_midi.aboutToShow.connect(self._populate_midi_menu)

        m_help = mb.addMenu("Pomo&c")
        m_help.addAction("Skróty klawiszowe", lambda: QMessageBox.information(self, "Skróty", SHORTCUTS_HELP))
        m_help.addAction("Instalacja VB-Cable", self._show_vbcable_help)
        m_help.addSeparator()
        m_help.addAction("O programie", self._show_about)

    def _populate_midi_menu(self) -> None:
        m = self.m_midi
        m.clear()
        if not self.midi.available:
            act = m.addAction("MIDI niedostępne (zainstaluj mido + python-rtmidi lub pygame-ce)")
            act.setEnabled(False)
            return
        ports = m.addMenu("Port wejściowy")
        none = ports.addAction("— brak —")
        none.setCheckable(True)
        none.setChecked(self.midi.port_name is None)
        none.triggered.connect(lambda: self._open_midi(None))
        for name in self.midi.inputs():
            a = ports.addAction(name)
            a.setCheckable(True)
            a.setChecked(name == self.midi.port_name)
            a.triggered.connect(lambda _=False, n=name: self._open_midi(n))
        learn = m.addAction("Tryb learn (porusz kontrolkę, potem kontroler)")
        learn.setCheckable(True)
        learn.setChecked(self.midi.learning)
        learn.toggled.connect(self._set_midi_learn)
        profiles = m.addMenu("Profil kontrolera")
        for pname in PROFILES:
            a = profiles.addAction(pname)
            a.setCheckable(True)
            a.setChecked(pname == self.midi.profile_name)
            a.triggered.connect(lambda _=False, n=pname: self._apply_midi_profile(n))
        pickup = m.addAction("Przejęcie wartości (pickup) – bez skoków po zmianie sceny")
        pickup.setCheckable(True)
        pickup.setChecked(self.midi.pickup)
        pickup.toggled.connect(lambda on: setattr(self.midi, "pickup", on))
        leds = m.addAction("Diody kontrolera: " + ("aktywne" if self.midi.out_port is not None else "brak portu wyjściowego"))
        leds.setEnabled(False)
        m.addAction(f"Wyczyść mapowanie ({len(self.midi.mapping)})", self.midi.clear)

    def _build_statusbar(self) -> None:
        sb = self.statusBar()
        self.lbl_route = ClickableLabel("Urządzenia: —")
        self.lbl_route.setToolTip("Kliknij, aby otworzyć ustawienia audio")
        self.lbl_route.clicked.connect(self.open_audio_settings)
        self.lbl_cpu = QLabel("CPU: —")
        self.lbl_buf = QLabel("Niedobory: 0 | Przepełnienia: 0")
        self.lbl_lat = QLabel("Latencja: —")
        self.lbl_err = QLabel("")
        self.lbl_err.setStyleSheet("color: #d62828;")
        self.lbl_state = QLabel("Zatrzymany")
        sb.addWidget(self.lbl_route)
        for w in (self.lbl_state, self.lbl_cpu, self.lbl_buf, self.lbl_lat, self.lbl_err):
            sb.addPermanentWidget(w)

    def _build_tray(self) -> None:
        self.tray = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(app_icon(), self)
        self.tray.setToolTip("Roots Soundsystem")
        menu = QMenu()
        menu.addAction("Pokaż", self._show_from_tray)
        menu.addAction("Start / Stop", lambda: self.start_btn.toggle())
        menu.addSeparator()
        menu.addAction("Zakończ", self.quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self._show_from_tray() if reason == QSystemTrayIcon.Trigger else None)
        self.tray.show()

    # --- urządzenia ---
    def refresh_devices(self) -> None:
        self.devices = list_devices()
        self.music_in, self.output, self.mic_in = resolve_saved_devices(self.devices, self.settings)
        self._update_route_label()
        self.qaudio.load(self.devices, self._config())

    def _device(self, index):
        return next((d for d in self.devices if d.index == index), None)

    def _device_name(self, index, fallback="—") -> str:
        d = self._device(index)
        if d is None:
            return fallback
        return d.name.split("(")[0].strip() or d.name

    def _update_route_label(self) -> None:
        mode = "Symulacja" if self.mode == "sim" else "Multi"
        src = self._device_name(self.music_in)
        dst = self._device_name(self.output)
        self.lbl_route.setText(f"{src} → {dst} | {mode} | {self.block}")

    def open_audio_settings(self) -> None:
        dlg = AudioSettingsDialog(
            self,
            self.bridge,
            self.settings,
            self.devices,
            self.mode,
            self.block,
            self.channel_map,
            self.tray_act.isChecked(),
            self.fs,
        )
        if dlg.exec() != AudioSettingsDialog.Accepted:
            return
        dlg.persist()
        self.devices = dlg.devices
        self.tray_act.setChecked(dlg.tray_box.isChecked())
        self._apply_config(dlg.result_config())

    def _apply_config(self, cfg: EngineConfig) -> None:
        """Nowa konfiguracja audio (z okna Audio lub karty QML): przebudowa podglądu i restart silnika."""
        self.music_in, self.output, self.mic_in = cfg.music_in, cfg.output, cfg.mic_in
        mode_changed = cfg.mode != self.mode or cfg.block != self.block
        self.mode = cfg.mode
        self.block = cfg.block
        self.channel_map = dict(cfg.channel_map)
        self.sim_mirror, self.music_offset, self.mic_channel = cfg.sim_mirror, cfg.music_offset, cfg.mic_channel
        self.output_panel.set_mode(self.mode)
        self._update_route_label()
        if mode_changed:
            self._rebuild_preview()
        self._restart_if_running()
        self._update_session_status()
        self.qaudio.load(self.devices, self._config())

    def _apply_audio_draft(self) -> None:
        a = self.qaudio
        cfg = a.config(self.fs)
        self.devices = list(a.devices)
        audio_config.persist(self.settings, cfg, self.devices)
        if a.pending_ways is not None:
            self.store.set("xo.ways", a.pending_ways, source="gui")
        self._apply_config(cfg)
        self.session.toast.emit("Zastosowano ustawienia audio")

    # --- silnik ---
    def _config(self) -> EngineConfig:
        return EngineConfig(
            music_in=self.music_in,
            output=self.output,
            mic_in=self.mic_in,
            mode=self.mode,
            fs=self.fs,
            block=self.block,
            channel_map=self.channel_map,
            sim_mirror=self.sim_mirror,
            music_offset=self.music_offset,
            mic_channel=self.mic_channel,
        )

    def _on_start_toggled(self, on: bool) -> None:
        if on:
            if not self.start_engine():
                self.live.set_running(False)
        else:
            self.engine.stop()
        self._update_start_button()

    def start_engine(self) -> bool:
        if self.mode == "multi":
            from dsp.crossover import WAYS_BY_COUNT
            from dsp.graph import validate_channel_map

            ways = WAYS_BY_COUNT[(2, 3, 4)[int(self.store["xo.ways"])]]
            dev = self._device(self.output)
            nch = dev.max_out if dev else 0
            probs = validate_channel_map(self.channel_map, ways, nch)
            if probs:
                QMessageBox.critical(self, "Tryb Multi", "Popraw mapowanie kanałów:\n\n" + "\n".join(probs))
                self.open_audio_settings()
                return False
            ans = QMessageBox.warning(
                self,
                "Tryb Multi",
                "Drogi trafią bezpośrednio na wzmacniacze kolumn.\n\n"
                "Skręć wzmacniacze, sprawdź mapowanie kanałów i progi limiterów.\n"
                "Wyjście startuje z łagodnym narastaniem głośności. Kontynuować?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if ans != QMessageBox.Yes:
                return False
        cfg = self._config()
        try:
            self.engine.start(cfg)
        except EngineError as exc:
            dev = self._device(cfg.output)
            alt = int(dev.default_fs) if dev else DEFAULT_FS
            if alt != cfg.fs:
                cfg.fs = alt
                try:
                    self.engine.start(cfg)
                except EngineError as exc2:
                    QMessageBox.critical(self, "Błąd audio", str(exc2))
                    return False
            else:
                QMessageBox.critical(self, "Błąd audio", str(exc))
                return False
        if self.ir_path and self.engine.chain is not None:
            try:
                self.engine.chain.room.load_custom(self.ir_path)
            except Exception:
                pass
        self._cpu_warned = False
        return True

    def _restart_if_running(self, *_):
        if self.engine.running:
            self.engine.stop()
            if not self.start_engine():
                self.live.set_running(False)
        self._update_start_button()

    def _update_start_button(self) -> None:
        running = self.engine.running
        self.live.set_running(running)
        self.session.set_running(running)
        self.lbl_state.setText(f"Działa ({self.engine.config.fs} Hz)" if running else "Zatrzymany")
        self._update_session_status()

    def _rebuild_preview(self) -> None:
        self.preview.dispose()
        self.preview = SignalChain(self.store, self.fs, self.block, self.mode)
        if self.ir_path:
            try:
                self.preview.room.load_custom(self.ir_path)
            except Exception:
                pass
        self._update_responses()

    def _update_responses(self) -> None:
        self.plots.update_response()
        self.qplots.update_response(self.preview)

    def _load_channel_map(self) -> dict:
        raw = self.settings.value("audio/channel_map")
        if raw:
            try:
                return {k: tuple(v) for k, v in json.loads(raw).items()}
            except (TypeError, ValueError):
                pass
        return default_channel_map()

    # --- IR ---
    def _load_ir(self, path: str, quiet: bool = False) -> None:
        try:
            self.preview.room.load_custom(path)
            if self.engine.chain is not None:
                self.engine.chain.room.load_custom(path)
        except Exception as exc:
            if not quiet:
                QMessageBox.critical(self, "IR", f"Nie udało się wczytać pliku IR:\n{exc}")
            return
        self.ir_path = path
        self.settings.setValue("room/ir_path", path)
        self.room_panel.set_ir_path(path)
        if not quiet:
            self.store.set("room.preset", ROOM_KEYS.index("custom"), source="gui")

    # --- sceny ---
    def _reload_scenes(self, select: str | None = None) -> None:
        self.live.reload_scenes(select)
        self._sync_scene()

    def _sync_scene(self) -> None:
        combo = self.scene_combo
        names = [combo.itemData(i) for i in range(combo.count())]
        self.session.set_scenes(names, combo.currentData() or "")

    def _apply_scene(self, idx: int) -> None:
        name = self.scene_combo.itemData(idx)
        try:
            self.store.set_many(preset_store.scene_values(self.store, name), source="gui")
        except Exception as exc:
            QMessageBox.critical(self, "Scena", f"Nie udało się wczytać sceny:\n{exc}")

    def _save_scene(self) -> None:
        name, ok = QInputDialog.getText(self, "Zapisz scenę", "Nazwa sceny:")
        if ok and name.strip():
            preset_store.save_scene(name.strip(), self.store)
            self._reload_scenes(name.strip())

    def _delete_scene(self) -> None:
        name = self.scene_combo.currentData()
        if name is None:
            return
        if dict(preset_store.list_scenes()).get(name, True):
            QMessageBox.information(self, "Scena", "Wbudowanych scen nie można usunąć.")
            return
        preset_store.delete_scene(name)
        self._reload_scenes()

    # --- MIDI ---
    def _open_midi(self, name: str | None) -> None:
        try:
            if name is None:
                self.midi.close()
            else:
                self.midi.open(name)
            self.settings.setValue("midi/port", name or "")
        except Exception as exc:
            QMessageBox.critical(self, "MIDI", f"Nie udało się otworzyć portu:\n{exc}")

    def _apply_midi_profile(self, name: str) -> None:
        self.midi.apply_profile(name)
        self.statusBar().showMessage(f"MIDI: wczytano profil {name}", 4000)

    def _on_midi_action(self, action: str) -> None:
        if action in ("action:scene_prev", "action:scene_next"):
            n = self.scene_combo.count()
            if n == 0:
                return
            step = -1 if action == "action:scene_prev" else 1
            idx = (self.scene_combo.currentIndex() + step) % n
            self.scene_combo.setCurrentIndex(idx)
            self._apply_scene(idx)
            self.statusBar().showMessage(f"Scena: {self.scene_combo.itemText(idx)}", 2000)
        elif action == "action:tap":
            self.dub_panel.tap_tempo()
        elif action == "action:siren_mem_next":
            self._siren_mem = (self._siren_mem + 1) % N_MEMORIES
            self.dub_panel.recall_memory(self._siren_mem)
            self.statusBar().showMessage(f"Syrena: pamięć M{self._siren_mem + 1}", 2000)
        elif action == "action:start_stop":
            self.start_btn.click()
        elif action == "action:dsp_toggle":
            self._toggle_dsp()
        elif action.startswith("action:siren_mem:"):
            i = int(action.rsplit(":", 1)[1])
            self._siren_mem = i
            self.dub_panel.recall_memory(i)
            self.statusBar().showMessage(f"Syrena: pamięć M{i + 1}", 2000)

    # --- polecenia z interfejsu QML ---
    def _on_qml_request(self, action: str, arg) -> None:
        if action == "start_stop":
            self.start_btn.click()
        elif action in ("scene_prev", "scene_next"):
            self._on_midi_action(f"action:{action}")
        elif action == "scene":
            idx = self.scene_combo.findData(arg)
            if idx >= 0:
                self.scene_combo.setCurrentIndex(idx)
                self._apply_scene(idx)
        elif action == "scene_save":
            self._save_scene()
        elif action == "audio":
            self.open_audio_settings()
            self._update_session_status()
        elif action == "ir_load":
            path, _ = QFileDialog.getOpenFileName(self, "Wybierz odpowiedź impulsową", "", "Pliki audio (*.wav *.flac *.aiff *.ogg)")
            if path:
                self._load_ir(path)
                self._update_session_status()
        elif action.partition("_")[0] in preset_store.PRESET_KINDS and action.partition("_")[2] in PRESET_OPS:
            kind, _, op = action.partition("_")
            self._preset_request(kind, op, arg)
        elif action == "startup_dsp":
            self.clean_start_act.setChecked(str(arg) != "last")
        elif action == "classic":
            self.set_view("classic")
        elif action == "action":
            self._on_midi_action(str(arg))
        elif action == "siren_store":
            self.dub_panel.store_memory(int(arg))
            self.session.toast.emit(f"Zapisano pamięć syreny M{int(arg) + 1}")
        elif action == "midi_learn":
            self._learn_param(str(arg))
        elif action == "layout_export":
            path, _ = QFileDialog.getSaveFileName(self, "Eksport układu", f"{self.layout_model.profile['name']}.json", "Układ (*.json)")
            if path:
                self.layout_model.exportTo(QUrl.fromLocalFile(path))
        elif action == "layout_import":
            path, _ = QFileDialog.getOpenFileName(self, "Import układu", "", "Układ (*.json)")
            if path:
                self.layout_model.importFrom(QUrl.fromLocalFile(path))

    # --- czysty tor / moduły DSP ---
    def _saved_switches(self) -> dict[str, bool]:
        """Moduły włączone w ostatniej sesji – do przywrócenia przyciskiem DSP po czystym starcie."""
        try:
            data = json.loads(self.settings.value("state/params") or "{}")
        except (TypeError, ValueError):
            data = {}
        return {k: bool(data.get(k, self.store.specs[k].default)) for k in DSP_SWITCHES}

    def _toggle_dsp(self) -> None:
        current = {k: bool(self.store[k]) for k in DSP_SWITCHES}
        if any(current.values()):
            self._dsp_memory = current
            self.store.set_many(bypass_values(), source="gui")
            self.session.toast.emit("DSP wyłączone – czysty tor")
        else:
            restore = self._dsp_memory if any(self._dsp_memory.values()) else {k: True for k in DSP_SWITCHES}
            self.store.set_many(restore, source="gui")
            self.session.toast.emit("DSP przywrócone")

    def _on_params_changed(self, changed: dict) -> None:
        if any(k in DSP_SWITCHES for k in changed):
            self._update_dsp_state()

    def _update_dsp_state(self) -> None:
        self.session.set_dsp(sum(bool(self.store[k]) for k in DSP_SWITCHES), len(DSP_SWITCHES))

    def _set_startup_mode(self, mode: str) -> None:
        self.settings.setValue("startup/dsp", mode)
        self._update_session_status()

    def _preset_request(self, kind: str, op: str, arg) -> None:
        """Presety EQ i syreny z QML: apply / save / delete / reset (wspólne `PRESET_KINDS`)."""
        pk = preset_store.PRESET_KINDS[kind]
        name = str(arg or "").strip()
        if op == "apply" and name:
            self.store.set_many(pk.values(self.store, name), source="gui")
        elif op == "save" and name:
            pk.save(name, self.store)
            self._sync_presets()
            self.session.toast.emit(f"Zapisano {pk.title} „{name}”")
        elif op == "delete" and name:
            if pk.is_builtin(name):
                self.session.toast.emit("Wbudowanych presetów nie można usunąć")
            else:
                pk.delete(name)
                self._sync_presets()
        elif op == "reset":
            self.store.reset(list(pk.keys), source="gui")

    def _sync_presets(self) -> None:
        for kind, pk in preset_store.PRESET_KINDS.items():
            self.session.set_presets(kind, pk.list())
        for bar in self.findChildren(PresetBar):
            bar.reload(bar.combo.currentData())

    def _learn_param(self, key: str) -> None:
        if not self.midi.available or key not in self.store.specs:
            self.session.toast.emit("MIDI niedostępne" if not self.midi.available else "Learn działa tylko dla parametrów")
            return
        self.midi.learning = True
        self.midi.arm(key)
        self.session.toast.emit(f"MIDI learn: porusz elementem kontrolera dla „{self.store.specs[key].label}”")

    def _edit_layout(self) -> None:
        if self.quick is None:
            QMessageBox.information(self, "Układ", "Interfejs QML jest niedostępny.")
            return
        self.set_view("qml")
        self.session.editing = True

    def _set_midi_learn(self, on: bool) -> None:
        self.midi.learning = on
        self.midi.armed_key = None
        self.statusBar().showMessage("MIDI learn: porusz kontrolkę w aplikacji, potem element kontrolera" if on else "MIDI learn wyłączony", 5000)

    def _on_touched(self, key: str) -> None:
        if self.midi.learning:
            self.midi.arm(key)
            self.statusBar().showMessage(f"MIDI learn: porusz elementem kontrolera dla „{self.store.specs[key].label}”", 5000)

    # --- timery ---
    def _update_meters(self) -> None:
        chain = self.engine.chain if self.engine.running else None
        if self.view == "qml":
            if chain is not None:
                self.session.set_meters(chain, chain.mic_level_db, chain.mic.gr_db)
            else:
                self.session.set_meters(None)
            self.session.set_pickup(self.midi.pickup_pending() if self.midi.pickup else {})
            self._spectrum_tick = (self._spectrum_tick + 1) % 2
            if self.qplots.active and self._spectrum_tick == 0:
                self.qplots.update_spectrum(chain, self.engine.config.fs if chain is not None else self.fs)
            return
        self.live.update_meters(chain)
        if chain is not None:
            self.mic_panel.update_meters(chain.mic_level_db, chain.mic.gr_db, self.engine.stats.mic_latency_ms or None)
        else:
            self.mic_panel.update_meters(-120.0, 0.0, None)
        self.plots.update_spectrum(chain)

    def _update_session_status(self) -> None:
        eng = self.engine
        if self.mode == "multi":
            dev = self._device(self.output)
            mode = f"MULTI · {dev.max_out} kan." if dev else "MULTI"
        else:
            mode = "SYMULACJA"
        fs = eng.config.fs if eng.running and eng.config else self.fs
        chips = [mode, f"{fs / 1000:g} kHz · {self.block}"]
        cpu = ""
        if eng.running:
            chips.append(f"{eng.stats.latency_ms:.0f} ms")
            cpu = f"{eng.stats.cpu_load * 100:.0f}%"
        self.session.set_status(chips, cpu)
        self.session.set_devices({
            "music": self._device_name(self.music_in),
            "output": self._device_name(self.output),
            "mic": self._device_name(self.mic_in) if self.mic_in is not None else "— (bez mikrofonu)",
            "mode": self.mode,
            "block": self.block,
            "blocks": list(BLOCKS),
            "fs": fs,
            "running": eng.running,
            "multi": self.mode == "multi",
            "route": self.lbl_route.text(),
            "ir": Path(self.ir_path).name if self.ir_path else "",
            "startup": "last" if self.settings.value("startup/dsp", "clean") == "last" else "clean",
        })

    def _update_status(self) -> None:
        eng = self.engine
        if eng.device_lost():
            eng.stop()
            self._update_start_button()
            self.refresh_devices()
            QMessageBox.warning(self, "Urządzenie audio", "Utracono lub zmieniono urządzenie audio. Silnik zatrzymano – wybierz urządzenia i uruchom ponownie.")
            self.open_audio_settings()
            return
        st = eng.stats
        self._update_session_status()
        if not eng.running:
            self.lbl_cpu.setText("CPU: —")
            self.lbl_lat.setText("Latencja: —")
            return
        self._no_input = 0 if st.primed else self._no_input + 1
        if self._no_input >= 4:
            self.statusBar().showMessage("Brak danych z wejścia muzyki – sprawdź, czy wybrano CABLE Output i czy coś gra", 2000)
        self.lbl_cpu.setText(f"CPU: {st.cpu_load * 100:.0f}% (szczyt {st.cpu_peak * 100:.0f}%)")
        self.lbl_buf.setText(f"Niedobory: {st.underruns} | Przepełnienia: {st.overflows}")
        self.lbl_lat.setText(f"Latencja: {st.latency_ms:.0f} ms")
        if st.callback_errors:
            self.lbl_err.setText(f"Błędy DSP: {st.callback_errors}")
            self.lbl_err.setToolTip(st.last_error)
        self._cpu_high = self._cpu_high + 1 if st.cpu_load > CPU_WARN else 0
        if self._cpu_high >= 4:
            self.statusBar().showMessage("Przekroczony budżet CPU: zwiększ blok lub wyłącz akustykę miejsca (splot)", 5000)
            if not self._cpu_warned:
                self._cpu_warned = True
                QMessageBox.warning(
                    self, "Obciążenie CPU",
                    "Przetwarzanie zajmuje ponad 80% czasu bloku – mogą pojawić się trzaski.\n\n"
                    "Zwiększ rozmiar bloku (np. 1024), wybierz krótszą akustykę (Plener) lub wyłącz splot miejsca.",
                )

    def _startup_checks(self) -> None:
        if sd is None:
            QMessageBox.critical(self, "Audio", "Nie można załadować biblioteki sounddevice (PortAudio).")
            return
        missing_cable = find_cable_output(self.devices) is None
        first_run = not self.settings.value("audio/output")
        saved_out_missing = self.settings.value("audio/output") and self.output is None
        if missing_cable:
            self.statusBar().showMessage("Brak VB-Cable (CABLE Output) – zobacz Pomoc → Instalacja VB-Cable")
            self._show_vbcable_help()
        if first_run or saved_out_missing:
            self.open_audio_settings()

    def _show_about(self) -> None:
        QMessageBox.about(self, f"O programie {APP_NAME}", about_text())

    def _show_vbcable_help(self) -> None:
        box = QMessageBox(self)
        box.setWindowTitle("VB-Cable")
        box.setTextFormat(Qt.RichText)
        box.setTextInteractionFlags(Qt.TextBrowserInteraction)
        box.setText(VB_CABLE_HELP)
        settings_btn = box.addButton("Otwórz ustawienia audio", QMessageBox.ActionRole)
        box.addButton(QMessageBox.Ok)
        box.exec()
        if box.clickedButton() is settings_btn:
            self.open_audio_settings()

    # --- klawiatura ---
    def eventFilter(self, obj: QObject, ev: QEvent) -> bool:
        t = ev.type()
        if t not in (QEvent.KeyPress, QEvent.KeyRelease) or ev.isAutoRepeat():
            return False
        if QApplication.activeWindow() is not self:
            return False
        fw = QApplication.focusWidget()
        if isinstance(fw, (QLineEdit, QAbstractSpinBox)) or (isinstance(fw, QComboBox) and fw.isEditable()):
            return False
        if ev.modifiers() & (Qt.ControlModifier | Qt.AltModifier):
            return False
        if self.session.editing:
            return False
        target = self._shortcuts.get(ev.key())
        if target is None:
            return False
        return self._trigger(target, t == QEvent.KeyPress)

    def _trigger(self, target: str, pressed: bool) -> bool:
        """Skrót klawiszowy: akcja (przy naciśnięciu), przełącznik chwilowy (przytrzymanie) lub zwykły (przełącz)."""
        if target.startswith("action:"):
            if pressed:
                self._on_midi_action(target)
            return True
        spec = self.store.specs.get(target)
        if spec is None or spec.kind != "bool":
            return False
        if layout_profile.is_hold(spec):
            self.store.set(target, pressed, source="key")
            (self._held_keys.add if pressed else self._held_keys.discard)(target)
        elif pressed:
            self.store.set(target, not self.store[target], source="key")
        return True

    def _release_held_keys(self, *_args) -> None:
        for param in list(self._held_keys):
            self.store.set(param, False, source="key")
        self._held_keys.clear()

    # --- okno / zasobnik ---
    def changeEvent(self, ev: QEvent) -> None:
        if ev.type() == QEvent.ActivationChange and not self.isActiveWindow():
            self._release_held_keys()
        if ev.type() == QEvent.WindowStateChange and self.isMinimized() and self.tray is not None and self.tray_act.isChecked():
            QTimer.singleShot(0, self.hide)
            self.tray.showMessage("Roots Soundsystem", "Aplikacja działa w zasobniku systemowym.", QSystemTrayIcon.Information, 2000)
        super().changeEvent(ev)

    def _show_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _restore_geometry(self) -> None:
        geo = self.settings.value("ui/geometry")
        if geo is not None:
            self.restoreGeometry(geo)
        else:
            self.resize(1600, 980)
        view = self.settings.value("ui/view", "qml")
        self.set_view(view if view in VIEWS else "qml")
        QTimer.singleShot(0, self.scaler.apply)

    def save_settings(self) -> None:
        s = self.settings
        s.setValue("ui/geometry", self.saveGeometry())
        s.setValue("ui/minimize_to_tray", "true" if self.tray_act.isChecked() else "false")
        s.setValue("audio/mode", self.mode)
        s.setValue("audio/block", self.block)
        s.setValue("audio/channel_map", json.dumps(self.channel_map))
        s.setValue("state/params", json.dumps(self.store.snapshot(scene_only=True)))
        s.setValue("midi/mapping", self.midi.to_json())
        s.setValue("ui/view", self.view)
        s.setValue("ui/layout_profile", self.layout_model.profile["name"])
        self.layout_model.flush()
        s.sync()

    def quit(self) -> None:
        self.close()

    def closeEvent(self, ev) -> None:
        self.save_settings()
        if self.quick is not None:
            self.quick.shutdown()
        self.engine.stop()
        self.midi.close()
        if self.tray is not None:
            self.tray.hide()
        super().closeEvent(ev)
        QApplication.instance().quit()
