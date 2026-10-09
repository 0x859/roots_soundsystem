"""Akcje dubowe wspólne dla interfejsów Widgets i QML: tap tempo i pamięci syreny."""

from __future__ import annotations

import itertools
import json
import time

from dsp.fx_siren import SIREN_MEMORY_KEYS
from engine.params import ParamStore

N_MEMORIES = 4
TAP_TIMEOUT_S = 2.0


class TapTempo:
    """Liczy BPM z odstępów między stuknięciami; w trybie „Wolny” ustawia też czas echa."""

    def __init__(self, store: ParamStore):
        self.store = store
        self._taps: list[float] = []

    def tap(self, now: float | None = None) -> float | None:
        now = time.monotonic() if now is None else now
        self._taps = [t for t in self._taps if now - t < TAP_TIMEOUT_S] + [now]
        if len(self._taps) < 2:
            return None
        diffs = [b - a for a, b in itertools.pairwise(self._taps)]
        bpm = 60.0 / (sum(diffs) / len(diffs))
        values = {"echo.bpm": bpm}
        if self.store["echo.sync"] == 0:
            values["echo.time"] = 60000.0 / bpm
        self.store.set_many(values, source="gui")
        return bpm


def store_siren_memory(store: ParamStore, settings, i: int) -> None:
    data = {k: store[k] for k in SIREN_MEMORY_KEYS}
    settings.setValue(f"siren/mem{i}", json.dumps(data))


def recall_siren_memory(store: ParamStore, settings, i: int) -> bool:
    raw = settings.value(f"siren/mem{i}")
    if not raw:
        return False
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return False
    store.set_many({k: data[k] for k in SIREN_MEMORY_KEYS if k in data}, source="gui")
    return True


def has_siren_memory(settings, i: int) -> bool:
    return bool(settings.value(f"siren/mem{i}"))
