"""Okno główne: pasek LIVE, stół w dwóch rzędach, ustawienia audio, zasobnik, MIDI."""

from __future__ import annotations

import json

from PySide6.QtCore import QEvent, QObject, QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QKeySequence, QMouseEvent
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QScrollArea,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from dsp.graph import SignalChain, default_channel_map
from dsp.room import ROOM_KEYS
from engine.audio_engine import AudioEngine, EngineConfig, EngineError, find_cable_output, list_devices, sd
from engine.midi import MidiController
from engine.params import ParamStore
from presets import store as preset_store

from .binding import ParamBridge
from .dialogs.audio_settings import AudioSettingsDialog, resolve_saved_devices
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
from .plots import PlotTabs
from .scaling import DeskScaler
from .theme import app_icon

MODES = (("sim", "Symulacja (stereo)"), ("multi", "Multi (wielokanałowe)"))
BLOCKS = (256, 512, 1024)
DEFAULT_FS = 48000
CPU_WARN = 0.8
VB_CABLE_URL = "https://vb-audio.com/Cable/"

MOMENTARY_KEYS = {
    Qt.Key_1: "iso.kill.sub",
    Qt.Key_2: "iso.kill.bass",
    Qt.Key_3: "iso.kill.lowmid",
    Qt.Key_4: "iso.kill.highmid",
    Qt.Key_5: "iso.kill.top",
    Qt.Key_Space: "echo.throw",
    Qt.Key_S: "siren.trigger",
    Qt.Key_D: "spring.crash",
}
MEMORY_KEYS = {Qt.Key_F5: 0, Qt.Key_F6: 1, Qt.Key_F7: 2, Qt.Key_F8: 3}

SHORTCUTS_HELP = """
<b>Skróty klawiszowe</b> (działają, gdy okno jest aktywne):<br><br>
<b>1-5</b> – kill pasm izolatora (sub, bass, low-mid, high-mid, top), aktywny przy przytrzymaniu<br>
<b>Spacja</b> – echo THROW (przytrzymaj)<br>
<b>S</b> – syrena (przytrzymaj)<br>
<b>D</b> – crash sprężyny<br>
<b>T</b> – tap tempo echa<br>
<b>M</b> – mute wyjścia<br>
<b>F5-F8</b> – przywołanie pamięci syreny 1-4 (Ctrl+klik M1-M4 zapisuje)<br><br>
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


class ClickableLabel(QLabel):
    clicked = Signal()

    def mousePressEvent(self, ev: QMouseEvent) -> None:
        self.clicked.emit()
        super().mousePressEvent(ev)


class MainWindow(QMainWindow):
    def __init__(self, store: ParamStore, settings: QSettings):
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
        self._cpu_high = 0
        self._cpu_warned = False
        self._no_input = 0
        self._held_keys: set[str] = set()
        self.ir_path: str | None = settings.value("room/ir_path") or None
        self.preview = SignalChain(store, self.fs, self.block, self.mode)

        self.setWindowTitle("Roots Soundsystem – cyfrowy tor roots and culture")
        self.setWindowIcon(app_icon())
        self._build_central()
        self._build_menus()
        self._build_statusbar()
        self._build_tray()

        self.midi.on_learned = lambda mid, key: self.statusBar().showMessage(f"MIDI: {mid} → {store.specs[key].label}", 4000)
        self.midi.load_json(settings.value("midi/mapping"))
        self.bridge.touched.connect(self._on_touched)

        self._resp_timer = QTimer(self, singleShot=True, interval=60, timeout=self.plots.update_response)
        self.bridge.watch_all(lambda _c: self._resp_timer.start())
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
        self.plots.update_response()
        QApplication.instance().installEventFilter(self)
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

        root = QWidget()
        root_lay = QVBoxLayout(root)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)
        root_lay.addWidget(self.live)
        root_lay.addWidget(self.desk_scroll, 1)
        self.setCentralWidget(root)

        self.room_panel.irFileChosen.connect(self._load_ir)
        self.room_panel.set_ir_path(self.ir_path)

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

        m_audio = mb.addMenu("&Audio")
        m_audio.addAction("Ustawienia audio…", self.open_audio_settings)
        m_audio.addAction("Odśwież urządzenia", self.refresh_devices)
        self.tray_act = QAction("Minimalizuj do zasobnika", self, checkable=True)
        self.tray_act.setChecked(self.settings.value("ui/minimize_to_tray", "true") in (True, "true"))
        m_audio.addAction(self.tray_act)

        self.m_midi = mb.addMenu("&MIDI")
        self.m_midi.aboutToShow.connect(self._populate_midi_menu)

        m_help = mb.addMenu("Pomo&c")
        m_help.addAction("Skróty klawiszowe", lambda: QMessageBox.information(self, "Skróty", SHORTCUTS_HELP))
        m_help.addAction("Instalacja VB-Cable", self._show_vbcable_help)

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
        cfg = dlg.result_config()
        self.devices = dlg.devices
        self.music_in, self.output, self.mic_in = cfg.music_in, cfg.output, cfg.mic_in
        mode_changed = cfg.mode != self.mode or cfg.block != self.block
        self.mode = cfg.mode
        self.block = cfg.block
        self.channel_map = cfg.channel_map
        self.tray_act.setChecked(dlg.tray_box.isChecked())
        self.output_panel.set_mode(self.mode)
        self._update_route_label()
        if mode_changed:
            self._rebuild_preview()
        self._restart_if_running()

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
        self.lbl_state.setText(f"Działa ({self.engine.config.fs} Hz)" if running else "Zatrzymany")

    def _rebuild_preview(self) -> None:
        self.preview.dispose()
        self.preview = SignalChain(self.store, self.fs, self.block, self.mode)
        if self.ir_path:
            try:
                self.preview.room.load_custom(self.ir_path)
            except Exception:
                pass
        self.plots.update_response()

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
        self.live.update_meters(chain)
        if chain is not None:
            self.mic_panel.update_meters(chain.mic_level_db, chain.mic.gr_db, self.engine.stats.mic_latency_ms or None)
        else:
            self.mic_panel.update_meters(-120.0, 0.0, None)
        self.plots.update_spectrum(chain)

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
        key = ev.key()
        pressed = t == QEvent.KeyPress
        if key in MOMENTARY_KEYS:
            param = MOMENTARY_KEYS[key]
            self.store.set(param, pressed, source="key")
            (self._held_keys.add if pressed else self._held_keys.discard)(param)
            return True
        if not pressed:
            return False
        if key == Qt.Key_M:
            self.store.set("out.mute", not self.store["out.mute"], source="key")
            return True
        if key == Qt.Key_T:
            self.findChild(DubPanel).tap_tempo()
            return True
        if key in MEMORY_KEYS:
            self.findChild(DubPanel).recall_memory(MEMORY_KEYS[key])
            return True
        return False

    def _release_held_keys(self) -> None:
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
        s.sync()

    def quit(self) -> None:
        self.close()

    def closeEvent(self, ev) -> None:
        self.save_settings()
        self.engine.stop()
        self.midi.close()
        if self.tray is not None:
            self.tray.hide()
        super().closeEvent(ev)
        QApplication.instance().quit()
