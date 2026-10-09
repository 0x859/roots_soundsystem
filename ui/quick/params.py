"""Parametry `ParamStore` wystawione do QML jako obiekty z właściwościami (wiązania reaktywne)."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtQml import QQmlEngine

from engine.params import ParamSpec

from ..binding import ParamBridge
from ..layout_profile import ACTIONS, VIEWS, allowed_types, is_hold, target_label


class QmlParam(QObject):
    """Jeden parametr: QML wiąże `value`, `norm` i `text`; zmiany idą przez `ParamBridge` (MIDI learn)."""

    changed = Signal()

    def __init__(self, bridge: ParamBridge, spec: ParamSpec, parent: QObject):
        super().__init__(parent)
        self._bridge = bridge
        self._spec = spec
        self._value = bridge.get(spec.key)

    def _update(self, value: Any) -> None:
        if value != self._value:
            self._value = value
            self.changed.emit()

    def _set(self, value: Any) -> None:
        self._bridge.set(self._spec.key, value)

    # --- stałe ---
    @Property(str, constant=True)
    def key(self) -> str:
        return self._spec.key

    @Property(str, constant=True)
    def label(self) -> str:
        return self._spec.label

    @Property(str, constant=True)
    def kind(self) -> str:
        return self._spec.kind

    @Property(str, constant=True)
    def unit(self) -> str:
        return self._spec.unit

    @Property("QVariantList", constant=True)
    def choices(self) -> list[str]:
        return list(self._spec.choices)

    @Property(bool, constant=True)
    def hold(self) -> bool:
        return is_hold(self._spec)

    @Property(float, constant=True)
    def originNorm(self) -> float:
        s = self._spec
        if s.kind in ("float", "int") and s.min < 0 < s.max:
            return float(s.to_norm(0.0))
        return 0.0

    @Property(float, constant=True)
    def defaultNorm(self) -> float:
        return float(self._spec.to_norm(self._spec.clamp(self._spec.default)))

    # --- zmienne ---
    @Property("QVariant", notify=changed)
    def value(self) -> Any:
        return self._value

    @Property(float, notify=changed)
    def norm(self) -> float:
        return float(self._spec.to_norm(self._value))

    @Property(str, notify=changed)
    def text(self) -> str:
        return self._spec.format(self._value)

    @Property(bool, notify=changed)
    def on(self) -> bool:
        return bool(self._value)

    @Property(int, notify=changed)
    def index(self) -> int:
        return int(self._value) if self._spec.kind == "choice" else 0

    @Property(bool, notify=changed)
    def killed(self) -> bool:
        s = self._spec
        return s.kill_floor is not None and float(self._value) <= s.kill_floor

    # --- zmiana ---
    @Slot(float)
    def setNorm(self, norm: float) -> None:
        self._set(self._spec.from_norm(norm))

    @Slot("QVariant")
    def setValue(self, value: Any) -> None:
        self._set(value)

    @Slot(int)
    def step(self, delta: int) -> None:
        """Następny/poprzedni wybór (choice) lub krok o 1% zakresu."""
        s = self._spec
        if s.kind == "choice":
            n = len(s.choices)
            self._set((int(self._value) + delta) % n)
        elif s.kind == "bool":
            self._set(not self._value)
        else:
            self._set(s.from_norm(s.to_norm(self._value) + 0.01 * delta))

    @Slot()
    def toggle(self) -> None:
        self._set(not bool(self._value))

    @Slot()
    def reset(self) -> None:
        self._set(self._spec.default)


class QmlParams(QObject):
    """Rejestr obiektów parametrów (tworzone leniwie, własność po stronie Pythona)."""

    def __init__(self, bridge: ParamBridge, parent: QObject | None = None):
        super().__init__(parent)
        self.bridge = bridge
        self._items: dict[str, QmlParam] = {}
        bridge.watch_all(self._on_changed)

    def _on_changed(self, changed: dict) -> None:
        for key, value in changed.items():
            item = self._items.get(key)
            if item is not None:
                item._update(value)

    def item(self, key: str) -> QmlParam | None:
        if key not in self.bridge.store.specs:
            return None
        obj = self._items.get(key)
        if obj is None:
            obj = QmlParam(self.bridge, self.bridge.spec(key), self)
            QQmlEngine.setObjectOwnership(obj, QQmlEngine.CppOwnership)
            self._items[key] = obj
        return obj

    @Slot(str, result=QObject)
    def get(self, key: str) -> QObject | None:
        return self.item(key)

    @Slot(str, result=bool)
    def isParam(self, key: str) -> bool:
        return key in self.bridge.store.specs

    @Slot(str, result=str)
    def labelOf(self, target: str) -> str:
        return target_label(target, self.bridge.store.specs)

    @Slot(str, result="QVariantList")
    def typesFor(self, target: str) -> list[str]:
        specs = self.bridge.store.specs
        if target not in specs and target not in ACTIONS and target not in VIEWS:
            return []
        return list(allowed_types(target, specs))

    @Slot(str, result="QVariantList")
    def search(self, text: str) -> list[dict[str, str]]:
        """Wyszukiwarka celów kontrolek: parametry, akcje i widoki (po kluczu i etykiecie)."""
        q = text.strip().lower()
        out: list[dict[str, str]] = []
        specs = self.bridge.store.specs
        entries = [(k, s.label) for k, s in specs.items()] + list(ACTIONS.items()) + list(VIEWS.items())
        for key, label in entries:
            if not q or q in key.lower() or q in label.lower():
                out.append({"key": key, "label": label})
            if len(out) >= 60:
                break
        return out
