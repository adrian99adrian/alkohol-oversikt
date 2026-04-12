"""Infrastructure tests: web/package.json scripts for auto-regenerating .astro/types.d.ts."""

import json
from pathlib import Path


def _package_json() -> dict:
    path = Path(__file__).parent.parent.parent / "web" / "package.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_astro_sync_script_exists() -> None:
    """web/package.json defines astro:sync so postinstall and tooling share one command."""
    scripts = _package_json().get("scripts", {})
    assert scripts.get("astro:sync") == "astro sync"


def test_postinstall_runs_astro_sync() -> None:
    """postinstall regenerates .astro/types.d.ts so the TS error doesn't return after install."""
    scripts = _package_json().get("scripts", {})
    assert scripts.get("postinstall") == "npm run astro:sync"
