"""Wersja: jedno źródło (`version.py`) zgodne z pyproject.toml, CHANGELOG i oknem „O programie”."""

import re
import tomllib
from pathlib import Path

import pytest

from version import APP_NAME, VERSION, version_tuple

ROOT = Path(__file__).resolve().parents[1]


def test_semver_and_pyproject_match():
    assert re.fullmatch(r"\d+\.\d+\.\d+", VERSION)
    with open(ROOT / "pyproject.toml", "rb") as fh:
        assert tomllib.load(fh)["project"]["version"] == VERSION


def test_changelog_has_current_version():
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## [{VERSION}]" in text


def test_version_tuple():
    assert version_tuple("1.2.3") == (1, 2, 3, 0)
    assert version_tuple("0.2") == (0, 2, 0, 0)
    assert version_tuple("1.0.0-rc1") == (1, 0, 0, 0)
    assert len(version_tuple()) == 4


def test_about_text():
    pytest.importorskip("PySide6")
    from ui.main_window import about_text

    text = about_text()
    assert f"{APP_NAME} {VERSION}" in text and "Qt" in text and "Python" in text
