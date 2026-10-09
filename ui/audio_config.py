"""Konfiguracja audio bez widżetów: listy urządzeń, wybór zapisanych, podpowiedzi i zapis ustawień.

Wspólne dla okna „Ustawienia audio” (Widgets) i karty urządzeń w QML.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from engine.audio_engine import EngineConfig, find_cable_output, wasapi_default_output
from engine.devices import is_focusrite, is_loopback

MODES = (("sim", "Symulacja (stereo)"), ("multi", "Multi (wielokanałowe)"))
BLOCKS = (256, 512, 1024)
NO_MIC = "— brak mikrofonu —"


def music_items(devices) -> list[tuple[str, int]]:
    return [(d.label, d.index) for d in devices if d.max_in > 0]


def output_items(devices) -> list[tuple[str, int]]:
    return [(f"{d.label} ({d.max_out} kan.)", d.index) for d in devices if d.max_out > 0]


def mic_items(devices) -> list[tuple[str, int | None]]:
    return [(NO_MIC, None)] + [(d.label, d.index) for d in devices if d.max_in > 0]


def match_item(items: Sequence[tuple[str, Any]], saved: Any, fallback: Any = None) -> Any:
    """Jak wybór w liście rozwijanej: etykieta zaczynająca się od zapisanej, potem zapasowa, potem pierwsza."""
    if saved:
        for text, data in items:
            if text.startswith(str(saved)):
                return data
    if fallback is not None and any(data == fallback for _, data in items):
        return fallback
    return items[0][1] if items else None


def default_output(devices) -> int | None:
    """Domyślne wyjście Windows, ale nigdy CABLE (to wejście muzyki)."""
    out = wasapi_default_output()
    dev = next((d for d in devices if d.index == out), None)
    if dev is None or "CABLE" in dev.name.upper():
        out = next((d.index for d in devices if d.max_out > 0 and "CABLE" not in d.name.upper()), None)
    return out


def resolve_devices(devices, settings) -> tuple[int | None, int | None, int | None]:
    """(muzyka, wyjście, mikrofon) na podstawie etykiet zapisanych w ustawieniach."""
    music = match_item(music_items(devices), settings.value("audio/music"), find_cable_output(devices))
    out = match_item(output_items(devices), settings.value("audio/output"), default_output(devices))
    mic = match_item(mic_items(devices), settings.value("audio/mic"))
    return music, out, mic


def device_by_index(devices, index):
    return next((d for d in devices if d.index == index), None)


def hints(devices, music: int | None, output: int | None, music_offset: int, note: str = "") -> list[str]:
    tips = [note] if note else []
    out = device_by_index(devices, output)
    mus = device_by_index(devices, music)
    if out is not None and is_focusrite(out.name) and out.max_out < 4:
        tips.append("Windows widzi tylko 2 kanały wyjścia Focusrite – w Panelu dźwięku → Konfiguruj ustaw "
                    "głośniki „Kwadrofoniczne”, aby użyć wyjść 3–4.")
    if (mus is not None and is_loopback(mus.name)) or music_offset == 4:
        tips.append("Loopback nagrywa to, co gra karta. Nie wysyłaj wyjścia aplikacji na kanały objęte "
                    "loopbackiem (pętla sprzężenia) – w razie wątpliwości użyj VB-Cable.")
    return tips


def persist(settings, cfg: EngineConfig, devices) -> None:
    """Zapis konfiguracji w formacie okna „Ustawienia audio” (urządzenia po etykietach)."""
    mus = device_by_index(devices, cfg.music_in)
    out = device_by_index(devices, cfg.output)
    mic = device_by_index(devices, cfg.mic_in)
    settings.setValue("audio/music", mus.label if mus else "")
    settings.setValue("audio/output", out.label if out else "")
    settings.setValue("audio/mic", mic.label if mic else "")
    settings.setValue("audio/mode", cfg.mode)
    settings.setValue("audio/block", cfg.block)
    settings.setValue("audio/channel_map", json.dumps(cfg.channel_map))
    settings.setValue("audio/sim_mirror", "true" if cfg.sim_mirror else "false")
    settings.setValue("audio/music_offset", int(cfg.music_offset))
    settings.setValue("audio/mic_channel", int(cfg.mic_channel))
