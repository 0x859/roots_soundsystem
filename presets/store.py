"""Zapis i odczyt scen oraz presetów EQ w %APPDATA%\\RootsSoundsystem."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from dsp.graph import bypass_values
from engine.params import ParamStore

from .builtin import EQ_PRESETS, SCENES, eq_values


def app_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    d = Path(base) / "RootsSoundsystem"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _dir(kind: str) -> Path:
    d = app_dir() / kind
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", name).strip() or "preset"


def _list(kind: str) -> list[str]:
    return sorted(p.stem for p in _dir(kind).glob("*.json"))


def _save(kind: str, name: str, data) -> Path:
    path = _dir(kind) / f"{_safe(name)}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _load(kind: str, name: str):
    return json.loads((_dir(kind) / f"{_safe(name)}.json").read_text(encoding="utf-8"))


def _delete(kind: str, name: str) -> None:
    p = _dir(kind) / f"{_safe(name)}.json"
    if p.exists():
        p.unlink()


# --- stan przy starcie ---
STARTUP_MODES = ("clean", "last")  # czysty tor (moduły DSP wyłączone) | ostatni stan


def restore_state(store: ParamStore, raw: str | None, mode: str = "clean") -> None:
    """Wczytuje zapisany stan; w trybie „clean” wyłącza wszystkie moduły DSP (ustawienia gałek zostają)."""
    if raw:
        try:
            store.load(json.loads(raw))
        except (TypeError, ValueError):
            pass
    if mode != "last":
        store.set_many(bypass_values())


# --- sceny ---
def list_scenes() -> list[tuple[str, bool]]:
    return [(n, True) for n in SCENES] + [(n, False) for n in _list("scenes") if n not in SCENES]


def scene_values(store: ParamStore, name: str) -> dict:
    """Pełny stan sceny: wartości domyślne uzupełnione nadpisaniami sceny."""
    base = {k: s.default for k, s in store.specs.items() if s.scene and not s.momentary}
    base.update(SCENES[name] if name in SCENES else _load("scenes", name))
    return base


def save_scene(name: str, store: ParamStore) -> Path:
    return _save("scenes", name, store.snapshot(scene_only=True))


def delete_scene(name: str) -> None:
    if name not in SCENES:
        _delete("scenes", name)


# --- presety EQ ---
def list_eq_presets() -> list[tuple[str, bool]]:
    return [(n, True) for n in EQ_PRESETS] + [(n, False) for n in _list("eq") if n not in EQ_PRESETS]


def eq_preset_values(name: str) -> dict:
    if name in EQ_PRESETS:
        return eq_values(EQ_PRESETS[name])
    data = _load("eq", name)
    return eq_values(data["gains"]) | ({"eq.preamp": data["preamp"]} if "preamp" in data else {})


def save_eq_preset(name: str, store: ParamStore) -> Path:
    return _save("eq", name, {"gains": [store[f"eq.b{i}"] for i in range(12)], "preamp": store["eq.preamp"]})


def delete_eq_preset(name: str) -> None:
    if name not in EQ_PRESETS:
        _delete("eq", name)
