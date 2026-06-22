#!/usr/bin/env python3
"""Conservative file-based supervisor for the Triad Agent Workflow."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


WORKFLOW_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = WORKFLOW_ROOT.parent if WORKFLOW_ROOT.name == ".triadflow" else WORKFLOW_ROOT
ROOT = PROJECT_ROOT
AGENT_DIR = WORKFLOW_ROOT / ".agent"
REPORTS_DIR = AGENT_DIR / "reports"
LOGS_DIR = AGENT_DIR / "logs"
TMP_DIR = AGENT_DIR / "tmp"
STATE_PATH = AGENT_DIR / "state.json"
CONFIG_PATH = AGENT_DIR / "config.json"
AUDIT_PATH = LOGS_DIR / "audit.jsonl"
SCAFFOLD_MANIFEST_PATH = WORKFLOW_ROOT / "manifest.lock"
PLAN_PATH = PROJECT_ROOT / "PLAN.md"
PROMPTS_DIR = WORKFLOW_ROOT / "prompts"

SCAFFOLD_MANIFEST_FILES = [
    "tools/triad_supervisor.py",
    "tools/triad.py",
    "prompts/planner.md",
    "prompts/reviewer_plan.md",
    "prompts/developer.md",
    "prompts/reviewer_code.md",
    "prompts/planner_fix.md",
    "prompts/reviewer_fix_plan.md",
    ".agents/skills/triad-plan-loop/SKILL.md",
    ".agents/skills/triad-plan-loop/references/workflow.md",
    ".agents/skills/triad-plan-loop/references/safety_policy.md",
    "templates/gitignore.snippet",
    "templates/gitattributes.snippet",
    "TRIAD_AGENT_WORKFLOW.md",
]

PROTECTED_BLOCKS = [
    {"path": "AGENTS.md", "name": "TRIADFLOW"},
    {"path": "README.md", "name": "TRIADFLOW"},
]

ROLE_REPORTS = {
    "planner": REPORTS_DIR / "planner_report.md",
    "reviewer_plan": REPORTS_DIR / "plan_review.md",
    "developer": REPORTS_DIR / "implementation_report.md",
    "reviewer_code": REPORTS_DIR / "code_review.md",
    "planner_fix": REPORTS_DIR / "fix_plan.md",
    "reviewer_fix_plan": REPORTS_DIR / "fix_plan_review.md",
}

PROMPT_FILES = {
    "planner": PROMPTS_DIR / "planner.md",
    "reviewer_plan": PROMPTS_DIR / "reviewer_plan.md",
    "developer": PROMPTS_DIR / "developer.md",
    "reviewer_code": PROMPTS_DIR / "reviewer_code.md",
    "planner_fix": PROMPTS_DIR / "planner_fix.md",
    "reviewer_fix_plan": PROMPTS_DIR / "reviewer_fix_plan.md",
}

HIGH_RISK_PATTERNS = [
    r"\bdeploy\b",
    r"\bpublish\b",
    r"\bproduction\b",
    r"\bprod(?:uction)?\s+database\b",
    r"\bdelete\s+database\b",
    r"\bpayment\b",
    r"\bbilling\b",
    r"\bsecret\b",
    r"\bcredential\b",
    r"\btoken\b",
    r"\bprivate\s+key\b",
    r"\bforce[- ]push\b",
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+clean\b",
]


class TriadError(RuntimeError):
    """Expected supervisor failure that should stop the workflow."""


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def workflow_rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(WORKFLOW_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def ensure_dirs() -> None:
    for path in [AGENT_DIR, REPORTS_DIR, LOGS_DIR, TMP_DIR, AGENT_DIR / "schemas"]:
        path.mkdir(parents=True, exist_ok=True)


def audit(event: str, **fields: Any) -> None:
    ensure_dirs()
    entry = {"time": now_iso(), "event": event, **fields}
    with AUDIT_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=True, sort_keys=True) + "\n")


def read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return dict(default)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TriadError(f"Invalid JSON in {rel(path)}: {exc}") from exc


def write_json(path: Path, data: dict[str, Any]) -> None:
    ensure_dirs()
    path.write_text(json.dumps(data, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def default_state() -> dict[str, Any]:
    return {
        "version": 1,
        "active": False,
        "mode": "manual",
        "current_phase": "idle",
        "current_task_id": None,
        "iteration": 0,
        "max_iterations": 10,
        "last_status": "idle",
        "next_action": "await_user_request",
        "blocked_reason": None,
        "requires_user_approval": False,
        "plan": {
            "approval": "not_confirmed",
            "approved_at": None,
            "path": None,
            "sha256": None,
        },
        "agents": {
            "planner": {"last_run": None, "last_report": ".agent/reports/planner_report.md"},
            "reviewer": {"last_run": None, "last_report": ".agent/reports/code_review.md"},
            "developer": {"last_run": None, "last_report": ".agent/reports/implementation_report.md"},
        },
        "safety": {
            "allow_auto_continue": False,
            "allow_network": False,
            "allow_deploy": False,
            "allow_push": False,
            "allow_destructive": False,
        },
    }


def load_state() -> dict[str, Any]:
    return read_json(STATE_PATH, default_state())


def save_state(state: dict[str, Any]) -> None:
    write_json(STATE_PATH, state)


def set_state(**updates: Any) -> None:
    state = load_state()
    state.update(updates)
    save_state(state)


def require_files(paths: Iterable[Path]) -> None:
    missing = [rel(path) for path in paths if not path.exists()]
    if missing:
        raise TriadError("Missing required files: " + ", ".join(missing))


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def protected_block_text(path: Path, name: str) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    start = f"<!-- {name}:PROTECTED:START -->"
    end = f"<!-- {name}:PROTECTED:END -->"
    pattern = re.compile(rf"{re.escape(start)}(.*?){re.escape(end)}", flags=re.DOTALL)
    match = pattern.search(text)
    if not match:
        raise TriadError(f"Protected block missing in {rel(path)}: {name}")
    return match.group(1).strip()


def scaffold_manifest_entries() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for name in SCAFFOLD_MANIFEST_FILES:
        path = WORKFLOW_ROOT / name
        if path.exists():
            entries.append({"path": name, "sha256": file_sha256(path), "size": path.stat().st_size})
    return entries


def protected_block_entries() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for block in PROTECTED_BLOCKS:
        path = PROJECT_ROOT / block["path"]
        if path.exists():
            text = protected_block_text(path, block["name"])
            entries.append({
                "path": block["path"],
                "name": block["name"],
                "sha256": text_sha256(text),
            })
    return entries


def write_scaffold_manifest() -> None:
    data = {
        "version": 1,
        "root": ".triadflow" if WORKFLOW_ROOT.name == ".triadflow" else ".",
        "files": scaffold_manifest_entries(),
        "protected_blocks": protected_block_entries(),
    }
    SCAFFOLD_MANIFEST_PATH.write_text(json.dumps(data, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def check_scaffold_manifest() -> None:
    if not SCAFFOLD_MANIFEST_PATH.exists():
        return
    data = read_json(SCAFFOLD_MANIFEST_PATH, {})
    problems = []
    for entry in data.get("files", []):
        path = WORKFLOW_ROOT / entry.get("path", "")
        if not path.exists():
            problems.append(f"missing {entry.get('path')}")
            continue
        if file_sha256(path) != entry.get("sha256"):
            problems.append(f"changed {entry.get('path')}")
    for entry in data.get("protected_blocks", []):
        path = PROJECT_ROOT / entry.get("path", "")
        if not path.exists():
            problems.append(f"missing protected block file {entry.get('path')}")
            continue
        try:
            text = protected_block_text(path, entry.get("name", ""))
        except TriadError as exc:
            problems.append(str(exc))
            continue
        if text_sha256(text) != entry.get("sha256"):
            problems.append(f"changed protected block {entry.get('path')}#{entry.get('name')}")
    if problems:
        raise TriadError("TriadFlow scaffold integrity check failed: " + "; ".join(problems))


def is_scaffold_maintenance_command(command: str) -> bool:
    return command in {"lock-scaffold", "audit", "init", "status"}


def plan_status() -> str | None:
    if not PLAN_PATH.exists():
        return None
    text = PLAN_PATH.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"^Status:\s*([A-Za-z_ -]+)\s*$", text, flags=re.MULTILINE)
    return match.group(1).strip() if match else None


def require_active_plan_status() -> None:
    status = plan_status()
    if status != "Active":
        raise TriadError("PLAN.md must contain an exact status line: Status: Active")


def require_approved_plan() -> None:
    require_files([PLAN_PATH])
    require_active_plan_status()
    state = load_state()
    if state.get("plan", {}).get("approval") != "human_confirmed":
        raise TriadError("PLAN.md exists but is not human-approved. Run approve-plan after reviewing it.")
    approved_hash = state.get("plan", {}).get("sha256")
    current_hash = file_sha256(PLAN_PATH)
    if approved_hash != current_hash:
        raise TriadError("PLAN.md changed since approval. Review it and run approve-plan again.")


def safe_read(path: Path, limit: int = 120_000) -> str:
    if not path.exists():
        return f"[missing: {rel(path)}]\n"
    data = path.read_text(encoding="utf-8", errors="replace")
    if len(data) > limit:
        return data[:limit] + f"\n[truncated {len(data) - limit} chars]\n"
    return data


def check_high_risk_request(request: str | None) -> None:
    if not request:
        return
    lowered = request.lower()
    for pattern in HIGH_RISK_PATTERNS:
        if re.search(pattern, lowered):
            set_state(
                last_status="USER_APPROVAL_REQUIRED",
                blocked_reason=f"High-risk request matched pattern: {pattern}",
                requires_user_approval=True,
                current_phase="stopped",
            )
            audit("high_risk_request", pattern=pattern, request=request)
            raise TriadError(f"High-risk request requires explicit user approval: {pattern}")


def run_process(args: list[str], *, cwd: Path = PROJECT_ROOT, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    audit("process_start", args=args)
    try:
        result = subprocess.run(
            args,
            cwd=str(cwd),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            shell=False,
        )
    except FileNotFoundError as exc:
        audit("process_missing", args=args, error=str(exc))
        raise TriadError(f"Command not found: {args[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        audit("process_timeout", args=args, timeout=timeout)
        raise TriadError(f"Command timed out: {' '.join(args)}") from exc
    audit("process_finish", args=args, returncode=result.returncode)
    return result


def git_available() -> bool:
    return shutil.which("git") is not None


def in_git_repo() -> bool:
    if not git_available():
        return False
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=str(PROJECT_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def git_status_summary() -> str:
    if not in_git_repo():
        return "Git repository not detected; git status unavailable.\n"
    result = run_process(["git", "status", "--short"], timeout=30)
    return result.stdout if result.stdout else "[clean]\n"


def save_git_diff() -> None:
    diff_path = REPORTS_DIR / "latest_diff.patch"
    if not in_git_repo():
        diff_path.write_text("Git repository not detected; diff unavailable.\n", encoding="utf-8")
        return
    result = run_process(["git", "diff", "--"], timeout=60)
    diff_path.write_text(result.stdout + result.stderr, encoding="utf-8")


def build_prompt(role_key: str, request: str | None = None) -> Path:
    require_files([PROMPT_FILES[role_key], STATE_PATH])
    context: list[str] = [safe_read(PROMPT_FILES[role_key])]
    context.append("\n\n## User Request\n")
    context.append(request or "[No new user request provided. Use PLAN.md when applicable.]\n")
    context.append("\n\n## State\n```json\n")
    context.append(safe_read(STATE_PATH))
    context.append("```\n")

    if role_key in {"planner", "reviewer_plan", "developer", "reviewer_code", "planner_fix", "reviewer_fix_plan"}:
        context.append("\n\n## PLAN.md\n")
        context.append(safe_read(PLAN_PATH))

    if role_key in {"planner_fix", "reviewer_fix_plan", "developer"}:
        context.append("\n\n## Fix Plan\n")
        context.append(safe_read(REPORTS_DIR / "fix_plan.md"))

    if role_key in {"planner", "planner_fix"}:
        context.append("\n\n## Reviewer Reports\n")
        context.append("\n### Plan Review\n")
        context.append(safe_read(REPORTS_DIR / "plan_review.md"))
        context.append("\n### Code Review\n")
        context.append(safe_read(REPORTS_DIR / "code_review.md"))

    if role_key == "reviewer_plan":
        context.append("\n\n## Planner Report\n")
        context.append(safe_read(REPORTS_DIR / "planner_report.md"))

    if role_key == "reviewer_code":
        context.append("\n\n## Implementation Report\n")
        context.append(safe_read(REPORTS_DIR / "implementation_report.md"))
        context.append("\n\n## Latest Diff\n")
        context.append(safe_read(REPORTS_DIR / "latest_diff.patch"))
        context.append("\n\n## Test Output\n")
        context.append(safe_read(REPORTS_DIR / "test_output.txt"))
        context.append("\n\n## Git Status Summary\n")
        context.append(git_status_summary())

    context.append("\n\n## Isolation Rule\nDo not use or request prior chat history. Use only files and context above.\n")
    prompt_path = TMP_DIR / f"{role_key}_prompt.md"
    ensure_dirs()
    prompt_path.write_text("".join(context), encoding="utf-8")
    return prompt_path


def run_codex_role(role_key: str, prompt_path: Path, output_path: Path, sandbox: str) -> str:
    codex = read_json(CONFIG_PATH, {}).get("codex_command", "codex")
    if shutil.which(codex) is None:
        raise TriadError(f"Codex CLI not found on PATH: {codex}")
    cmd = [codex, "exec", "--sandbox", sandbox, "-o", str(output_path)]
    if sandbox == "workspace-write":
        cmd.extend(["--ask-for-approval", "on-request"])
    cmd.append(safe_read(prompt_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = run_process(cmd, timeout=1800)
    (REPORTS_DIR / f"{role_key}_stdout.txt").write_text(result.stdout, encoding="utf-8")
    (REPORTS_DIR / f"{role_key}_stderr.txt").write_text(result.stderr, encoding="utf-8")
    if result.returncode != 0:
        raise TriadError(f"Codex role failed ({role_key}) with exit code {result.returncode}")
    return safe_read(output_path)


def extract_status(text: str, prefix: str, allowed: set[str]) -> str:
    matches = re.findall(rf"^{re.escape(prefix)}:\s*([A-Z_]+)\s*$", text, flags=re.MULTILINE)
    if not matches:
        raise TriadError(f"Missing status line: {prefix}: ...")
    status = matches[-1]
    if status not in allowed:
        raise TriadError(f"Unexpected {prefix}: {status}")
    return status


def update_agent_run(agent: str, report: Path) -> None:
    state = load_state()
    state.setdefault("agents", {}).setdefault(agent, {})
    state["agents"][agent]["last_run"] = now_iso()
    state["agents"][agent]["last_report"] = rel(report)
    save_state(state)


def init_command(_: argparse.Namespace) -> int:
    ensure_dirs()
    if not STATE_PATH.exists():
        save_state(default_state())
    for path, title in [
        (REPORTS_DIR / "planner_report.md", "Planner Report"),
        (REPORTS_DIR / "plan_review.md", "Plan Review"),
        (REPORTS_DIR / "implementation_report.md", "Implementation Report"),
        (REPORTS_DIR / "code_review.md", "Code Review"),
        (REPORTS_DIR / "fix_plan.md", "Fix Plan"),
        (REPORTS_DIR / "fix_plan_review.md", "Fix Plan Review"),
    ]:
        if not path.exists():
            path.write_text(f"# {title}\n\nStatus: not run\n", encoding="utf-8")
    audit("init")
    print("Triad supervisor initialized.")
    return 0


def lock_scaffold_command(_: argparse.Namespace) -> int:
    ensure_dirs()
    write_scaffold_manifest()
    audit("lock_scaffold", path=workflow_rel(SCAFFOLD_MANIFEST_PATH))
    print(f"TriadFlow scaffold lock written: {workflow_rel(SCAFFOLD_MANIFEST_PATH)}")
    return 0


def status_command(_: argparse.Namespace) -> int:
    state = load_state()
    print("Triad state")
    print(f"- active: {state.get('active')}")
    print(f"- mode: {state.get('mode')}")
    print(f"- current_phase: {state.get('current_phase')}")
    print(f"- current_task_id: {state.get('current_task_id')}")
    print(f"- iteration: {state.get('iteration')} / {state.get('max_iterations')}")
    print(f"- last_status: {state.get('last_status')}")
    print(f"- next_action: {state.get('next_action')}")
    print(f"- blocked_reason: {state.get('blocked_reason')}")
    print(f"- requires_user_approval: {state.get('requires_user_approval')}")
    print(f"- git: {'available' if in_git_repo() else 'not detected'}")
    audit("status")
    return 0


def plan_command(args: argparse.Namespace) -> int:
    check_high_risk_request(args.request)
    set_state(active=True, current_phase="planning", last_status="running", blocked_reason=None)
    prompt = build_prompt("planner", args.request)
    text = run_codex_role("planner", prompt, ROLE_REPORTS["planner"], "read-only")
    status = extract_status(text, "PLANNER_STATUS", {"PLAN_READY", "NEEDS_USER_INPUT", "BLOCKED"})
    update_agent_run("planner", ROLE_REPORTS["planner"])
    next_action = "review_plan" if status == "PLAN_READY" else "await_user_request"
    set_state(current_phase="planned", last_status=status, next_action=next_action, requires_user_approval=status == "NEEDS_USER_INPUT")
    print(f"Planner status: {status}")
    return 0


def review_plan_command(args: argparse.Namespace) -> int:
    require_files([PLAN_PATH])
    set_state(current_phase="reviewing_plan", last_status="running")
    prompt = build_prompt("reviewer_plan", getattr(args, "request", None))
    text = run_codex_role("reviewer_plan", prompt, ROLE_REPORTS["reviewer_plan"], "read-only")
    status = extract_status(text, "REVIEW_STATUS", {"PASS", "NEEDS_FIX", "BLOCKED", "USER_APPROVAL_REQUIRED"})
    update_agent_run("reviewer", ROLE_REPORTS["reviewer_plan"])
    next_action = "implement_next" if status == "PASS" else ("fix_plan" if status == "NEEDS_FIX" else "await_user_request")
    set_state(current_phase="plan_reviewed", last_status=status, next_action=next_action, requires_user_approval=status == "USER_APPROVAL_REQUIRED")
    print(f"Plan review status: {status}")
    return 0


def implement_next_command(args: argparse.Namespace) -> int:
    require_files([PLAN_PATH])
    before = git_status_summary()
    if "[clean]" not in before and "Git repository not detected" not in before:
        raise TriadError("Workspace has uncommitted changes. Supervisor stops before Developer run.")
    set_state(current_phase="implementing", last_status="running")
    prompt = build_prompt("developer", getattr(args, "request", None))
    text = run_codex_role("developer", prompt, ROLE_REPORTS["developer"], "workspace-write")
    status = extract_status(text, "DEVELOPER_STATUS", {"IMPLEMENTED", "BLOCKED", "USER_APPROVAL_REQUIRED"})
    update_agent_run("developer", ROLE_REPORTS["developer"])
    save_git_diff()
    after = git_status_summary()
    (REPORTS_DIR / "git_status_after_developer.txt").write_text(after, encoding="utf-8")
    next_action = "review_code" if status == "IMPLEMENTED" else "await_user_request"
    set_state(current_phase="implemented", last_status=status, next_action=next_action, requires_user_approval=status == "USER_APPROVAL_REQUIRED")
    print(f"Developer status: {status}")
    return 0


def review_code_command(args: argparse.Namespace) -> int:
    save_git_diff()
    set_state(current_phase="reviewing_code", last_status="running")
    prompt = build_prompt("reviewer_code", getattr(args, "request", None))
    text = run_codex_role("reviewer_code", prompt, ROLE_REPORTS["reviewer_code"], "read-only")
    status = extract_status(text, "REVIEW_STATUS", {"PASS", "NEEDS_FIX", "BLOCKED", "USER_APPROVAL_REQUIRED"})
    update_agent_run("reviewer", ROLE_REPORTS["reviewer_code"])
    next_action = "done" if status == "PASS" else ("fix_plan" if status == "NEEDS_FIX" else "await_user_request")
    set_state(current_phase="code_reviewed", last_status=status, next_action=next_action, requires_user_approval=status == "USER_APPROVAL_REQUIRED")
    print(f"Code review status: {status}")
    return 0


def fix_plan_command(args: argparse.Namespace) -> int:
    require_files([REPORTS_DIR / "code_review.md"])
    set_state(current_phase="fix_planning", last_status="running")
    prompt = build_prompt("planner_fix", getattr(args, "request", None))
    text = run_codex_role("planner_fix", prompt, ROLE_REPORTS["planner_fix"], "read-only")
    status = extract_status(text, "PLANNER_STATUS", {"FIX_PLAN_READY", "BLOCKED", "USER_APPROVAL_REQUIRED"})
    update_agent_run("planner", ROLE_REPORTS["planner_fix"])
    next_action = "review_fix_plan" if status == "FIX_PLAN_READY" else "await_user_request"
    set_state(current_phase="fix_planned", last_status=status, next_action=next_action, requires_user_approval=status == "USER_APPROVAL_REQUIRED")
    print(f"Fix planner status: {status}")
    return 0


def review_fix_plan_command(args: argparse.Namespace) -> int:
    require_files([REPORTS_DIR / "fix_plan.md"])
    set_state(current_phase="reviewing_fix_plan", last_status="running")
    prompt = build_prompt("reviewer_fix_plan", getattr(args, "request", None))
    text = run_codex_role("reviewer_fix_plan", prompt, ROLE_REPORTS["reviewer_fix_plan"], "read-only")
    status = extract_status(text, "REVIEW_STATUS", {"PASS", "NEEDS_FIX", "BLOCKED", "USER_APPROVAL_REQUIRED"})
    update_agent_run("reviewer", ROLE_REPORTS["reviewer_fix_plan"])
    next_action = "implement_next" if status == "PASS" else "await_user_request"
    set_state(current_phase="fix_plan_reviewed", last_status=status, next_action=next_action, requires_user_approval=status == "USER_APPROVAL_REQUIRED")
    print(f"Fix plan review status: {status}")
    return 0


def approve_plan_command(_: argparse.Namespace) -> int:
    require_files([PLAN_PATH])
    require_active_plan_status()
    state = load_state()
    state.setdefault("plan", {})
    state["plan"]["approval"] = "human_confirmed"
    state["plan"]["approved_at"] = now_iso()
    state["plan"]["path"] = rel(PLAN_PATH)
    state["plan"]["sha256"] = file_sha256(PLAN_PATH)
    state["active"] = True
    state["current_phase"] = "plan_approved"
    state["last_status"] = "PLAN_APPROVED"
    state["next_action"] = "review_plan"
    state["requires_user_approval"] = False
    state["blocked_reason"] = None
    save_state(state)
    audit("plan_approved", plan=rel(PLAN_PATH))
    print("PLAN.md marked as human-approved.")
    return 0


def audit_command(_: argparse.Namespace) -> int:
    problems: list[str] = []
    if in_git_repo():
        result = run_process(["git", "status", "--short", "--untracked-files=all"], timeout=30)
        tracked_runtime = []
        for line in result.stdout.splitlines():
            path = line[3:].replace("\\", "/") if len(line) > 3 else line
            if path == "PLAN.md" or path.startswith(".agent/reports/") or path.startswith(".agent/logs/") or path.startswith(".agent/tmp/"):
                tracked_runtime.append(line)
        if tracked_runtime:
            problems.append("Runtime files are staged or visible to git: " + "; ".join(tracked_runtime))
    else:
        problems.append("Git repository not detected; publishing audit is incomplete.")

    try:
        check_scaffold_manifest()
    except TriadError as exc:
        problems.append(str(exc))

    if list(PROJECT_ROOT.rglob("__pycache__")):
        problems.append("__pycache__ directories are present.")
    if not (PROJECT_ROOT / "README.md").exists():
        problems.append("README.md is missing.")

    if problems:
        for problem in problems:
            print(f"AUDIT: FAIL: {problem}")
        audit("audit", status="FAIL", problems=problems)
        return 1
    print("AUDIT: PASS")
    audit("audit", status="PASS")
    return 0


def run_once_command(args: argparse.Namespace) -> int:
    plan_command(args)
    if load_state().get("last_status") != "PLAN_READY":
        return 1
    review_plan_command(args)
    if load_state().get("last_status") != "PASS":
        return 1
    implement_next_command(args)
    if load_state().get("last_status") != "IMPLEMENTED":
        return 1
    review_code_command(args)
    return 0 if load_state().get("last_status") == "PASS" else 1


def execute_approved_plan_command(args: argparse.Namespace) -> int:
    require_approved_plan()
    state = load_state()
    max_iterations = args.max_iterations or state.get("max_iterations", 10)
    state["max_iterations"] = max_iterations
    state["active"] = True
    state["requires_user_approval"] = False
    state["blocked_reason"] = None
    if state.get("next_action") in {None, "", "await_user_request"}:
        state["next_action"] = "review_plan"
    save_state(state)
    return run_execution_loop(args, max_iterations)


def run_execution_loop(args: argparse.Namespace, max_iterations: int) -> int:
    for _ in range(max_iterations):
        state = load_state()
        state["iteration"] = int(state.get("iteration") or 0) + 1
        save_state(state)
        audit("loop_iteration", iteration=state["iteration"])
        next_action = load_state().get("next_action")
        if next_action == "review_plan":
            review_plan_command(args)
        if load_state().get("next_action") == "implement_next":
            implement_next_command(args)
        if load_state().get("next_action") == "review_code":
            review_code_command(args)
        status = load_state().get("last_status")
        if status == "PASS":
            set_state(active=False, current_phase="done", next_action="done")
            print("Loop stopped after reviewer PASS.")
            return 0
        if status in {"BLOCKED", "USER_APPROVAL_REQUIRED", "NEEDS_USER_INPUT"}:
            print(f"Loop stopped: {status}")
            return 1
        if load_state().get("next_action") == "fix_plan":
            fix_plan_command(args)
            if load_state().get("last_status") != "FIX_PLAN_READY":
                return 1
            review_fix_plan_command(args)
            if load_state().get("last_status") != "PASS":
                return 1
    set_state(last_status="BLOCKED", current_phase="stopped", blocked_reason="Maximum iterations reached", next_action="await_user_request")
    print("Loop stopped: maximum iterations reached.")
    return 1


def run_loop_command(args: argparse.Namespace) -> int:
    check_high_risk_request(args.request)
    require_approved_plan()
    state = load_state()
    max_iterations = args.max_iterations or state.get("max_iterations", 10)
    state["max_iterations"] = max_iterations
    state["active"] = True
    save_state(state)
    return run_execution_loop(args, max_iterations)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Triad Agent Workflow supervisor")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init").set_defaults(func=init_command)
    sub.add_parser("status").set_defaults(func=status_command)
    sub.add_parser("approve-plan").set_defaults(func=approve_plan_command)
    sub.add_parser("audit").set_defaults(func=audit_command)
    sub.add_parser("lock-scaffold").set_defaults(func=lock_scaffold_command)
    for name, func in [
        ("plan", plan_command),
        ("review-plan", review_plan_command),
        ("implement-next", implement_next_command),
        ("review-code", review_code_command),
        ("fix-plan", fix_plan_command),
        ("review-fix-plan", review_fix_plan_command),
        ("execute-approved-plan", execute_approved_plan_command),
        ("run-once", run_once_command),
        ("run-loop", run_loop_command),
    ]:
        p = sub.add_parser(name)
        p.add_argument("--request", default=None, help="User requirement for this workflow run")
        if name == "run-loop":
            p.add_argument("--max-iterations", type=int, default=None)
        p.set_defaults(func=func)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        ensure_dirs()
        if not is_scaffold_maintenance_command(args.command):
            check_scaffold_manifest()
        return int(args.func(args))
    except TriadError as exc:
        audit("supervisor_error", error=str(exc))
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
