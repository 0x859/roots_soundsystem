"""Sterowanie kontrolerem MIDI z trybem learn.

Komunikaty są odpytywane z timera GUI (`poll`), więc nie ma dodatkowych wątków.
Backend: python-rtmidi, a gdy go brak - pygame (pygame-ce).
"""

from __future__ import annotations

import json
from typing import Any, Callable

from .params import ParamStore

try:
    import mido  # type: ignore
except Exception:
    mido = None

BACKENDS = ("mido.backends.rtmidi", "mido.backends.pygame")


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


class MidiController:
    def __init__(self, store: ParamStore):
        self.store = store
        self.backend = _init_backend()
        self.port = None
        self.port_name: str | None = None
        self.mapping: dict[str, str] = {}
        self.learning = False
        self.armed_key: str | None = None
        self.on_learned: Callable[[str, str], None] | None = None
        self._toggle_state: dict[str, bool] = {}

    @property
    def available(self) -> bool:
        return self.backend is not None

    def inputs(self) -> list[str]:
        if not self.available:
            return []
        try:
            return list(mido.get_input_names())
        except Exception:
            return []

    def open(self, name: str) -> None:
        self.close()
        self.port = mido.open_input(name)
        self.port_name = name

    def close(self) -> None:
        if self.port is not None:
            try:
                self.port.close()
            except Exception:
                pass
        self.port = None
        self.port_name = None

    def arm(self, key: str) -> None:
        if self.learning:
            self.armed_key = key

    def clear(self) -> None:
        self.mapping.clear()

    def to_json(self) -> str:
        return json.dumps(self.mapping)

    def load_json(self, text: str | None) -> None:
        if not text:
            return
        try:
            data = json.loads(text)
        except ValueError:
            return
        self.mapping = {k: v for k, v in data.items() if v in self.store.specs}

    def poll(self) -> None:
        if self.port is None:
            return
        try:
            for msg in self.port.iter_pending():
                self.handle(msg)
        except Exception:
            self.close()

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
        if self.learning and self.armed_key:
            self.mapping[mid] = self.armed_key
            key, self.armed_key = self.armed_key, None
            if self.on_learned:
                self.on_learned(mid, key)
            return
        key = self.mapping.get(mid)
        if key is None:
            return
        spec = self.store.specs[key]
        if spec.kind == "bool":
            pressed = value >= 0.5
            if spec.momentary:
                self.store.set(key, pressed, source="midi")
            elif pressed and not self._toggle_state.get(mid, False):
                self.store.set(key, not self.store[key], source="midi")
            self._toggle_state[mid] = pressed
        else:
            self.store.set(key, spec.from_norm(value), source="midi")
