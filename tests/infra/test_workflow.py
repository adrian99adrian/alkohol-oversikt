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


class TestCiWorkflow:
    """Validate ci.yml structure and sonar issue gate."""

    def setup_method(self) -> None:
        with open(WORKFLOWS_DIR / "ci.yml", encoding="utf-8") as f:
            self.workflow = yaml.safe_load(f)

    def test_sonar_job_has_fork_pr_guard(self) -> None:
        """Sonar job must skip forked PRs (no SONAR_TOKEN available)."""
        sonar_if = self.workflow["jobs"]["sonar"].get("if", "")
        assert "pull_request" in sonar_if
        assert "head.repo.full_name" in sonar_if

    def test_sonar_job_has_issue_gate_step(self) -> None:
        """After SonarQube scan, a step must check for zero open issues."""
        steps = self.workflow["jobs"]["sonar"]["steps"]
        scan_idx = next(i for i, s in enumerate(steps) if s.get("name") == "SonarQube Scan")
        gate_steps = [
            s
            for s in steps[scan_idx + 1 :]
            if "sonarcloud.io/api/issues/search" in s.get("run", "")
        ]
        assert len(gate_steps) == 1, "Expected exactly one issue-gate step after SonarQube Scan"

    def test_issue_gate_uses_sonar_token(self) -> None:
        """The issue-gate step must use SONAR_TOKEN for authentication."""
        steps = self.workflow["jobs"]["sonar"]["steps"]
        gate_step = next(s for s in steps if "sonarcloud.io/api/issues/search" in s.get("run", ""))
        assert "SONAR_TOKEN" in str(gate_step.get("env", {})), "Issue gate must use SONAR_TOKEN"

    def test_issue_gate_reads_project_key_from_properties(self) -> None:
        """The issue-gate step must read project key from sonar-project.properties."""
        steps = self.workflow["jobs"]["sonar"]["steps"]
        gate_step = next(s for s in steps if "sonarcloud.io/api/issues/search" in s.get("run", ""))
        assert "sonar-project.properties" in gate_step.get("run", "")
