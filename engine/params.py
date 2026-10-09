"""Rejestr parametrów wspólny dla GUI, presetów, MIDI i toru DSP."""

from __future__ import annotations

import math
import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

Listener = Callable[[dict[str, Any], Any], None]


@dataclass(frozen=True)
class ParamSpec:
    key: str
    label: str
    default: Any
    min: float = 0.0
    max: float = 1.0
    unit: str = ""
    kind: str = "float"  # float | bool | choice | int
    scale: str = "lin"  # lin | log
    choices: tuple[str, ...] = ()
    step: float = 0.0
    scene: bool = True
    momentary: bool = False
    kill_floor: float | None = None  # wartość (dB) pokazywana jako KILL i oznaczająca ciszę

    def clamp(self, value: Any) -> Any:
        if self.kind == "bool":
            return bool(value)
        if self.kind == "choice":
            idx = int(round(float(value)))
            return max(0, min(len(self.choices) - 1, idx))
        v = float(value)
        if math.isnan(v):
            v = float(self.default)
        v = max(self.min, min(self.max, v))
        if self.step > 0:
            v = self.min + round((v - self.min) / self.step) * self.step
            v = max(self.min, min(self.max, v))
        if self.kind == "int":
            return int(round(v))
        return v

    def to_norm(self, value: Any) -> float:
        if self.kind == "bool":
            return 1.0 if value else 0.0
        if self.kind == "choice":
            n = max(1, len(self.choices) - 1)
            return int(value) / n
        v = float(value)
        if self.scale == "log":
            return math.log(v / self.min) / math.log(self.max / self.min)
        return (v - self.min) / (self.max - self.min)

    def from_norm(self, norm: float) -> Any:
        norm = max(0.0, min(1.0, float(norm)))
        if self.kind == "bool":
            return norm >= 0.5
        if self.kind == "choice":
            return self.clamp(norm * (len(self.choices) - 1))
        if self.scale == "log":
            return self.clamp(self.min * (self.max / self.min) ** norm)
        return self.clamp(self.min + norm * (self.max - self.min))

    def format(self, value: Any) -> str:
        if self.kind == "bool":
            return "ON" if value else "OFF"
        if self.kind == "choice":
            return self.choices[int(value)]
        v = float(value)
        if self.kill_floor is not None and v <= self.kill_floor:
            return "KILL"
        if self.unit == "Hz":
            return f"{v / 1000:.2f} kHz" if v >= 1000 else f"{v:.0f} Hz"
        if self.unit == "ms":
            return f"{v:.0f} ms" if v >= 10 else f"{v:.1f} ms"
        if self.unit == "dB":
            return f"{v:+.1f} dB"
        if self.unit == "%":
            return f"{v * 100:.0f}%"
        if self.kind == "int":
            return f"{int(v)} {self.unit}".strip()
        return f"{v:.2f} {self.unit}".strip()


class ParamStore:
    """Wątkowo bezpieczny magazyn wartości.

    Słuchacze dostają słownik zmienionych wartości; są wywoływani pod blokadą,
    więc konfiguracja modułów DSP z różnych wątków (GUI, MIDI) jest serializowana.
    """

    def __init__(self, specs: Iterable[ParamSpec]):
        self.specs: dict[str, ParamSpec] = {}
        for s in specs:
            if s.key in self.specs:
                raise ValueError(f"Zduplikowany parametr: {s.key}")
            self.specs[s.key] = s
        self._values: dict[str, Any] = {k: s.clamp(s.default) for k, s in self.specs.items()}
        self._lock = threading.RLock()
        self._listeners: list[tuple[str, Listener]] = []

    def __contains__(self, key: str) -> bool:
        return key in self._values

    def __getitem__(self, key: str) -> Any:
        return self._values[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._values.get(key, default)

    def subscribe(self, fn: Listener, prefix: str = "") -> None:
        with self._lock:
            self._listeners.append((prefix, fn))

    def unsubscribe(self, fn: Listener) -> None:
        with self._lock:
            self._listeners = [(p, f) for p, f in self._listeners if f != fn]

    def set(self, key: str, value: Any, source: Any = None) -> bool:
        return bool(self.set_many({key: value}, source))

    def set_many(self, values: dict[str, Any], source: Any = None) -> dict[str, Any]:
        with self._lock:
            changed: dict[str, Any] = {}
            for key, value in values.items():
                spec = self.specs.get(key)
                if spec is None:
                    continue
                v = spec.clamp(value)
                if self._values[key] != v:
                    self._values[key] = v
                    changed[key] = v
            if changed:
                self._notify(changed, source)
            return changed

    def reset(self, keys: Iterable[str] | None = None, source: Any = None) -> None:
        keys = list(self.specs) if keys is None else list(keys)
        self.set_many({k: self.specs[k].default for k in keys if k in self.specs}, source)

    def snapshot(self, scene_only: bool = True) -> dict[str, Any]:
        with self._lock:
            return {
                k: v
                for k, v in self._values.items()
                if not scene_only or (self.specs[k].scene and not self.specs[k].momentary)
            }

    def load(self, values: dict[str, Any], source: Any = None) -> None:
        self.set_many(values, source)

    def _notify(self, changed: dict[str, Any], source: Any) -> None:
        for prefix, fn in list(self._listeners):
            if prefix:
                sub = {k: v for k, v in changed.items() if k.startswith(prefix)}
                if not sub:
                    continue
            else:
                sub = changed
            fn(sub, source)
