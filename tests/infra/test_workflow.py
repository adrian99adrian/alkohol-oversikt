"""Infrastructure tests: GitHub Actions workflow configuration."""

from pathlib import Path

import yaml

WORKFLOWS_DIR = Path(__file__).parent.parent.parent / ".github" / "workflows"


class TestBuildDeployWorkflow:
    """Validate build-deploy.yml structure and safety nets."""

    def setup_method(self) -> None:
        with open(WORKFLOWS_DIR / "build-deploy.yml", encoding="utf-8") as f:
            self.workflow = yaml.safe_load(f)

    def test_fetch_step_has_continue_on_error(self) -> None:
        """Vinmonopolet fetch step uses continue-on-error for resilience."""
        steps = self.workflow["jobs"]["build"]["steps"]
        fetch_step = next(s for s in steps if s.get("name") == "Fetch Vinmonopolet")
        assert fetch_step.get("continue-on-error") is True

    def test_fetch_failure_emits_warning(self) -> None:
        """A warning annotation step fires when Vinmonopolet fetch fails."""
        steps = self.workflow["jobs"]["build"]["steps"]
        fetch_step = next(s for s in steps if s.get("name") == "Fetch Vinmonopolet")
        assert "id" in fetch_step, "Fetch step needs an id for outcome check"

        fetch_id = fetch_step["id"]
        warning_steps = [
            s
            for s in steps
            if "::warning::" in s.get("run", "") and f"steps.{fetch_id}.outcome" in s.get("if", "")
        ]
        assert len(warning_steps) == 1, "Expected exactly one warning step for fetch failure"
