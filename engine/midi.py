"""Sterowanie kontrolerem MIDI: mapowanie (learn i gotowe profile), warstwa SHIFT,
przejęcie wartości (pickup), akcje oraz diody kontrolera (wyjście MIDI).

Komunikaty są odpytywane z timera GUI (`poll`), więc nie ma dodatkowych wątków.
Backend: python-rtmidi, a gdy go brak - pygame (pygame-ce).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

from .midi_profiles import ACTIONS, PROFILES, MidiProfile, profile_for_port
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
        self._toggle_state: dict[str, bool] = {}
        self._shift_held = False
        self._hw: dict[str, float] = {}  # ostatnia pozycja elementu kontrolera (0..1)
        self._latched: set[tuple[str, str]] = set()
        self._led_dirty: set[str] = set()
        self._led_sent: dict[str, int] = {}
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

    def close(self) -> None:
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

    # --- mapowanie i profile ---
    def apply_profile(self, profile: MidiProfile | str) -> None:
        if isinstance(profile, str):
            profile = PROFILES[profile]
        self.profile_name = profile.name
        self.mapping = dict(profile.mapping)
        self.shift_mapping = dict(profile.shift_mapping)
        self.shift_id = profile.shift
        self.feedback = set(profile.feedback)
        self.pickup = profile.pickup
        self._latched.clear()
        self._toggle_state.clear()
        self._mark_all_leds()

    def arm(self, key: str) -> None:
        if self.learning:
            self.armed_key = key

    def clear(self) -> None:
        self.leds_off()
        self.mapping.clear()
        self.shift_mapping.clear()
        self.shift_id = None
        self.feedback.clear()
        self.profile_name = None
        self._latched.clear()

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
        if data.get("version") != 2:  # stary format: płaski słownik element -> parametr
            self.mapping = {k: v for k, v in data.items() if self._valid_target(v)}
            return
        self.mapping = {k: v for k, v in (data.get("mapping") or {}).items() if self._valid_target(v)}
        self.shift_mapping = {k: v for k, v in (data.get("shift_mapping") or {}).items() if self._valid_target(v)}
        self.shift_id = data.get("shift") or None
        self.feedback = set(data.get("feedback") or ())
        self.pickup = bool(data.get("pickup", True))
        self.profile_name = data.get("profile") or None

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
            except Exception:
                self.close()
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
            if self.on_learned:
                self.on_learned(mid, key)
            return
        target = self.target_for(mid)
        if target is None:
            self._hw[mid] = value
            return
        pressed = value >= 0.5
        was = self._toggle_state.get(mid, False)
        self._toggle_state[mid] = pressed
        if target in ACTIONS:
            if pressed and not was and self.on_action:
                self.on_action(target)
            return
        spec = self.store.specs[target]
        if spec.kind == "bool":
            if spec.momentary:
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
        except Exception:
            self.out_port = None

    def flush_leds(self) -> None:
        if self.out_port is None:
            self._led_dirty.clear()
            return
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
