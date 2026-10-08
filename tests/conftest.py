import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dsp.graph import all_specs  # noqa: E402
from engine.params import ParamStore  # noqa: E402

FS = 48000
BLOCK = 512


@pytest.fixture
def store():
    return ParamStore(all_specs())


@pytest.fixture
def freqs():
    return np.geomspace(20, 20000, 400)
