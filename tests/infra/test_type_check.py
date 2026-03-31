"""Infrastructure tests: type checking."""

import shutil
import subprocess

import pytest


@pytest.mark.skipif(
    shutil.which("pyright") is None,
    reason="pyright not installed",
)
def test_pyright():
    """Verify no type errors in scripts/ and tests/."""
    result = subprocess.run(
        ["pyright"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"pyright failed:\n{result.stdout}\n{result.stderr}"
