"""Gotowe układy wyjść dla kart wielokanałowych (m.in. Focusrite Scarlett 4i4 3rd gen).

Scarlett 4i4 3rd gen (wg kart kanałów Focusrite): komputer widzi wyjścia 1-2 i 3-4,
przy czym słuchawki niosą wyjścia 3-4; wejścia 1-4 to sprzęt, 5-6 to Loopback
(tylko przy 44.1/48 i 88.2/96 kHz).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class OutputPreset:
    key: str
    label: str
    mode: str  # "sim" | "multi"
    min_channels: int
    ways_index: int | None = None  # wartość parametru xo.ways (0 = 2 drogi, 1 = 3, 2 = 4)
    channel_map: dict[str, tuple[int, int]] = field(default_factory=dict)
    sim_mirror: bool = False
    note: str = ""


OUTPUT_PRESETS: tuple[OutputPreset, ...] = (
    OutputPreset(
        "sim_mirror", "Symulacja: monitory 1–2 + kopia na 3–4 (słuchawki)", "sim", 4,
        sim_mirror=True,
        note="W Scarlett 4i4 słuchawki grają wyjścia 3–4, więc słychać ten sam miks co na monitorach.",
    ),
    OutputPreset(
        "multi2_stereo", "Multi 2 drogi stereo: bass 1/2, top 3/4", "multi", 4, 0,
        {"bass": (0, 1), "top": (2, 3)},
        note="Słuchawki (wyjścia 3–4) niosą wtedy drogę top.",
    ),
    OutputPreset(
        "multi3", "Multi 3 drogi: bass 1/2 stereo, mid 3, top 4 (mono)", "multi", 4, 1,
        {"bass": (0, 1), "mid": (2, -1), "top": (3, -1)},
        note="Mid i top w mono. Słuchawki niosą mid (L) i top (R).",
    ),
    OutputPreset(
        "multi4_mono", "Multi 4 drogi mono: sub 1, bass 2, mid 3, top 4", "multi", 4, 2,
        {"sub": (0, -1), "bass": (1, -1), "mid": (2, -1), "top": (3, -1)},
        note="Każda droga w mono. Słuchawki niosą mid (L) i top (R).",
    ),
)


def presets_for(n_channels: int) -> list[OutputPreset]:
    return [p for p in OUTPUT_PRESETS if n_channels >= p.min_channels]


def preset(key: str) -> OutputPreset:
    return next(p for p in OUTPUT_PRESETS if p.key == key)


def is_focusrite(name: str) -> bool:
    low = name.lower()
    return "focusrite" in low or "scarlett" in low


def is_loopback(name: str) -> bool:
    return "loopback" in name.lower()


def input_pairs(n_channels: int) -> list[tuple[int, str]]:
    """Pary kanałów wejściowych do wyboru jako źródło muzyki: (pierwszy kanał, etykieta)."""
    return [(i, f"{i + 1}–{i + 2}") for i in range(0, max(0, n_channels - 1), 2)] or [(0, "1")]


def fit_channels(block, n_out: int):
    """Dopasowuje blok wyjściowy (N, C) do n_out kanałów: kopiuje go cyklicznie (np. 1-2 -> 3-4)."""
    c = block.shape[1]
    if c == n_out:
        return block
    if c > n_out:
        return block[:, :n_out]
    idx = [i % c for i in range(n_out)]
    return block[:, idx]
