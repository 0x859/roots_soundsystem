"""Most między magazynem parametrów a widżetami Qt (zawsze w wątku GUI)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, Signal

from engine.params import ParamStore


class ParamBridge(QObject):
    changed = Signal(dict)
    touched = Signal(str)

    def __init__(self, store: ParamStore):
        super().__init__()
        self.store = store
        self._watchers: dict[str, list[Callable[[Any], None]]] = defaultdict(list)
        self._global: list[Callable[[dict], None]] = []
        self.changed.connect(self._dispatch)
        store.subscribe(self._on_store)

    def _on_store(self, changed: dict, source: Any) -> None:
        self.changed.emit(dict(changed))

    def _dispatch(self, changed: dict) -> None:
        for key, value in changed.items():
            for fn in self._watchers.get(key, ()):
                fn(value)
        for fn in self._global:
            fn(changed)

    def watch(self, key: str, fn: Callable[[Any], None]) -> None:
        self._watchers[key].append(fn)

    def watch_all(self, fn: Callable[[dict], None]) -> None:
        self._global.append(fn)

    def spec(self, key: str):
        return self.store.specs[key]

    def get(self, key: str) -> Any:
        return self.store[key]

    def set(self, key: str, value: Any, touched: bool = True) -> None:
        self.store.set(key, value, source="gui")
        if touched:
            self.touched.emit(key)
