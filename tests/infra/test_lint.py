"""Infrastructure tests: linting and formatting."""

import shutil
import subprocess

import pytest


def test_ruff_check():
    """Verify ruff finds no lint issues."""
    result = subprocess.run(
        ["ruff", "check", "."],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"ruff check failed:\n{result.stdout}\n{result.stderr}"


def test_ruff_format():
    """Verify all Python files are correctly formatted."""
    result = subprocess.run(
        ["ruff", "format", "--check", "."],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"ruff format failed:\n{result.stdout}\n{result.stderr}"


@pytest.mark.skipif(
    shutil.which("actionlint") is None,
    reason="actionlint not installed (best-effort local tool only)",
)
def test_actionlint():
    """Verify GitHub Actions workflow files are valid."""
    result = subprocess.run(
        ["actionlint"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"actionlint failed:\n{result.stdout}\n{result.stderr}"
