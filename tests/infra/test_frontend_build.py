"""Infrastructure tests: frontend build output."""

import json
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

    def test_municipality_page_has_day_cards(self, _project_root: Path, docs_dir: Path) -> None:
        """Municipality page contains today/tomorrow day cards.

        When frontend buildDate (UTC) matches data[0].date (Europe/Oslo), cards
        show "I dag" / "I morgen". When they disagree (common around midnight
        UTC), cards fall back to the specific first-day/second-day dates in
        DD.MM form. We read those dates from the generated JSON so the test
        pins the day-card rendering itself, not incidental DD.MM strings
        elsewhere on the page.
        """
        generated = _project_root / "data" / "generated" / "municipalities" / "oslo.json"
        data = json.loads(generated.read_text(encoding="utf-8"))
        # DD.MM from YYYY-MM-DD
        today_label = data["days"][0]["date"][8:10] + "." + data["days"][0]["date"][5:7]
        tomorrow_label = data["days"][1]["date"][8:10] + "." + data["days"][1]["date"][5:7]

        html = (docs_dir / "kommune" / "oslo" / "index.html").read_text(encoding="utf-8")
        has_fresh_labels = "I dag" in html and "I morgen" in html
        has_stale_labels = today_label in html and tomorrow_label in html
        assert has_fresh_labels or has_stale_labels, (
            f"day cards must show 'I dag'/'I morgen' or the specific dates "
            f"{today_label}/{tomorrow_label}"
        )

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

    def test_unverified_banner_text_on_unverified_page(self, docs_dir: Path) -> None:
        """Every unverified kommune page shows the exact 'ikke verifisert' banner.

        Fauske is one of the bulk-seeded unverified kommuner. The banner copy
        is a trust signal — if it changes, we want CI to catch it before
        shipping.
        """
        html = (docs_dir / "kommune" / "fauske" / "index.html").read_text(encoding="utf-8")
        expected = (
            "Ølsalgsreglene for Fauske er ikke verifisert. Tidene kan avvike fra nasjonale regler."
        )
        assert expected in html, "Missing or wrong unverified banner in fauske/index.html"

    def test_verified_page_has_no_unverified_banner(self, docs_dir: Path) -> None:
        """Verified kommuner must NOT show the 'ikke verifisert' banner.

        Guards against the banner accidentally rendering on every page,
        which would undermine the verification signal.
        """
        html = (docs_dir / "kommune" / "oslo" / "index.html").read_text(encoding="utf-8")
        assert "ikke verifisert" not in html, (
            "Verified kommune page unexpectedly shows 'ikke verifisert' banner"
        )

    def test_featured_section_excludes_bulk_seeded_kommuner(self, docs_dir: Path) -> None:
        """'Mest besøkte kommuner' must not silently balloon to include every bulk-seeded kommune.

        Pairs with test_featured_kommuner_on_index (which checks the positive
        set). This asserts the negative: a known bulk-seeded kommune like
        Haugesund is reachable via search but never a quick-link button.
        """
        import re

        html = (docs_dir / "index.html").read_text(encoding="utf-8")
        match = re.search(r"Mest besøkte kommuner.*?</section>", html, flags=re.DOTALL)
        assert match, "Missing 'Mest besøkte kommuner' section"
        section = match.group(0)
        for unwanted in ("Haugesund", "Fauske", "Drammen", "Kristiansand"):
            assert unwanted not in section, (
                f"{unwanted} leaked into featured quick-links (should only be in search)"
            )

    def test_featured_kommuner_on_index(self, docs_dir: Path) -> None:
        """'Mest besøkte kommuner' section shows exactly the curated short-list.

        The full kommune set is still searchable via the search box; this
        quick-links section is intentionally pinned so it doesn't balloon
        as coverage grows.
        """
        import re

        expected = {"Oslo", "Bergen", "Trondheim", "Stavanger", "Tromsø", "Sandefjord", "Larvik"}
        html = (docs_dir / "index.html").read_text(encoding="utf-8")
        # Grab everything after the "Mest besøkte kommuner" heading up to the end of that section.
        match = re.search(r"Mest besøkte kommuner.*?</section>", html, flags=re.DOTALL)
        assert match, "Missing 'Mest besøkte kommuner' section"
        section = match.group(0)
        # Quick-links render as <a ...>Name</a>; pull the label out.
        names = {m.strip() for m in re.findall(r">([^<>]+)</a>", section)}
        assert names == expected, f"featured set mismatch: got {names}, expected {expected}"

    def test_footer_has_build_timestamp(self, docs_dir: Path) -> None:
        """Footer shows build date on all pages."""
        for page in ("index.html", "kommune/oslo/index.html"):
            html = (docs_dir / page).read_text(encoding="utf-8")
            assert "Sist oppdatert" in html, f"Missing build timestamp in {page}"

    def test_footer_has_last_verified(self, docs_dir: Path) -> None:
        """Footer surfaces a verification signal on all pages.

        Index shows a site-wide coverage summary ("Verifisert: X av Y kommuner");
        per-kommune pages show the kommune's own "Regler sist sjekket".
        """
        index_html = (docs_dir / "index.html").read_text(encoding="utf-8")
        assert "Verifisert:" in index_html and "kommuner" in index_html, (
            "Missing coverage summary in index.html"
        )

        kommune_html = (docs_dir / "kommune" / "oslo" / "index.html").read_text(encoding="utf-8")
        assert "Regler sist sjekket" in kommune_html, (
            "Missing last-verified in kommune/oslo/index.html"
        )

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
