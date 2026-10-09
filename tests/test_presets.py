"""Sceny i presety EQ: poprawność wbudowanych danych i zapis/odczyt własnych."""

import pytest

from presets import store as pstore
from presets.builtin import EQ_PRESETS, SCENES


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
