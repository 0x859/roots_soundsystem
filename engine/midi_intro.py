"""Animacja powitalna diod kontrolera MIDI po podłączeniu (czysta logika, bez sprzętu i bez Qt).

Fala po przekątnej przez kolumny kanałów: zapala diody od lewej (dolny rząd o krok za górnym),
potem gasi je w tym samym kierunku, na koniec krótki błysk wszystkich diod. Klatki to pełne
stany diod (element -> velocity); kontroler wysyła tylko różnice i po ostatniej klatce przywraca
diody zgodne z `ParamStore`. Krok wyznacza zegar przekazany do `LedIntro.frame` – bez wątków i sleepów.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from .midi_profiles import Strip

FRAME_S = 0.05  # czas jednej klatki (s)
FLASH_ON, FLASH_OFF = 3, 2  # długość błysku na końcu (w klatkach)
LED_ON = 127


def _note_key(mid: str) -> tuple[int, int]:
    _, ch, num = mid.split(":")
    return int(ch), int(num)


def led_columns(layout: Sequence[Strip], feedback: Iterable[str]) -> list[list[str]]:
    """Diody pogrupowane w kolumny od lewej (w kolumnie od góry) według układu fizycznego.

    Diody spoza układu (np. mapa z samego learn) dostają osobne kolumny w kolejności numerów nut.
    """
    leds = {m for m in feedback if m.startswith("note:") and m.count(":") == 2}
    columns: list[list[str]] = []
    seen: set[str] = set()
    for strip in layout:
        col = [e.id for e in strip.elements if e.led and e.id in leds and e.id not in seen]
        if col:
            columns.append(col)
            seen.update(col)
    columns.extend([m] for m in sorted(leds - seen, key=_note_key))
    return columns


def intro_frames(columns: Sequence[Sequence[str]]) -> list[dict[str, int]]:
    """Klatki animacji: wypełnienie falą, zgaszenie falą, błysk i zgaszenie (pusta lista bez diod)."""
    cells = [(c + r, mid) for c, col in enumerate(columns) for r, mid in enumerate(col)]
    if not cells:
        return []
    span = max(d for d, _ in cells) + 1
    frames = [{mid: LED_ON if d <= t else 0 for d, mid in cells} for t in range(span)]
    frames += [{mid: LED_ON if d > t else 0 for d, mid in cells} for t in range(span)]
    frames += [{mid: LED_ON for _, mid in cells}] * FLASH_ON
    frames += [{mid: 0 for _, mid in cells}] * FLASH_OFF
    return frames


class LedIntro:
    """Odtwarzanie klatek według zegara; czas liczony od pierwszego kroku, nie od utworzenia
    (np. kontroler wykryty w konstruktorze okna, zanim ruszy pętla zdarzeń)."""

    def __init__(self, frames: Sequence[dict[str, int]], frame_s: float = FRAME_S):
        self.frames = list(frames)
        self.frame_s = frame_s
        self.start: float | None = None
        self.done = not self.frames
        self.mids: set[str] = set().union(*self.frames) if self.frames else set()

    def frame(self, now: float) -> dict[str, int] | None:
        """Klatka na chwilę `now` albo None po końcu animacji (opóźnione kroki pomijają klatki)."""
        if self.done:
            return None
        if self.start is None:
            self.start = now
        i = int((now - self.start) / self.frame_s)
        if i >= len(self.frames):
            self.done = True
            return None
        return self.frames[max(i, 0)]
