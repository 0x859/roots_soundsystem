"""Logika callbacku wyjściowego silnika bez urządzeń audio (priming, niedobory, nadmiar)."""

import numpy as np
from conftest import BLOCK, FS

from dsp.common import RingBuffer
from engine.audio_engine import MAX_FILL_BLOCKS, TARGET_FILL_BLOCKS, AudioEngine, EngineConfig


def _engine(store):
    eng = AudioEngine(store)
    cfg = EngineConfig(music_in=0, output=1, fs=FS, block=BLOCK)
    eng.config = cfg
    eng.chain = eng.build_chain(cfg)
    eng._music_ring = RingBuffer(BLOCK * 32, 2)
    eng._music_buf = np.zeros((BLOCK, 2), dtype=np.float32)
    return eng


def _tick(eng):
    out = np.ones((BLOCK, 2), dtype=np.float32)
    eng._out_cb(out, BLOCK, None, None)
    return out


def _feed(eng, blocks, amp=0.1):
    eng._in_cb(np.full((BLOCK * blocks, 2), amp, dtype=np.float32), BLOCK * blocks, None, None)


def test_silence_until_primed(store):
    eng = _engine(store)
    _feed(eng, TARGET_FILL_BLOCKS - 1)
    assert not np.any(_tick(eng))
    assert not eng.stats.primed
    _feed(eng, 1)
    _tick(eng)
    assert eng.stats.primed and eng.stats.underruns == 0


def test_underrun_counted_and_reprimes(store):
    eng = _engine(store)
    _feed(eng, TARGET_FILL_BLOCKS)
    for _ in range(TARGET_FILL_BLOCKS):
        _tick(eng)
    _tick(eng)  # pusty bufor
    assert eng.stats.underruns == 1
    assert not eng._primed


def test_overfill_is_trimmed(store):
    eng = _engine(store)
    _feed(eng, MAX_FILL_BLOCKS + 4)
    _tick(eng)
    assert len(eng._music_ring) == (TARGET_FILL_BLOCKS - 1) * BLOCK
    assert eng.stats.overflows >= 1


def test_mono_input_is_duplicated(store):
    eng = _engine(store)
    eng._in_channels = 1
    eng._in_cb(np.ones((BLOCK, 1), dtype=np.float32), BLOCK, None, None)
    assert len(eng._music_ring) == BLOCK


def test_wrong_block_size_outputs_silence(store):
    eng = _engine(store)
    _feed(eng, 4)
    out = np.ones((BLOCK // 2, 2), dtype=np.float32)
    eng._out_cb(out, BLOCK // 2, None, None)
    assert not np.any(out)


def test_callback_error_is_caught(store):
    eng = _engine(store)
    _feed(eng, 4)

    def boom(*a, **k):
        raise RuntimeError("test")

    eng.chain.process = boom
    out = _tick(eng)
    assert not np.any(out)
    assert eng.stats.callback_errors == 1 and "RuntimeError" in eng.stats.last_error


def test_start_without_devices_raises(store):
    import pytest

    from engine.audio_engine import EngineError

    eng = AudioEngine(store)
    with pytest.raises(EngineError):
        eng.start(EngineConfig(music_in=None, output=None))


def test_sim_mirror_copies_to_headphones(store):
    eng = _engine(store)
    _feed(eng, 4, amp=0.3)
    out = np.zeros((BLOCK, 4), dtype=np.float32)
    for _ in range(3):
        eng._out_cb(out, BLOCK, None, None)
    assert np.any(out[:, :2])
    assert np.array_equal(out[:, 2:], out[:, :2])


def test_music_offset_reads_loopback_pair(store):
    eng = _engine(store)
    eng._in_offset = 4
    data = np.zeros((BLOCK, 6), dtype=np.float32)
    data[:, 4] = 0.5
    data[:, 5] = -0.5
    eng._in_cb(data, BLOCK, None, None)
    buf = np.zeros((BLOCK, 2), dtype=np.float32)
    eng._music_ring.read(BLOCK, buf)
    assert np.allclose(buf[:, 0], 0.5) and np.allclose(buf[:, 1], -0.5)


def test_mic_channel_selection(store):
    eng = _engine(store)
    eng._mic_ring = RingBuffer(BLOCK * 8, 1)
    eng._mic_col = 1
    data = np.zeros((BLOCK, 2), dtype=np.float32)
    data[:, 1] = 0.25
    eng._mic_cb(data, BLOCK, None, None)
    buf = np.zeros((BLOCK, 1), dtype=np.float32)
    eng._mic_ring.read(BLOCK, buf)
    assert np.allclose(buf, 0.25)
