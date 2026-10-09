"""Sceny, presety EQ i syreny: poprawność wbudowanych danych i zapis/odczyt własnych."""

import numpy as np
import pytest

from dsp.fx_siren import SIREN_MEMORY_KEYS, DubSiren
from presets import store as pstore
from presets.builtin import EQ_PRESETS, SCENES, SIREN_PRESETS


@pytest.fixture
def appdata(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    return tmp_path


@pytest.mark.parametrize("name", list(SCENES))
def test_builtin_scene_keys_exist_and_in_range(store, name):
    for key, value in SCENES[name].items():
        assert key in store.specs, f"scena {name!r}: nieznany parametr {key}"
        spec = store.specs[key]
        assert spec.scene and not spec.momentary, f"scena {name!r}: {key} nie należy do sceny"
        assert spec.clamp(value) == pytest.approx(value), f"scena {name!r}: {key}={value} poza zakresem"


@pytest.mark.parametrize("name", list(EQ_PRESETS))
def test_builtin_eq_presets_fit_eq(store, name):
    gains = EQ_PRESETS[name]
    assert len(gains) == 12
    for i, g in enumerate(gains):
        assert store.specs[f"eq.b{i}"].clamp(g) == pytest.approx(g)


def test_scene_values_fill_defaults(store):
    vals = pstore.scene_values(store, "Neutralny")
    assert vals == {k: s.default for k, s in store.specs.items() if s.scene and not s.momentary}


def test_scene_roundtrip(store, appdata):
    store.set_many({"preamp.drive": 0.7, "echo.feedback": 0.66, "iso.g.sub": -12.0})
    pstore.save_scene("Moja / scena?", store)
    names = [n for n, builtin in pstore.list_scenes() if not builtin]
    assert names == ["Moja _ scena_"]
    vals = pstore.scene_values(store, "Moja _ scena_")
    assert vals["preamp.drive"] == 0.7 and vals["echo.feedback"] == 0.66 and vals["iso.g.sub"] == -12.0
    pstore.delete_scene("Moja _ scena_")
    assert all(builtin for _, builtin in pstore.list_scenes())


def test_builtin_scene_cannot_be_deleted(appdata):
    pstore.delete_scene("Neutralny")
    assert ("Neutralny", True) in pstore.list_scenes()


def test_eq_preset_roundtrip(store, appdata):
    store.set_many({f"eq.b{i}": float(i % 5) for i in range(12)} | {"eq.preamp": -3.0})
    pstore.save_eq_preset("Test", store)
    vals = pstore.eq_preset_values("Test")
    assert [vals[f"eq.b{i}"] for i in range(12)] == [float(i % 5) for i in range(12)]
    assert vals["eq.preamp"] == -3.0


def test_eq_presets_are_distinct():
    curves = [tuple(g) for g in EQ_PRESETS.values()]
    assert len(set(curves)) == len(curves)
    assert list(EQ_PRESETS)[0] == "Flat" and len(EQ_PRESETS) >= 12


@pytest.mark.parametrize("name", list(SIREN_PRESETS))
def test_builtin_siren_presets_valid(store, name):
    for key, value in SIREN_PRESETS[name].items():
        assert key in SIREN_MEMORY_KEYS, f"syrena {name!r}: {key} nie jest parametrem brzmienia syreny"
        spec = store.specs[key]
        if spec.kind == "choice":
            assert value in range(len(spec.choices))
        else:
            assert spec.clamp(value) == pytest.approx(value), f"syrena {name!r}: {key}={value} poza zakresem"


@pytest.mark.parametrize("name", list(SIREN_PRESETS))
def test_builtin_siren_presets_sound(store, name):
    """Każdy preset gra słyszalnie, nie przekracza 0 dBFS i cichnie po puszczeniu przycisku."""
    store.set_many(pstore.siren_preset_values(store, name))
    store.set("siren.trigger", True)
    siren = DubSiren(48000)
    siren.configure(store)
    y = np.concatenate([siren.process(512) for _ in range(94)])  # ~1 s
    peak = np.max(np.abs(y))
    assert 0.01 < peak <= 1.0
    store.set("siren.trigger", False)
    siren.configure(store)
    out = None
    # release to stała czasowa: do progu ciszy 1e-5 obwiednia potrzebuje ~11,5 × release
    blocks = int(12 * store["siren.release"] / 1000 * 48000 / 512) + 2
    for _ in range(blocks):
        out = siren.process(512)
    assert out is None


def test_siren_preset_values_fill_defaults(store):
    vals = pstore.siren_preset_values(store, "Klasyczna (dub siren)")
    assert set(vals) == set(SIREN_MEMORY_KEYS)
    assert vals["siren.echo_send"] == SIREN_PRESETS["Klasyczna (dub siren)"].get(
        "siren.echo_send", store.specs["siren.echo_send"].default)


def test_siren_preset_roundtrip(store, appdata):
    store.set_many({"siren.pitch": 777.0, "siren.wave": 2, "siren.level": -20.0})
    pstore.save_siren_preset("Moja syrena", store)
    assert ("Moja syrena", False) in pstore.list_siren_presets()
    store.reset(SIREN_MEMORY_KEYS)
    vals = pstore.siren_preset_values(store, "Moja syrena")
    assert vals["siren.pitch"] == 777.0 and vals["siren.wave"] == 2 and vals["siren.level"] == -20.0
    pstore.delete_siren_preset("Klasyczna (dub siren)")  # wbudowany – zostaje
    pstore.delete_siren_preset("Moja syrena")
    assert all(builtin for _, builtin in pstore.list_siren_presets())


@pytest.mark.parametrize("kind", list(pstore.PRESET_KINDS))
def test_preset_kinds_apply_and_reset(store, appdata, kind):
    pk = pstore.PRESET_KINDS[kind]
    names = [n for n, builtin in pk.list() if builtin]
    values = pk.values(store, names[-1])
    assert set(values) <= set(pk.keys)
    store.set_many(values)
    pk.save("Własny", store)
    assert ("Własny", False) in pk.list()
    store.reset(list(pk.keys))
    saved = pk.values(store, "Własny")
    assert all(saved[k] == pytest.approx(v) for k, v in values.items())
    pk.delete("Własny")
    assert ("Własny", False) not in pk.list()
