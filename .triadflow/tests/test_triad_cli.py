import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "triad.py"


def load_triad_cli():
    spec = importlib.util.spec_from_file_location("triad_cli_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    old_dont_write_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = old_dont_write_bytecode
    return module


class TriadCliTests(unittest.TestCase):
    def test_status_maps_to_supervisor_status(self):
        triad = load_triad_cli()

        with mock.patch.object(triad, "run_supervisor", return_value=0) as run:
            result = triad.main(["status"])

        self.assertEqual(result, 0)
        run.assert_called_once_with(["status"])

    def test_approve_maps_to_approve_plan(self):
        triad = load_triad_cli()

        with mock.patch.object(triad, "run_supervisor", return_value=0) as run:
            result = triad.main(["approve"])

        self.assertEqual(result, 0)
        run.assert_called_once_with(["approve-plan"])

    def test_go_maps_to_execute_approved_plan(self):
        triad = load_triad_cli()

        with mock.patch.object(triad, "run_supervisor", return_value=0) as run:
            result = triad.main(["go", "--max-iterations", "7"])

        self.assertEqual(result, 0)
        run.assert_called_once_with(["execute-approved-plan", "--max-iterations", "7"])

    def test_audit_maps_to_supervisor_audit(self):
        triad = load_triad_cli()

        with mock.patch.object(triad, "run_supervisor", return_value=0) as run:
            result = triad.main(["audit"])

        self.assertEqual(result, 0)
        run.assert_called_once_with(["audit"])

    def test_lock_scaffold_maps_to_supervisor_lock(self):
        triad = load_triad_cli()

        with mock.patch.object(triad, "run_supervisor", return_value=0) as run:
            result = triad.main(["lock-scaffold"])

        self.assertEqual(result, 0)
        run.assert_called_once_with(["lock-scaffold"])

    def test_project_command_files_exist(self):
        root = Path(__file__).resolve().parents[1]
        commands = [
            "triad-init.md",
            "triad-status.md",
            "triad-approve.md",
            "triad-go.md",
            "triad-review.md",
            "triad-implement.md",
            "triad-review-code.md",
            "triad-fix.md",
            "triad-review-fix.md",
            "triad-audit.md",
            "triad-lock-scaffold.md",
        ]

        for command in commands:
            path = root / ".codex" / "commands" / command
            self.assertTrue(path.exists(), command)
            self.assertIn("python tools/triad.py", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
