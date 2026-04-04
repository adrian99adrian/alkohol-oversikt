"""Infrastructure tests: frontend build output."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="class")
def _project_root() -> Path:
    """Return the repo root directory (class-scoped for build tests)."""
    return Path(__file__).parent.parent.parent


@pytest.fixture(scope="class")
def docs_dir(_project_root: Path) -> Path:
    """Return the build output directory."""
    return _project_root / "docs"


@pytest.fixture(scope="class")
def web_dir(_project_root: Path) -> Path:
    """Return the web source directory."""
    return _project_root / "web"


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

    @pytest.fixture(autouse=True, scope="class")
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
        assert "/alkohol-oversikt/kommune/trondheim/" in html

    def test_index_contains_municipality_names(self, docs_dir: Path) -> None:
        """Landing page displays municipality names."""
        html = (docs_dir / "index.html").read_text(encoding="utf-8")
        assert "Oslo" in html
        assert "Sandefjord" in html
        assert "Larvik" in html
        assert "Trondheim" in html

    def test_municipality_pages_exist(self, docs_dir: Path) -> None:
        """Build generates a page for each municipality."""
        for muni in ("oslo", "sandefjord", "larvik", "trondheim"):
            page = docs_dir / "kommune" / muni / "index.html"
            assert page.exists(), f"Missing municipality page: {page}"

    def test_municipality_page_has_day_cards(self, docs_dir: Path) -> None:
        """Municipality page contains today/tomorrow day cards (date labels when stale)."""
        html = (docs_dir / "kommune" / "oslo" / "index.html").read_text(encoding="utf-8")
        # When data is fresh, cards show "I dag" / "I morgen".
        # When data is stale, cards show formatted dates (e.g. "01.01").
        has_fresh_labels = "I dag" in html and "I morgen" in html
        has_date_labels = "01.01" in html and "02.01" in html
        assert has_fresh_labels or has_date_labels

    def test_municipality_page_has_table(self, docs_dir: Path) -> None:
        """Municipality page contains the beer sales table with all columns."""
        html = (docs_dir / "kommune" / "oslo" / "index.html").read_text(encoding="utf-8")
        assert "Neste 14 dager" in html
        assert "Ølsalg" in html
        assert "Merknad" in html

    def test_municipality_page_has_badges(self, docs_dir: Path) -> None:
        """Municipality page renders day type badges with color classes."""
        html = (docs_dir / "kommune" / "sandefjord" / "index.html").read_text(encoding="utf-8")
        # Should have at least one badge (any color variant)
        assert "rounded-full" in html
        assert "text-xs" in html

    def test_municipality_page_has_back_link(self, docs_dir: Path) -> None:
        """Municipality page has a back link to the landing page."""
        html = (docs_dir / "kommune" / "oslo" / "index.html").read_text(encoding="utf-8")
        assert "Tilbake" in html
        assert "/alkohol-oversikt/" in html

    def test_municipality_page_has_vinmonopolet_column(self, docs_dir: Path) -> None:
        """Municipality page table has a Vinmonopolet column."""
        html = (docs_dir / "kommune" / "sandefjord" / "index.html").read_text(encoding="utf-8")
        assert "Vinm." in html

    def test_municipality_page_has_vinmonopolet_section(self, docs_dir: Path) -> None:
        """Municipality page has Vinmonopolet store list section."""
        html = (docs_dir / "kommune" / "sandefjord" / "index.html").read_text(encoding="utf-8")
        assert "Vinmonopolet" in html

    def test_municipality_page_has_sources(self, docs_dir: Path) -> None:
        """Municipality page has sources section with links."""
        html = (docs_dir / "kommune" / "sandefjord" / "index.html").read_text(encoding="utf-8")
        assert "Kilder" in html
        assert "Sist verifisert" in html

    def test_municipality_page_has_disclaimer(self, docs_dir: Path) -> None:
        """Municipality page has disclaimer text."""
        html = (docs_dir / "kommune" / "sandefjord" / "index.html").read_text(encoding="utf-8")
        assert "alkoholloven" in html

    def test_municipality_page_has_legend(self, docs_dir: Path) -> None:
        """Municipality page contains the day type color legend."""
        html = (docs_dir / "kommune" / "oslo" / "index.html").read_text(encoding="utf-8")
        assert "Vanlige salgstider" in html
        assert "Salg ikke tillatt" in html

    def test_oslo_has_store_directory_and_maps_link(self, docs_dir: Path) -> None:
        """Oslo municipality page has store directory and Google Maps link."""
        html = (docs_dir / "kommune" / "oslo" / "index.html").read_text(encoding="utf-8")
        assert "Butikker" in html
        assert "Finn nærmeste Vinmonopolet" in html

    def test_footer_has_build_timestamp(self, docs_dir: Path) -> None:
        """Footer shows build date on all pages."""
        for page in ("index.html", "kommune/oslo/index.html"):
            html = (docs_dir / page).read_text(encoding="utf-8")
            assert "Sist oppdatert" in html, f"Missing build timestamp in {page}"

    def test_footer_has_last_verified(self, docs_dir: Path) -> None:
        """Footer shows last-verified date on all pages."""
        for page in ("index.html", "kommune/oslo/index.html"):
            html = (docs_dir / page).read_text(encoding="utf-8")
            assert "Regler sist sjekket" in html, f"Missing last-verified in {page}"

    def test_404_html_exists(self, docs_dir: Path) -> None:
        """Build output contains 404.html at the root."""
        assert (docs_dir / "404.html").exists()

    def test_404_has_generic_message(self, docs_dir: Path) -> None:
        """404 page contains the generic not-found message."""
        html = (docs_dir / "404.html").read_text(encoding="utf-8")
        assert "Siden ble ikke funnet" in html

    def test_404_has_kommune_message(self, docs_dir: Path) -> None:
        """404 page contains the municipality-specific not-found message."""
        html = (docs_dir / "404.html").read_text(encoding="utf-8")
        assert "Denne kommunen eksisterer ikke eller er ikke implementert enda" in html

    def test_404_has_homepage_link(self, docs_dir: Path) -> None:
        """404 page has a visible link back to the homepage."""
        html = (docs_dir / "404.html").read_text(encoding="utf-8")
        assert 'href="/alkohol-oversikt/"' in html
        assert "forsiden" in html.lower()
