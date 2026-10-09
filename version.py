"""Wersja aplikacji – jedno źródło dla okna, autotestu, zasobu wersji EXE i pyproject.toml.

Schemat: MAJOR.MINOR.PATCH (SemVer). MINOR = etap planu (0.2 – etap 2: QML), PATCH = poprawki
w obrębie etapu. Zmiany opisuje CHANGELOG.md; test pilnuje zgodności z pyproject.toml.
"""

from __future__ import annotations

APP_NAME = "Roots Soundsystem"
VERSION = "0.2.0"
# identyfikator dla paska zadań Windows (bez wersji, żeby przypięta ikona przetrwała aktualizację)
APP_USER_MODEL_ID = "RootsSoundsystem.RootsSoundsystem"


def version_tuple(version: str = VERSION) -> tuple[int, int, int, int]:
    """Cztery liczby dla zasobu wersji Windows (brakujące uzupełnione zerami)."""
    parts = [int(p) for p in version.split("-")[0].split("+")[0].split(".")]
    return tuple((parts + [0, 0, 0, 0])[:4])  # type: ignore[return-value]
