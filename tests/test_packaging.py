"""Packaging regression tests for the public CLI surface."""
from __future__ import annotations

import importlib
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"


def test_pyproject_declares_installable_console_script() -> None:
    assert PYPROJECT.exists(), "phantom-companion must be installable with pip -e ."
    with PYPROJECT.open("rb") as fp:
        project = tomllib.load(fp)["project"]

    assert project["scripts"] == {
        "phantom-companion": "phantom_companion.cli:main",
    }


def test_pyproject_declares_public_package_metadata() -> None:
    with PYPROJECT.open("rb") as fp:
        project = tomllib.load(fp)["project"]

    classifiers = set(project["classifiers"])
    urls = project["urls"]

    assert "Development Status :: 3 - Alpha" in classifiers
    assert "License :: OSI Approved :: Apache Software License" in classifiers
    assert "Programming Language :: Python :: 3.11" in classifiers
    assert urls["Homepage"] == "https://github.com/markl-a/phantom-companion"
    assert urls["Repository"] == "https://github.com/markl-a/phantom-companion"
    assert urls["Issues"] == "https://github.com/markl-a/phantom-companion/issues"


def test_console_script_targets_are_importable_and_callable() -> None:
    with PYPROJECT.open("rb") as fp:
        scripts = tomllib.load(fp)["project"]["scripts"]

    for target in scripts.values():
        module_name, _, attr = target.partition(":")
        module = importlib.import_module(module_name)
        entry = getattr(module, attr)
        assert callable(entry), target
