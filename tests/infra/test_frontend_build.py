"""Infrastructure tests: frontend build output."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def docs_dir(project_root: Path) -> Path:
    """Return the build output directory."""
    return project_root / "docs"


@pytest.fixture
def web_dir(project_root: Path) -> Path:
    """Return the web source directory."""
    return project_root / "web"


def _npm_available() -> bool:
    return shutil.which("npm") is not None


def _generated_data_exists() -> bool:
    data_dir = Path(__file__).parent.parent.parent / "data" / "generated" / "municipalities"
    return data_dir.is_dir() and any(data_dir.glob("*.json"))


def _npm_cmd() -> str:
    """Return the npm command name (npm.cmd on Windows, npm elsewhere)."""
    return "npm.cmd" if sys.platform == "win32" else "npm"


def _npm_env() -> dict[str, str]:
    """Return env with Node.js on PATH (needed after fresh install on Windows)."""
    env = os.environ.copy()
    node_dir = r"C:\Program Files\nodejs"
    if sys.platform == "win32" and node_dir not in env.get("PATH", ""):
        env["PATH"] = node_dir + os.pathsep + env.get("PATH", "")
    return env


@pytest.mark.slow
@pytest.mark.skipif(not _npm_available(), reason="npm not installed")
@pytest.mark.skipif(not _generated_data_exists(), reason="generated municipality data not present")
class TestFrontendBuild:
    """Tests that require a full Astro build (npm install + build)."""

    @pytest.fixture(autouse=True)
    def build_site(self, web_dir: Path, docs_dir: Path) -> None:
        """Run npm install and build once for all tests in this class."""
        npm = _npm_cmd()
        env = _npm_env()

        install = subprocess.run(
            [npm, "install"],
            cwd=web_dir,
            capture_output=True,
            text=True,
            env=env,
        )
        assert install.returncode == 0, f"npm install failed:\n{install.stderr}"

        build = subprocess.run(
            [npm, "run", "build"],
            cwd=web_dir,
            capture_output=True,
            text=True,
            env=env,
        )
        assert build.returncode == 0, f"npm run build failed:\n{build.stderr}"

    def test_index_html_exists(self, docs_dir: Path) -> None:
        """Build output contains index.html."""
        assert (docs_dir / "index.html").exists()

    def test_index_contains_search_input(self, docs_dir: Path) -> None:
        """Landing page has a search input element."""
        html = (docs_dir / "index.html").read_text(encoding="utf-8")
        assert 'id="search-input"' in html

    def test_index_contains_municipality_links(self, docs_dir: Path) -> None:
        """Landing page links to all generated municipalities."""
        html = (docs_dir / "index.html").read_text(encoding="utf-8")
        assert "/alkohol-oversikt/kommune/oslo/" in html
        assert "/alkohol-oversikt/kommune/sandefjord/" in html
        assert "/alkohol-oversikt/kommune/larvik/" in html

    def test_index_contains_municipality_names(self, docs_dir: Path) -> None:
        """Landing page displays municipality names."""
        html = (docs_dir / "index.html").read_text(encoding="utf-8")
        assert "Oslo" in html
        assert "Sandefjord" in html
        assert "Larvik" in html
