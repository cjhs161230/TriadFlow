# TriadFlow

TriadFlow is a file-based three-agent workflow scaffold for Codex CLI projects.

It separates work into isolated roles:

- Planner creates `PLAN.md` and fix plans.
- Reviewer reviews plans, implementation reports, actual diffs, and test output.
- Developer implements only approved plan steps or approved fix plans.

The supervisor, `tools/triad_supervisor.py`, is the only component that decides the next workflow phase.

## Contents

- `tools/triad_supervisor.py` - conservative workflow supervisor.
- `prompts/` - role prompts for Planner, Reviewer, Developer, and fix-plan flow.
- `.agents/skills/triad-plan-loop/` - project-local skill instructions and safety policy.
- `.codex/` - optional Codex agent and hook configuration.
- `.agent/config.json` - supervisor configuration template.
- `.agent/schemas/` - optional output schemas.
- `TRIAD_AGENT_WORKFLOW.md` - detailed workflow guide.
- `tests/` - scaffold self-check tests.

Runtime files such as `PLAN.md`, `.agent/reports/`, `.agent/logs/`, and `.agent/tmp/` are intentionally ignored by Git.

## Quick Start

From the project root:

```powershell
python tools/triad_supervisor.py init
python tools/triad_supervisor.py status
```

Create a plan:

```powershell
python tools/triad_supervisor.py plan --request "Add config validation"
python tools/triad_supervisor.py review-plan
python tools/triad_supervisor.py implement-next
python tools/triad_supervisor.py review-code
```

Run one full cycle:

```powershell
python tools/triad_supervisor.py run-once --request "Add config validation"
```

## Validation

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -m unittest tests.test_triad_supervisor
python -m py_compile tools/triad_supervisor.py .codex/hooks/command_gatekeeper.py .codex/hooks/stop_guard.py tests/test_triad_supervisor.py
python tools/triad_supervisor.py status
```

On Windows, `py_compile` may need permission to write `__pycache__` under `.codex/hooks`.

## Safety Defaults

TriadFlow stops for destructive operations, deployment, package publishing, production data, secrets, credentials, external payments, missing handoff files, unsupported Codex CLI behavior, and unclear scope.

Planner and Reviewer are read-only roles. Developer uses workspace-write only for approved work.

Network access is disabled by default. Pushes, deployments, and external actions require explicit user approval.

## Codex CLI

The default supervisor config uses:

```json
"codex_command": "codex"
```

If `codex` is not on `PATH`, edit `.agent/config.json` and set `codex_command` to your local Codex CLI executable.

