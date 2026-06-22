import argparse
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


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

        self.supervisor.ROOT = root
        self.supervisor.AGENT_DIR = root / ".agent"
        self.supervisor.REPORTS_DIR = self.supervisor.AGENT_DIR / "reports"
        self.supervisor.LOGS_DIR = self.supervisor.AGENT_DIR / "logs"
        self.supervisor.TMP_DIR = self.supervisor.AGENT_DIR / "tmp"
        self.supervisor.STATE_PATH = self.supervisor.AGENT_DIR / "state.json"
        self.supervisor.CONFIG_PATH = self.supervisor.AGENT_DIR / "config.json"
        self.supervisor.AUDIT_PATH = self.supervisor.LOGS_DIR / "audit.jsonl"
        self.supervisor.PLAN_PATH = root / "PLAN.md"
        self.supervisor.PROMPTS_DIR = root / "prompts"
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


if __name__ == "__main__":
    unittest.main()
