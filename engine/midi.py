"""Sterowanie kontrolerem MIDI: mapowanie (learn i gotowe profile), warstwa SHIFT,
przejęcie wartości (pickup), akcje oraz diody kontrolera (wyjście MIDI, z animacją powitalną
po podłączeniu – `engine/midi_intro.py`).

Komunikaty są odpytywane z timera GUI (`poll`), więc nie ma dodatkowych wątków.
Backend: python-rtmidi, a gdy go brak - pygame (pygame-ce).
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

from .midi_intro import LedIntro, intro_frames, led_columns
from .midi_profiles import ACTIONS, PROFILES, MidiProfile, Strip, profile_for_port
from .params import ParamStore

try:
    import mido  # type: ignore
except Exception:
    mido = None

BACKENDS = ("mido.backends.rtmidi", "mido.backends.pygame")
PICKUP_TOLERANCE = 0.02  # znormalizowana odległość, przy której gałka „łapie” wartość
SOURCE = "midi"


def _init_backend() -> str | None:
    if mido is None:
        return None
    for name in BACKENDS:
        try:
            mido.set_backend(name, load=True)
            mido.get_input_names()
            return name
        except Exception:
            continue
    return None


def _port_base(name: str) -> str:
    """Nazwa portu bez numeru dopisywanego przez Windows ("MIDI Mix 0" -> "midi mix")."""
    return re.sub(r"\s+\d+$", "", name).strip().lower()


def match_output(input_name: str, outputs: list[str]) -> str | None:
    if input_name in outputs:
        return input_name
    base = _port_base(input_name)
    for out in outputs:
        if _port_base(out) == base:
            return out
    return None


def element_name(mid: str) -> str:
    """Czytelna nazwa elementu kontrolera: „CC 19”, „Nuta 1 · kan. 2”, „Pitch bend”."""
    kind, _, rest = mid.partition(":")
    chan, _, num = rest.partition(":")
    ch = f" · kan. {int(chan) + 1}" if chan.isdigit() and chan != "0" else ""
    if kind == "cc":
        return f"CC {num}{ch}"
    if kind == "note":
        return f"Nuta {num}{ch}"
    if kind == "pw":
        return "Pitch bend"
    return mid


def _note_message(channel: int, note: int, velocity: int) -> Any:
    if mido is not None:
        return mido.Message("note_on", channel=channel, note=note, velocity=velocity)
    return SimpleNamespace(type="note_on", channel=channel, note=note, velocity=velocity)


class MidiController:
    def __init__(self, store: ParamStore):
        self.store = store
        self.backend = _init_backend()
        self.port = None
        self.out_port = None
        self.port_name: str | None = None
        self.profile_name: str | None = None
        self.mapping: dict[str, str] = {}
        self.shift_mapping: dict[str, str] = {}
        self.shift_id: str | None = None
        self.feedback: set[str] = set()
        self.pickup = True
        self.learning = False
        self.armed_key: str | None = None
        self.on_learned: Callable[[str, str], None] | None = None
        self.on_action: Callable[[str], None] | None = None
        self.on_status: Callable[[str], None] | None = None  # "connected" / "disconnected"
        self.activity: dict[str, int] = {}  # licznik komunikatów na element (podświetlenie na mapie)
        self.last_event: tuple[str, float] | None = None
        self.revision = 0  # rośnie przy każdej zmianie mapy, profilu lub połączenia (odświeżanie podglądu)
        self._toggle_state: dict[str, bool] = {}
        self._held: dict[str, str] = {}  # wciśnięte przyciski chwilowe: element -> cel z chwili wciśnięcia
        self._shift_held = False
        self._hw: dict[str, float] = {}  # ostatnia pozycja elementu kontrolera (0..1)
        self._latched: set[tuple[str, str]] = set()
        self._led_dirty: set[str] = set()
        self._led_sent: dict[str, int] = {}
        self.intro_enabled = True  # animacja powitalna diod po podłączeniu (ustawienie okna midi/intro)
        self.clock: Callable[[], float] = time.monotonic
        self._intro: LedIntro | None = None
        store.subscribe(self._on_params)

    # --- porty ---
    @property
    def available(self) -> bool:
        return self.backend is not None

    @property
    def shift_held(self) -> bool:
        return self._shift_held

    def inputs(self) -> list[str]:
        if not self.available:
            return []
        try:
            return list(mido.get_input_names())
        except Exception:
            return []

    def outputs(self) -> list[str]:
        if not self.available:
            return []
        try:
            return list(mido.get_output_names())
        except Exception:
            return []

    def open(self, name: str, auto_profile: bool = True) -> None:
        self.close()
        self.port = mido.open_input(name)
        self.port_name = name
        out = match_output(name, self.outputs())
        if out is not None:
            try:
                self.out_port = mido.open_output(out)
            except Exception:
                self.out_port = None
        if auto_profile and not self.mapping:
            profile = profile_for_port(name)
            if profile is not None:
                self.apply_profile(profile)
        self._mark_all_leds()
        self.play_intro()
        self.revision += 1

    def ensure_connected(self, saved: str | None) -> bool:
        """Pilnuje połączenia (wołane co kilka sekund): wykrywa odłączenie, ponownie łączy z zapisanym
        portem – także pod innym numerem nadanym przez Windows – a gdy nic nie zapisano (None), łączy
        ze znanym kontrolerem (np. MIDImix). Pusty napis = świadomie bez kontrolera."""
        if not self.available:
            return False
        names = self.inputs()
        if self.port is not None:
            if any(_port_base(n) == _port_base(self.port_name or "") for n in names):
                return True
            self.close()
            self._notify("disconnected")
            return False
        if saved == "":
            return False
        if saved:
            candidates = [n for n in names if n == saved] + [n for n in names if n != saved and _port_base(n) == _port_base(saved)]
        else:
            candidates = [n for n in names if profile_for_port(n) is not None]
        for name in candidates:
            try:
                self.open(name)
            except Exception:
                self.close()
                continue
            self._notify("connected")
            return True
        return False

    def _notify(self, status: str) -> None:
        if self.on_status:
            self.on_status(status)

    def close(self) -> None:
        self._release_held()
        self._intro = None  # diody animacji należą do `feedback`, więc gasi je leds_off
        if self.out_port is not None:
            self.leds_off()
            try:
                self.out_port.close()
            except Exception:
                pass
        if self.port is not None:
            try:
                self.port.close()
            except Exception:
                pass
        self.port = None
        self.out_port = None
        self.port_name = None
        self._shift_held = False
        self.revision += 1

    # --- mapowanie i profile ---
    def apply_profile(self, profile: MidiProfile | str) -> None:
        if isinstance(profile, str):
            profile = PROFILES[profile]
        self.stop_intro()
        self._release_held()
        self.profile_name = profile.name
        self.mapping = dict(profile.mapping)
        self.shift_mapping = dict(profile.shift_mapping)
        self.shift_id = profile.shift
        self.feedback = set(profile.feedback)
        self.pickup = profile.pickup
        self._latched.clear()
        self._mark_all_leds()
        self.revision += 1

    @property
    def layout(self) -> tuple[Strip, ...]:
        """Układ fizyczny bieżącego profilu (do podglądu mapy); pusty dla mapowania z samego learn."""
        profile = PROFILES.get(self.profile_name or "")
        return profile.layout if profile else ()

    def assign(self, mid: str, target: str, shift: bool = False) -> None:
        """Przypisuje element kontrolera do parametru lub akcji (bez trybu learn)."""
        if not self._valid_target(target):
            raise KeyError(target)
        (self.shift_mapping if shift else self.mapping)[mid] = target
        self._latched = {lk for lk in self._latched if lk[0] != mid}
        self._mark_led(mid)
        self.revision += 1

    def unassign(self, mid: str, shift: bool = False) -> None:
        (self.shift_mapping if shift else self.mapping).pop(mid, None)
        self._latched = {lk for lk in self._latched if lk[0] != mid}
        self._mark_led(mid)
        self.revision += 1

    def hw_position(self, mid: str) -> float | None:
        """Ostatnia pozycja elementu (0..1) albo None, gdy jeszcze nic nie wysłał."""
        return self._hw.get(mid)

    def hw_positions(self) -> dict[str, float]:
        return dict(self._hw)

    def arm(self, key: str) -> None:
        if self.learning:
            self.armed_key = key

    def clear(self) -> None:
        self.stop_intro()
        self._release_held()
        self.leds_off()
        self.mapping.clear()
        self.shift_mapping.clear()
        self.shift_id = None
        self.feedback.clear()
        self.profile_name = None
        self._latched.clear()
        self.revision += 1

    def _valid_target(self, target: Any) -> bool:
        return isinstance(target, str) and (target in self.store.specs or target in ACTIONS)

    def to_json(self) -> str:
        return json.dumps(
            {
                "version": 2,
                "profile": self.profile_name,
                "mapping": self.mapping,
                "shift_mapping": self.shift_mapping,
                "shift": self.shift_id,
                "feedback": sorted(self.feedback),
                "pickup": self.pickup,
            },
            ensure_ascii=False,
        )

    def load_json(self, text: str | None) -> None:
        if not text:
            return
        try:
            data = json.loads(text)
        except ValueError:
            return
        if not isinstance(data, dict):
            return
        self.stop_intro()
        self._release_held()
        self.leds_off()  # nowa mapa może mieć inne diody (albo żadnych)
        if data.get("version") != 2:  # stary format: płaski słownik element -> parametr (cała mapa, bez SHIFT)
            data = {"version": 2, "mapping": data, "pickup": self.pickup}
        self.mapping = {k: v for k, v in (data.get("mapping") or {}).items() if self._valid_target(v)}
        self.shift_mapping = {k: v for k, v in (data.get("shift_mapping") or {}).items() if self._valid_target(v)}
        self.shift_id = data.get("shift") or None
        self.feedback = set(data.get("feedback") or ())
        self.pickup = bool(data.get("pickup", True))
        self.profile_name = data.get("profile") or None
        self._latched.clear()
        self._mark_all_leds()
        self.revision += 1

    def target_for(self, mid: str) -> str | None:
        if self._shift_held and mid in self.shift_mapping:
            return self.shift_mapping[mid]
        return self.mapping.get(mid)

    # --- odbiór ---
    def poll(self) -> None:
        if self.port is not None:
            try:
                for msg in self.port.iter_pending():
                    self.handle(msg)
            except Exception:  # port zniknął (np. wyjęty kabel) – watchdog połączy ponownie
                self.close()
                self._notify("disconnected")
        self.flush_leds()

    @staticmethod
    def message_id(msg: Any) -> tuple[str | None, float | None]:
        t = msg.type
        if t == "control_change":
            return f"cc:{msg.channel}:{msg.control}", msg.value / 127.0
        if t in ("note_on", "note_off"):
            vel = msg.velocity if t == "note_on" else 0
            return f"note:{msg.channel}:{msg.note}", 1.0 if vel > 0 else 0.0
        if t == "pitchwheel":
            return f"pw:{msg.channel}", (msg.pitch + 8192) / 16383.0
        return None, None

    def handle(self, msg: Any) -> None:
        mid, value = self.message_id(msg)
        if mid is None:
            return
        self.activity[mid] = self.activity.get(mid, 0) + 1
        self.last_event = (mid, value)
        if mid == self.shift_id:
            self._shift_held = value >= 0.5
            return
        if self.learning and self.armed_key:
            layer = self.shift_mapping if self._shift_held else self.mapping
            layer[mid] = self.armed_key
            self._hw[mid] = value
            self._latched.add((mid, self.armed_key))  # świadome przypisanie: steruje od razu
            self._mark_led(mid)
            key, self.armed_key = self.armed_key, None
            self.revision += 1
            if self.on_learned:
                self.on_learned(mid, key)
            return
        target = self.target_for(mid)
        pressed = value >= 0.5
        if not pressed and mid in self._held:
            # puszczenie zwalnia cel z chwili wciśnięcia – SOLO mogło zostać puszczone lub wciśnięte w trakcie
            target = self._held.pop(mid)
        if target is None:
            self._hw[mid] = value
            return
        was = self._toggle_state.get(mid, False)
        self._toggle_state[mid] = pressed
        if target in ACTIONS:
            if pressed and not was and self.on_action:
                self.on_action(target)
            return
        spec = self.store.specs[target]
        if spec.kind == "bool":
            if spec.momentary:
                if pressed:
                    self._held[mid] = target
                self.store.set(target, pressed, source=SOURCE)
            elif pressed and not was:
                self.store.set(target, not self.store[target], source=SOURCE)
            self._mark_led(mid)
            return
        if self._accept(mid, target, value, spec):
            self.store.set(target, spec.from_norm(value), source=SOURCE)

    # --- przejęcie wartości ---
    def _accept(self, mid: str, target: str, value: float, spec) -> bool:
        prev = self._hw.get(mid)
        self._hw[mid] = value
        if not self.pickup:
            return True
        lk = (mid, target)
        if lk in self._latched:
            return True
        cur = spec.to_norm(self.store[target])
        crossed = prev is not None and min(prev, value) - 1e-9 <= cur <= max(prev, value) + 1e-9
        if abs(value - cur) <= PICKUP_TOLERANCE or crossed:
            self._latched.add(lk)
            return True
        return False

    def pickup_pending(self) -> dict[str, float]:
        """Parametry czekające na przejęcie: klucz -> pozycja elementu kontrolera (0..1)."""
        out: dict[str, float] = {}
        for layer in (self.mapping, self.shift_mapping):
            for mid, target in layer.items():
                spec = self.store.specs.get(target)
                if spec is None or spec.kind == "bool" or mid not in self._hw:
                    continue
                if (mid, target) not in self._latched and self.target_for(mid) == target:
                    out[target] = self._hw[mid]
        return out

    def _on_params(self, changed: dict[str, Any], source: Any) -> None:
        keys = set(changed)
        if source != SOURCE:
            self._latched = {lk for lk in self._latched if lk[1] not in keys}
        for mid in self.feedback:
            if self.mapping.get(mid) in keys:
                self._led_dirty.add(mid)

    # --- diody ---
    def _mark_led(self, mid: str) -> None:
        if mid in self.feedback:
            self._led_dirty.add(mid)

    def _mark_all_leds(self) -> None:
        self._led_sent.clear()
        self._led_dirty |= self.feedback

    def _led_value(self, mid: str) -> int:
        target = self.mapping.get(mid)
        spec = self.store.specs.get(target) if target else None
        return 127 if spec is not None and spec.kind == "bool" and self.store[target] else 0

    def _send_led(self, mid: str, velocity: int) -> None:
        kind, ch, num = mid.split(":")
        if kind != "note":
            return
        try:
            self.out_port.send(_note_message(int(ch), int(num), velocity))
            self._led_sent[mid] = velocity
        except Exception:  # bez diod dalej; port zamykamy, żeby nie wisiał otwarty w sterowniku
            port, self.out_port = self.out_port, None
            try:
                port.close()
            except Exception:
                pass

    def _release_held(self) -> None:
        """Puszcza parametry trzymane przyciskami chwilowymi, gdy port znika albo zmienia się mapa –
        puszczenia już nie będzie, a syrena, FX PANIC czy DRY CUT zostałyby włączone na stałe."""
        held, self._held = self._held, {}
        self._toggle_state.clear()  # przełącznik wciśnięty w tej chwili zadziała przy pierwszym naciśnięciu
        for target in held.values():
            self.store.set(target, False, source=SOURCE)

    # --- animacja powitalna diod ---
    @property
    def intro_running(self) -> bool:
        return self._intro is not None

    def play_intro(self) -> bool:
        """Odtwarza (od początku) animację powitalną diod; False, gdy wyłączona albo brak diod/portu.

        Klatki idą z `flush_leds` (timer okna), sterowanie działa normalnie, a zmiany diod czekają
        do końca animacji – wtedy wszystkie diody dostają stan z `ParamStore`."""
        self._intro = None
        if not self.intro_enabled or self.out_port is None:
            return False
        frames = intro_frames(led_columns(self.layout, self.feedback))
        if not frames:
            return False
        self._intro = LedIntro(frames)
        return True

    def stop_intro(self) -> None:
        """Przerywa animację: gasi zapalone przez nią diody i odświeża stan wszystkich diod."""
        intro, self._intro = self._intro, None
        if intro is None:
            return
        if self.out_port is not None:
            for mid in sorted(intro.mids):
                if self._led_sent.get(mid):
                    self._send_led(mid, 0)
                if self.out_port is None:
                    break
        self._mark_all_leds()

    def set_intro(self, on: bool) -> None:
        """Włącza/wyłącza animację; włączenie od razu ją pokazuje (podgląd na kontrolerze)."""
        self.intro_enabled = bool(on)
        if self.intro_enabled:
            self.play_intro()
        else:
            self.stop_intro()

    def _step_intro(self) -> bool:
        """Wysyła bieżącą klatkę (tylko zmienione diody); False, gdy animacja właśnie się skończyła."""
        frame = self._intro.frame(self.clock())
        if frame is None:
            self._intro = None
            self._mark_all_leds()  # pełne odświeżenie stanu z ParamStore
            return False
        for mid, v in frame.items():
            if self._led_sent.get(mid) != v:
                self._send_led(mid, v)
                if self.out_port is None:
                    self._intro = None
                    break
        return True

    def flush_leds(self) -> None:
        if self.out_port is None:
            self._intro = None
            self._led_dirty.clear()
            return
        if self._intro is not None and self._step_intro():
            return  # w trakcie animacji zmiany diod zbierają się w _led_dirty
        if not self._led_dirty:
            return
        dirty, self._led_dirty = self._led_dirty, set()
        for mid in sorted(dirty):
            v = self._led_value(mid)
            if self._led_sent.get(mid) != v:
                self._send_led(mid, v)
            if self.out_port is None:
                return

    def leds_off(self) -> None:
        if self.out_port is None:
            return
        for mid in sorted(self.feedback):
            self._send_led(mid, 0)
            if self.out_port is None:
                return
