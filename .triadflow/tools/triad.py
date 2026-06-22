#!/usr/bin/env python3
"""Short command wrapper for TriadFlow."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


WORKFLOW_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = WORKFLOW_ROOT.parent if WORKFLOW_ROOT.name == ".triadflow" else WORKFLOW_ROOT
SUPERVISOR = WORKFLOW_ROOT / "tools" / "triad_supervisor.py"


def run_supervisor(args: list[str]) -> int:
    command = [sys.executable, str(SUPERVISOR), *args]
    return subprocess.run(command, cwd=str(PROJECT_ROOT), shell=False).returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TriadFlow shortcut commands")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    sub.add_parser("status")
    sub.add_parser("approve")
    go = sub.add_parser("go")
    go.add_argument("--max-iterations", default="5")
    sub.add_parser("review")
    sub.add_parser("implement")
    sub.add_parser("review-code")
    sub.add_parser("fix")
    sub.add_parser("review-fix")
    sub.add_parser("audit")
    sub.add_parser("lock-scaffold")
    args = parser.parse_args(argv)

    command_map = {
        "init": ["init"],
        "status": ["status"],
        "approve": ["approve-plan"],
        "review": ["review-plan"],
        "implement": ["implement-next"],
        "review-code": ["review-code"],
        "fix": ["fix-plan"],
        "review-fix": ["review-fix-plan"],
        "audit": ["audit"],
        "lock-scaffold": ["lock-scaffold"],
    }
    if args.command == "go":
        return run_supervisor(["execute-approved-plan", "--max-iterations", str(args.max_iterations)])
    return run_supervisor(command_map[args.command])


if __name__ == "__main__":
    raise SystemExit(main())
