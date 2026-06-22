# Triad Agent Workflow

This repository includes a project-local, file-based three-agent Codex CLI workflow.

## What It Does

The workflow separates planning, implementation, and review:
- A human and Codex prepare PLAN.md together, or the human writes PLAN.md directly.
- The human explicitly approves PLAN.md before automated execution starts.
- Planner creates fix plans from Reviewer findings.
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
- manifest.lock

## Isolated Install Layout

In target projects, prefer installing TriadFlow under `.triadflow/`:

```text
target-project/
  AGENTS.md
  README.md
  PLAN.md
  .triadflow/
    tools/
    prompts/
    .agent/
    .agents/
    .codex/
    manifest.lock
    README.md
    TRIAD_AGENT_WORKFLOW.md
```

`PLAN.md` and the business project README remain at the project root. TriadFlow internals remain under `.triadflow/`.

The root `AGENTS.md` should be a thin entrypoint pointing agents to `.triadflow/TRIAD_AGENT_WORKFLOW.md` and warning them not to modify `.triadflow/` unless the user explicitly requests scaffold maintenance.

Do not overwrite an existing project's `.gitignore` or `.gitattributes`. Append `.triadflow/templates/gitignore.snippet` to `.gitignore` when needed. Apply `.triadflow/templates/gitattributes.snippet` only with explicit project-owner approval.

## Scaffold Integrity

`manifest.lock` records hashes for key TriadFlow files. TriadFlow checks this lock at command boundaries, not before every file edit.

Commands that check scaffold integrity include `approve`, `go`, `review`, `implement`, `review-code`, `fix`, and `review-fix`.

After intentional scaffold maintenance, update the lock:

```powershell
python .triadflow/tools/triad.py lock-scaffold
```

## Shortcut Commands

Project slash-command definitions live in `.codex/commands/`. If your Codex CLI build loads project commands from that directory, use:

```text
/triad-init
/triad-status
/triad-approve
/triad-go
/triad-review
/triad-implement
/triad-review-code
/triad-fix
/triad-review-fix
/triad-audit
/triad-lock-scaffold
```

All slash commands have terminal fallbacks through `tools/triad.py`:

```powershell
python .triadflow/tools/triad.py init
python .triadflow/tools/triad.py status
python .triadflow/tools/triad.py approve
python .triadflow/tools/triad.py go --max-iterations 5
python .triadflow/tools/triad.py review
python .triadflow/tools/triad.py implement
python .triadflow/tools/triad.py review-code
python .triadflow/tools/triad.py fix
python .triadflow/tools/triad.py review-fix
python .triadflow/tools/triad.py audit
python .triadflow/tools/triad.py lock-scaffold
```

## Initialize

Windows PowerShell:

```powershell
python .triadflow/tools/triad_supervisor.py init
python .triadflow/tools/triad_supervisor.py status
```

Recommended Codex CLI bootstrap command:

```powershell
codex exec --sandbox workspace-write --ask-for-approval on-request -o .agent/reports/bootstrap_report.md "Initialize and verify the triad agent workflow scaffold."
```

## Approve A Human-Reviewed Plan

```powershell
python .triadflow/tools/triad_supervisor.py approve-plan
```

This records that `PLAN.md` has been reviewed and confirmed by the human operator.

`PLAN.md` must contain `Status: Active`. Approval records a SHA-256 hash of `PLAN.md`; if the file changes after approval, execution stops until the human reviews it and runs approval again.

## Execute An Approved Plan

```powershell
python .triadflow/tools/triad_supervisor.py execute-approved-plan --max-iterations 5
```

This starts automation after plan confirmation. It reviews the plan, implements approved work, reviews actual diffs, creates and reviews fix plans when needed, and repeats until PASS, BLOCKED, USER_APPROVAL_REQUIRED, missing files, Codex command failure, unrelated dirty workspace, or the iteration limit.

`run-loop` is retained for compatibility, but it also requires an existing human-approved `PLAN.md`. It no longer creates a plan automatically when `PLAN.md` is missing.

## Stop Safely

Set `.agent/state.json` fields:
- `active` to `false`
- `safety.allow_auto_continue` to `false`
- `requires_user_approval` to `true` when human review is needed

The stop guard does not force continuation just because PLAN.md has unfinished tasks.

## Inspect Reports

Use:

```powershell
python .triadflow/tools/triad_supervisor.py status
Get-Content .agent/reports/plan_review.md
Get-Content .agent/reports/implementation_report.md
Get-Content .agent/reports/code_review.md
Get-Content .agent/logs/audit.jsonl
```

## Validate The Scaffold

Use:

```powershell
python -m unittest discover -s .triadflow/tests
python -m py_compile .triadflow/tools/triad.py .triadflow/tools/triad_supervisor.py .triadflow/.codex/hooks/command_gatekeeper.py .triadflow/.codex/hooks/stop_guard.py .triadflow/tests/test_triad_cli.py .triadflow/tests/test_triad_supervisor.py
python .triadflow/tools/triad_supervisor.py status
```

On Windows, `py_compile` may need permission to write `__pycache__` under `.codex/hooks`.

## Recover From Interruption

1. Run `python .triadflow/tools/triad_supervisor.py status`.
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
- `.triadflow/.codex/hooks/command_gatekeeper.py`
- `.triadflow/.codex/hooks/stop_guard.py`

Hooks are conservative fallbacks. Codex CLI hook schemas can vary by installed version, so manual trust or schema adaptation may be required.

## Command Reference

```powershell
python .triadflow/tools/triad_supervisor.py init
python .triadflow/tools/triad_supervisor.py status
python .triadflow/tools/triad.py init
python .triadflow/tools/triad.py status
python .triadflow/tools/triad.py approve
python .triadflow/tools/triad.py go --max-iterations 5
python .triadflow/tools/triad.py audit
python .triadflow/tools/triad.py lock-scaffold
python .triadflow/tools/triad_supervisor.py plan --request "user requirement here"
python .triadflow/tools/triad_supervisor.py approve-plan
python .triadflow/tools/triad_supervisor.py review-plan
python .triadflow/tools/triad_supervisor.py implement-next
python .triadflow/tools/triad_supervisor.py review-code
python .triadflow/tools/triad_supervisor.py fix-plan
python .triadflow/tools/triad_supervisor.py review-fix-plan
python .triadflow/tools/triad_supervisor.py audit
python .triadflow/tools/triad_supervisor.py lock-scaffold
python .triadflow/tools/triad_supervisor.py execute-approved-plan --max-iterations 5
python .triadflow/tools/triad_supervisor.py run-once --request "Implement the first approved task in PLAN.md"
python .triadflow/tools/triad_supervisor.py run-loop --request "Continue the project according to PLAN.md" --max-iterations 5
```

## Known Limitations

- This v0.1 scaffold uses only Python standard library code.
- Custom agent TOML and hook loading depend on the installed Codex CLI version.
- If the installed Codex CLI does not support a feature, the supervisor still uses direct `codex exec` calls and role prompts as a safe fallback.
- The current supervisor does not parse PLAN.md into a structured task graph; it delegates task selection to the role prompt and stops conservatively on missing or unsafe context.
