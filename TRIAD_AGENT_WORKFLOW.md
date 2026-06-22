# Triad Agent Workflow

This repository includes a project-local, file-based three-agent Codex CLI workflow.

## What It Does

The workflow separates planning, implementation, and review:
- Planner creates and maintains PLAN.md and fix plans.
- Reviewer independently reviews plans, fix plans, implementation reports, git diff, and test output.
- Developer implements only approved plan steps or approved fix plans.

The supervisor script, `tools/triad_supervisor.py`, is the only component that decides the next phase.

## Why Agents Are Isolated

Each role is invoked through a fresh `codex exec` call. Agents do not share chat history. This reduces context bias and prevents the Developer from approving its own work.

## File-Based Handoff

Agents communicate through:
- PLAN.md
- .agent/state.json
- .agent/reports/planner_report.md
- .agent/reports/plan_review.md
- .agent/reports/implementation_report.md
- .agent/reports/code_review.md
- .agent/reports/fix_plan.md
- .agent/reports/fix_plan_review.md
- .agent/reports/latest_diff.patch
- .agent/reports/test_output.txt
- .agent/logs/audit.jsonl

## Initialize

Windows PowerShell:

```powershell
python tools/triad_supervisor.py init
python tools/triad_supervisor.py status
```

Recommended Codex CLI bootstrap command:

```powershell
codex exec --sandbox workspace-write --ask-for-approval on-request -o .agent/reports/bootstrap_report.md "Initialize and verify the triad agent workflow scaffold."
```

## Run One Cycle

```powershell
python tools/triad_supervisor.py run-once --request "Implement the first approved task in PLAN.md"
```

This runs plan, plan review, implementation, and code review once.

## Run A Loop

```powershell
python tools/triad_supervisor.py run-loop --request "Continue the project according to PLAN.md" --max-iterations 5
```

The loop stops on PASS, BLOCKED, USER_APPROVAL_REQUIRED, missing files, high-risk requests, Codex command failure, unrelated dirty workspace, or the iteration limit.

## Stop Safely

Set `.agent/state.json` fields:
- `active` to `false`
- `safety.allow_auto_continue` to `false`
- `requires_user_approval` to `true` when human review is needed

The stop guard does not force continuation just because PLAN.md has unfinished tasks.

## Inspect Reports

Use:

```powershell
python tools/triad_supervisor.py status
Get-Content .agent/reports/plan_review.md
Get-Content .agent/reports/implementation_report.md
Get-Content .agent/reports/code_review.md
Get-Content .agent/logs/audit.jsonl
```

## Validate The Scaffold

Use:

```powershell
python -m unittest tests.test_triad_supervisor
python -m py_compile tools/triad_supervisor.py .codex/hooks/command_gatekeeper.py .codex/hooks/stop_guard.py tests/test_triad_supervisor.py
python tools/triad_supervisor.py status
```

On Windows, `py_compile` may need permission to write `__pycache__` under `.codex/hooks`.

## Recover From Interruption

1. Run `python tools/triad_supervisor.py status`.
2. Inspect `.agent/state.json`.
3. Inspect the latest report in `.agent/reports/`.
4. Resume from the next explicit command, such as `review-plan`, `implement-next`, or `review-code`.
5. Do not use cross-role `codex exec resume`.

## Never Automated

The workflow never automatically performs:
- Deployment or release publishing.
- Package publication.
- Push, force-push, merge, rebase, reset, clean, or history rewriting.
- Production data mutation.
- Database deletion.
- External payments or billing operations.
- Secret, credential, token, SSH key, browser cookie, or credential-store access.
- Destructive filesystem operations.

## Customize Prompts

Edit files in `prompts/`:
- `planner.md`
- `reviewer_plan.md`
- `developer.md`
- `reviewer_code.md`
- `planner_fix.md`
- `reviewer_fix_plan.md`

Keep role boundaries intact. Planner and Reviewer should remain read-only.

## Customize Safety Policy

Edit:
- `.agents/skills/triad-plan-loop/references/safety_policy.md`
- `.agent/config.json`
- `.codex/hooks/command_gatekeeper.py`
- `.codex/hooks/stop_guard.py`

Hooks are conservative fallbacks. Codex CLI hook schemas can vary by installed version, so manual trust or schema adaptation may be required.

## Command Reference

```powershell
python tools/triad_supervisor.py init
python tools/triad_supervisor.py status
python tools/triad_supervisor.py plan --request "user requirement here"
python tools/triad_supervisor.py review-plan
python tools/triad_supervisor.py implement-next
python tools/triad_supervisor.py review-code
python tools/triad_supervisor.py fix-plan
python tools/triad_supervisor.py review-fix-plan
python tools/triad_supervisor.py run-once --request "Implement the first approved task in PLAN.md"
python tools/triad_supervisor.py run-loop --request "Continue the project according to PLAN.md" --max-iterations 5
```

## Known Limitations

- This v0.1 scaffold uses only Python standard library code.
- Custom agent TOML and hook loading depend on the installed Codex CLI version.
- If the installed Codex CLI does not support a feature, the supervisor still uses direct `codex exec` calls and role prompts as a safe fallback.
- The current supervisor does not parse PLAN.md into a structured task graph; it delegates task selection to the role prompt and stops conservatively on missing or unsafe context.
