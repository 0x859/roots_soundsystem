"""Gotowe układy wyjść (Scarlett 4i4 i inne karty 4-kanałowe)."""

import numpy as np
import pytest

from dsp.crossover import WAYS_BY_COUNT
from dsp.graph import validate_channel_map
from engine.devices import OUTPUT_PRESETS, fit_channels, input_pairs, is_focusrite, is_loopback, presets_for


@pytest.mark.parametrize("p", [p for p in OUTPUT_PRESETS if p.mode == "multi"], ids=lambda p: p.key)
def test_multi_presets_are_valid_maps(store, p):
    ways = WAYS_BY_COUNT[(2, 3, 4)[p.ways_index]]
    assert set(p.channel_map) == set(ways)
    assert validate_channel_map(p.channel_map, ways, 4) == []
    assert store.specs["xo.ways"].clamp(p.ways_index) == p.ways_index


def test_presets_need_four_channels():
    assert presets_for(2) == []
    assert len(presets_for(4)) == len(OUTPUT_PRESETS)


def test_fit_channels():
    x = np.arange(6, dtype=float).reshape(3, 2)
    y = fit_channels(x, 4)
    assert y.shape == (3, 4) and np.array_equal(y[:, 2:], x)
    assert fit_channels(x, 2) is x
    assert fit_channels(x, 1).shape == (3, 1)


def test_name_helpers():
    assert is_focusrite("Analogue 1 + 2 (Focusrite USB Audio)")
    assert is_loopback("Loopback (Focusrite USB Audio)")
    assert input_pairs(6) == [(0, "1–2"), (2, "3–4"), (4, "5–6")]
    assert input_pairs(1) == [(0, "1")]
