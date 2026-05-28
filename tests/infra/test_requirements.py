"""Validate that every dependency in requirements.txt is pinned with `==`.

A loose spec (e.g. `requests` or `requests>=2.0`) lets fresh installs silently
pull a different version, breaking reproducibility and widening the supply-chain
attack surface. This test fails if any non-comment line drifts away from the
`name==version` form.
"""

import re
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
REQUIREMENTS_PATH = ROOT_DIR / "requirements.txt"

PINNED_LINE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-]*==\S+$")


def _iter_dependency_lines(path: Path):
    """Yield (lineno, stripped_line) for each non-blank, non-comment line."""
    with path.open("r", encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            line = raw.split("#", 1)[0].strip()
            if line:
                yield lineno, line


def test_requirements_file_exists():
    assert REQUIREMENTS_PATH.exists(), f"Missing file: {REQUIREMENTS_PATH}"


def test_every_dependency_uses_exact_version_pin():
    bad_lines = [
        f"line {lineno}: {line!r}"
        for lineno, line in _iter_dependency_lines(REQUIREMENTS_PATH)
        if not PINNED_LINE_PATTERN.match(line)
    ]
    assert not bad_lines, (
        "Every dependency in requirements.txt must be pinned with '==X.Y.Z'. "
        "Loose specs (e.g. 'requests', 'requests>=2.0') reintroduce the "
        "supply-chain risk this pinning was meant to remove. Offending lines:\n"
        + "\n".join(bad_lines)
    )


@pytest.mark.parametrize(
    "bad_line",
    [
        "requests",
        "requests>=2.0",
        "requests<=2.0",
        "requests~=2.0",
        "requests>2.0",
        "requests<2.0",
        "requests!=2.0",
        "requests==",
    ],
)
def test_pinned_pattern_rejects_loose_specs(bad_line):
    assert not PINNED_LINE_PATTERN.match(bad_line), (
        f"Pattern should reject loose spec: {bad_line!r}"
    )


@pytest.mark.parametrize(
    "good_line",
    [
        "requests==2.32.5",
        "pytest-cov==7.0.0",
        "tzdata==2025.3",
        "pyright==1.1.409",
    ],
)
def test_pinned_pattern_accepts_exact_pins(good_line):
    assert PINNED_LINE_PATTERN.match(good_line), f"Pattern should accept exact pin: {good_line!r}"
