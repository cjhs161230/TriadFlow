import argparse
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "triad_supervisor.py"


def load_supervisor():
    spec = importlib.util.spec_from_file_location("triad_supervisor_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    old_dont_write_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = old_dont_write_bytecode
    return module


class TriadSupervisorTests(unittest.TestCase):
    def setUp(self):
        self.supervisor = load_supervisor()
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)

        self.configure_roots(root, root)

    def configure_roots(self, project_root: Path, workflow_root: Path):
        self.supervisor.PROJECT_ROOT = project_root
        self.supervisor.WORKFLOW_ROOT = workflow_root
        self.supervisor.ROOT = project_root
        self.supervisor.AGENT_DIR = workflow_root / ".agent"
        self.supervisor.REPORTS_DIR = self.supervisor.AGENT_DIR / "reports"
        self.supervisor.LOGS_DIR = self.supervisor.AGENT_DIR / "logs"
        self.supervisor.TMP_DIR = self.supervisor.AGENT_DIR / "tmp"
        self.supervisor.STATE_PATH = self.supervisor.AGENT_DIR / "state.json"
        self.supervisor.CONFIG_PATH = self.supervisor.AGENT_DIR / "config.json"
        self.supervisor.AUDIT_PATH = self.supervisor.LOGS_DIR / "audit.jsonl"
        self.supervisor.SCAFFOLD_MANIFEST_PATH = workflow_root / "manifest.lock"
        self.supervisor.PLAN_PATH = project_root / "PLAN.md"
        self.supervisor.PROMPTS_DIR = workflow_root / "prompts"
        self.supervisor.ROLE_REPORTS = {
            "planner": self.supervisor.REPORTS_DIR / "planner_report.md",
            "reviewer_plan": self.supervisor.REPORTS_DIR / "plan_review.md",
            "developer": self.supervisor.REPORTS_DIR / "implementation_report.md",
            "reviewer_code": self.supervisor.REPORTS_DIR / "code_review.md",
            "planner_fix": self.supervisor.REPORTS_DIR / "fix_plan.md",
            "reviewer_fix_plan": self.supervisor.REPORTS_DIR / "fix_plan_review.md",
        }

    def tearDown(self):
        self.tmp.cleanup()

    def test_init_creates_state_and_handoff_reports(self):
        result = self.supervisor.init_command(argparse.Namespace())

        self.assertEqual(result, 0)
        self.assertTrue(self.supervisor.STATE_PATH.exists())
        self.assertTrue((self.supervisor.REPORTS_DIR / "planner_report.md").exists())
        self.assertTrue((self.supervisor.REPORTS_DIR / "code_review.md").exists())

    def test_high_risk_request_stops_for_user_approval(self):
        self.supervisor.ensure_dirs()
        self.supervisor.save_state(self.supervisor.default_state())

        with self.assertRaises(self.supervisor.TriadError):
            self.supervisor.check_high_risk_request("Please deploy this to production")

        state = self.supervisor.load_state()
        self.assertEqual(state["last_status"], "USER_APPROVAL_REQUIRED")
        self.assertTrue(state["requires_user_approval"])
        self.assertEqual(state["current_phase"], "stopped")

    def test_require_approved_plan_rejects_missing_plan(self):
        self.supervisor.ensure_dirs()
        self.supervisor.save_state(self.supervisor.default_state())

        with self.assertRaisesRegex(self.supervisor.TriadError, "PLAN.md"):
            self.supervisor.require_approved_plan()

    def test_approve_plan_records_human_confirmation(self):
        self.supervisor.ensure_dirs()
        self.supervisor.save_state(self.supervisor.default_state())
        self.supervisor.PLAN_PATH.write_text("# Plan\n\nStatus: Active\n", encoding="utf-8")

        result = self.supervisor.approve_plan_command(argparse.Namespace())

        state = self.supervisor.load_state()
        self.assertEqual(result, 0)
        self.assertEqual(state["current_phase"], "plan_approved")
        self.assertEqual(state["last_status"], "PLAN_APPROVED")
        self.assertEqual(state["next_action"], "review_plan")
        self.assertEqual(state["plan"]["approval"], "human_confirmed")
        self.assertEqual(state["plan"]["path"], "PLAN.md")
        self.assertRegex(state["plan"]["sha256"], r"^[a-f0-9]{64}$")

    def test_approve_plan_requires_active_status(self):
        self.supervisor.ensure_dirs()
        self.supervisor.save_state(self.supervisor.default_state())
        self.supervisor.PLAN_PATH.write_text("# Plan\n\nStatus: Draft\n", encoding="utf-8")

        with self.assertRaisesRegex(self.supervisor.TriadError, "Status: Active"):
            self.supervisor.approve_plan_command(argparse.Namespace())

    def test_require_approved_plan_rejects_changed_plan(self):
        self.supervisor.ensure_dirs()
        self.supervisor.save_state(self.supervisor.default_state())
        self.supervisor.PLAN_PATH.write_text("# Plan\n\nStatus: Active\n", encoding="utf-8")
        self.supervisor.approve_plan_command(argparse.Namespace())
        self.supervisor.PLAN_PATH.write_text("# Plan\n\nStatus: Active\n\nChanged\n", encoding="utf-8")

        with self.assertRaisesRegex(self.supervisor.TriadError, "changed since approval"):
            self.supervisor.require_approved_plan()

    def test_execute_approved_plan_requires_human_confirmation(self):
        self.supervisor.ensure_dirs()
        self.supervisor.save_state(self.supervisor.default_state())
        self.supervisor.PLAN_PATH.write_text("# Plan\n\nStatus: Active\n", encoding="utf-8")

        with self.assertRaisesRegex(self.supervisor.TriadError, "not human-approved"):
            self.supervisor.execute_approved_plan_command(argparse.Namespace(max_iterations=1))

    def test_run_loop_requires_human_approved_plan(self):
        self.supervisor.ensure_dirs()
        self.supervisor.save_state(self.supervisor.default_state())

        with self.assertRaisesRegex(self.supervisor.TriadError, "PLAN.md"):
            self.supervisor.run_loop_command(argparse.Namespace(request=None, max_iterations=1))

    def test_audit_detects_tracked_runtime_files(self):
        self.supervisor.ensure_dirs()
        self.supervisor.PLAN_PATH.write_text("# Plan\n\nStatus: Active\n", encoding="utf-8")

        with mock.patch.object(self.supervisor, "run_process") as run:
            run.return_value.stdout = "A  .agent/reports/code_review.md\nA  PLAN.md\n"
            run.return_value.stderr = ""
            run.return_value.returncode = 0
            result = self.supervisor.audit_command(argparse.Namespace())

        self.assertEqual(result, 1)

    def test_triadflow_install_keeps_plan_in_project_root(self):
        project_root = Path(self.tmp.name) / "project"
        workflow_root = project_root / ".triadflow"
        workflow_root.mkdir(parents=True)
        self.configure_roots(project_root, workflow_root)

        self.assertEqual(self.supervisor.PLAN_PATH, project_root / "PLAN.md")
        self.assertEqual(self.supervisor.STATE_PATH, workflow_root / ".agent" / "state.json")

    def test_scaffold_manifest_detects_changed_file(self):
        workflow_root = Path(self.tmp.name)
        target = workflow_root / "tools" / "triad.py"
        target.parent.mkdir(parents=True)
        target.write_text("original\n", encoding="utf-8")
        self.supervisor.SCAFFOLD_MANIFEST_FILES = ["tools/triad.py"]
        self.supervisor.write_scaffold_manifest()
        target.write_text("changed\n", encoding="utf-8")

        with self.assertRaisesRegex(self.supervisor.TriadError, "scaffold"):
            self.supervisor.check_scaffold_manifest()


if __name__ == "__main__":
    unittest.main()
