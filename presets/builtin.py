"""Wbudowane sceny (pełny stan toru) i presety 12-pasmowego EQ.

Wbudowane odpowiedzi impulsowe miejsc generuje `dsp.room.generate_ir`,
a profile kolumn są w `dsp.cabinets.PROFILES`.
"""

from __future__ import annotations

EQ_PRESETS: dict[str, list[float]] = {
    "Flat": [0.0] * 12,
    "Bass Boost": [6.0, 6.0, 4.5, 2.5, 1.0, 0, 0, 0, 0, 0, 0, 0],
    "Treble Boost": [0, 0, 0, 0, 0, 0, 1.0, 2.5, 4.0, 5.0, 5.5, 6.0],
    "Vocal": [-3.0, -2.5, -1.5, 0, 1.5, 3.0, 3.5, 3.0, 1.5, 0, -0.5, -1.0],
    "Rock": [4.5, 4.0, 3.0, 1.0, -1.0, -1.5, 0, 1.5, 3.0, 3.5, 3.5, 3.0],
    "Loudness": [6.0, 5.0, 3.0, 1.0, 0, -0.5, 0, 0.5, 2.0, 3.5, 4.0, 4.5],
    "Roots (ciepły dół)": [3.0, 5.0, 4.0, 1.5, -0.5, -1.5, -1.0, 0, 1.0, 1.5, 1.0, 0.5],
}


def eq_values(gains: list[float]) -> dict[str, float]:
    return {f"eq.b{i}": float(g) for i, g in enumerate(gains)}


SCENES: dict[str, dict] = {
    "Neutralny": {},
    "Roots warm (styl Shaka)": {
        "preamp.drive": 0.35, "preamp.bias": 0.4, "preamp.bass": 4.0, "preamp.treble": 2.0,
        **eq_values(EQ_PRESETS["Roots (ciepły dół)"]),
        "room.preset": 0, "room.mix": 0.3,
        "echo.sync": 4, "echo.bpm": 75.0, "echo.feedback": 0.55,
    },
    "Steppers heavy": {
        "preamp.drive": 0.45, "preamp.bass": 5.0,
        "iso.g.sub": 3.0, "iso.g.highmid": -1.5,
        **eq_values([5.0, 6.0, 3.0, 0.5, -1.0, -1.5, -1.0, -2.0, 0, 1.0, 0.5, 0]),
        "xo.gain.sub": 3.0, "sim.cab_drive": 0.35,
        "room.preset": 1, "room.mix": 0.35,
    },
    "Dub echo chamber": {
        "preamp.echo_send": 0.2, "preamp.spring_send": 0.15, "preamp.lp": 9000.0,
        "echo.sync": 4, "echo.bpm": 72.0, "echo.feedback": 0.78, "echo.lp": 2500.0, "echo.wow": 0.4, "echo.drive": 0.5,
        "spring.decay": 0.75, "spring.return": 1.0,
        "room.preset": 1, "room.mix": 0.3,
    },
    "Plener (outdoor session)": {
        "preamp.bass": 3.0, "preamp.treble": 1.5,
        "room.preset": 2, "room.mix": 0.4, "room.size": 1.3,
        "sim.width": 0.4,
    },
    "Słuchawki (bass feel)": {
        "sim.bassfeel": 0.6, "room.mix": 0.15, "sim.width": 0.5, "preamp.bass": 2.0,
    },
}
