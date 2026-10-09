"""Wbudowane sceny (pełny stan toru), presety 12-pasmowego EQ i brzmienia syreny.

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
    # pasma: 25 50 100 200 400 800 1,6k 3,15k 6,3k 10k 12,5k 16k
    "Dub (sub i dół)": [4.0, 6.0, 4.0, 1.0, -1.0, -2.0, -1.5, -1.0, 0, 0.5, 0, -1.0],
    "Steppers (kopnięcie)": [3.0, 5.0, 5.0, 1.5, -1.5, -1.0, 0, 0.5, 1.0, 1.0, 0.5, 0],
    "Lovers rock (ciepło)": [1.5, 3.0, 2.5, 1.5, 0.5, 0, -0.5, -1.0, -0.5, 0, 0, -0.5],
    "Plener (dół i góra)": [4.0, 5.0, 3.0, 0.5, -1.0, -1.0, 0, 0.5, 1.5, 2.5, 3.0, 2.5],
    "Mała sala (mniej dudnienia)": [-4.0, -2.0, -1.5, -2.5, -1.0, 0, 0, 0, 0.5, 1.0, 1.0, 0.5],
    "Duża sala (pogłos)": [1.0, 2.0, 1.0, -1.0, -2.5, -2.0, -0.5, 0, 0.5, 0.5, -0.5, -1.5],
    "Winyl (ciepły, bez szumu)": [1.0, 1.5, 1.0, 0.5, 0, 0, 0, -0.5, -1.0, -2.0, -3.0, -4.5],
    "Ochrona góry (miękka)": [0, 0, 0, 0, 0, 0, 0, -1.0, -2.5, -4.0, -5.0, -6.0],
    "Stare nagranie (lo-fi)": [-8.0, -6.0, -2.0, 0.5, 1.5, 2.0, 1.5, 0, -2.0, -5.0, -7.0, -9.0],
    "Radio / telefon (efekt)": [-12.0, -12.0, -9.0, -3.0, 2.0, 4.0, 4.0, 1.0, -6.0, -12.0, -12.0, -12.0],
}

# Brzmienia syreny: tylko różnice względem wartości domyślnych parametrów `siren.*`.
# Fala: 0 sinus, 1 trójkąt, 2 piła, 3 prostokąt. LFO: 0 sinus, 1 trójkąt, 2 prostokąt, 3 piła w górę,
# 4 piła w dół. Sweep (półtony) narasta od naciśnięcia przez „czas sweepu”, potem zostaje.
SIREN_PRESETS: dict[str, dict[str, float]] = {
    "Klasyczna (dub siren)": {
        "siren.wave": 1, "siren.pitch": 520.0, "siren.lfo_rate": 3.5, "siren.lfo_depth": 7.0,
        "siren.lfo_shape": 1, "siren.release": 350.0,
    },
    "Wznosząca (riser)": {
        "siren.wave": 2, "siren.pitch": 180.0, "siren.lfo_rate": 7.0, "siren.lfo_depth": 1.5,
        "siren.sweep": 24.0, "siren.sweep_time": 3.0, "siren.release": 500.0, "siren.echo_send": 0.5,
    },
    "Spadająca bomba": {
        "siren.pitch": 1400.0, "siren.lfo_depth": 0.0, "siren.sweep": -24.0, "siren.sweep_time": 1.8,
        "siren.release": 700.0, "siren.echo_send": 0.7,
    },
    "Laser": {
        "siren.wave": 3, "siren.pitch": 1500.0, "siren.lfo_rate": 11.0, "siren.lfo_depth": 12.0,
        "siren.lfo_shape": 4, "siren.sweep": -7.0, "siren.sweep_time": 0.25, "siren.release": 90.0,
        "siren.level": -14.0, "siren.echo_send": 0.8,
    },
    "Alarm (dwa tony)": {
        "siren.wave": 3, "siren.pitch": 750.0, "siren.lfo_rate": 1.6, "siren.lfo_depth": 5.0,
        "siren.lfo_shape": 2, "siren.release": 120.0, "siren.level": -14.0, "siren.echo_send": 0.4,
    },
    "Whoop": {
        "siren.pitch": 260.0, "siren.lfo_rate": 1.3, "siren.lfo_depth": 14.0, "siren.lfo_shape": 3,
        "siren.release": 250.0,
    },
    "Ptak (ćwierk)": {
        "siren.pitch": 1700.0, "siren.lfo_rate": 14.0, "siren.lfo_depth": 4.0, "siren.sweep": 5.0,
        "siren.sweep_time": 0.12, "siren.release": 60.0, "siren.level": -16.0, "siren.echo_send": 0.9,
    },
    "Sub drop": {
        "siren.pitch": 220.0, "siren.lfo_depth": 0.0, "siren.sweep": -24.0, "siren.sweep_time": 2.0,
        "siren.release": 900.0, "siren.level": -10.0, "siren.echo_send": 0.25,
    },
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
