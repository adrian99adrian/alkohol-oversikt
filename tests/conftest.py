"""Shared pytest fixtures for all test modules."""

import json
import sys
from pathlib import Path

import pytest

# Add scripts/ to sys.path so test files can import pipeline modules directly
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


@pytest.fixture
def project_root() -> Path:
    """Return the repo root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def sample_municipality_sandefjord(project_root: Path) -> dict:
    """Load Sandefjord municipality JSON."""
    path = project_root / "data" / "municipalities" / "sandefjord.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def sample_municipality_larvik(project_root: Path) -> dict:
    """Load Larvik municipality JSON."""
    path = project_root / "data" / "municipalities" / "larvik.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def sample_municipality_oslo(project_root: Path) -> dict:
    """Load Oslo municipality JSON."""
    path = project_root / "data" / "municipalities" / "oslo.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def all_municipalities(project_root: Path) -> list[dict]:
    """Load all municipality JSON files from data/municipalities/."""
    municipalities_dir = project_root / "data" / "municipalities"
    result = []
    for path in sorted(municipalities_dir.glob("*.json")):
        with open(path, encoding="utf-8") as f:
            result.append(json.load(f))
    return result
