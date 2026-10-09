"""Autotest paczki (`main.py --selftest`) – ten sam, który sprawdza zbudowany EXE."""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_selftest_from_source(tmp_path):
    out = tmp_path / "selftest.json"
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    proc = subprocess.run([sys.executable, str(ROOT / "main.py"), "--selftest", str(out)],
                          env=env, cwd=ROOT, capture_output=True, timeout=180)
    result = json.loads(out.read_text(encoding="utf-8"))
    assert proc.returncode == 0, result
    assert result["ok"] and result["qml_loaded"] and result["qml_warnings"] == []
    assert result["steps"] == ["config", "live", "edit"]
    assert result["dsp_on"] == 0  # start z czystym torem
