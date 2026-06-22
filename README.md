# TriadFlow Template

<!-- TRIADFLOW:PROTECTED:START -->
This repository is a TriadFlow template. The workflow scaffold lives under `.triadflow/` so project files and workflow internals stay separated.

Root-level files are intentionally small:

- `AGENTS.md` - thin project entrypoint for agents.
- `README.md` - this template overview.
- `PLAN.md` - created per project and ignored by Git.
- `.triadflow/` - TriadFlow tools, prompts, state, reports, hooks, docs, and scaffold lock.
- `.triadflow/tests/` - scaffold self-check tests.

Detailed workflow documentation is in `.triadflow/TRIAD_AGENT_WORKFLOW.md`.

For existing projects, do not overwrite `.gitignore` or `.gitattributes`. Append the relevant snippets from:

```text
.triadflow/templates/gitignore.snippet
.triadflow/templates/gitattributes.snippet
```

## Quick Start

From the project root:

```powershell
python .triadflow/tools/triad.py init
python .triadflow/tools/triad.py status
```

Prepare and approve a plan:

```powershell
# Talk with Codex in the target project and create PLAN.md.
# Review PLAN.md yourself, then mark it approved:
python .triadflow/tools/triad.py approve
```

Execute the approved plan:

```powershell
python .triadflow/tools/triad.py go --max-iterations 5
```

Manual phase commands are still available:

```powershell
python .triadflow/tools/triad.py review
python .triadflow/tools/triad.py implement
python .triadflow/tools/triad.py review-code
```

## Slash Commands

If your Codex CLI build loads project commands from `.triadflow/.codex/commands/`, use:

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
```

If slash commands are not available in your Codex surface, use the equivalent terminal shortcuts:

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

`PLAN.md` must contain `Status: Active` before it can be approved. `approve` records the plan hash; if `PLAN.md` changes afterward, run `approve` again before `go`.

`lock-scaffold` is only for intentional TriadFlow maintenance. Normal project development should not update the scaffold lock.

## Isolated Install Layout

For a target project, install TriadFlow under `.triadflow/`:

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

In this layout, business project files stay at the project root. TriadFlow state, reports, prompts, hooks, and tools stay under `.triadflow/`.

The root `AGENTS.md` should be a small pointer that tells agents to follow `.triadflow/TRIAD_AGENT_WORKFLOW.md` and not modify `.triadflow/` unless the user explicitly asks to maintain the scaffold.

When installing into an existing Git repository, do not replace its `.gitignore` or `.gitattributes`. Append `.triadflow/templates/gitignore.snippet` to the existing `.gitignore`. Apply `.triadflow/templates/gitattributes.snippet` only if the project owner wants TriadFlow's line-ending normalization.

## Validation

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -m unittest discover -s .triadflow/tests
python -m py_compile .triadflow/tools/triad.py .triadflow/tools/triad_supervisor.py .triadflow/.codex/hooks/command_gatekeeper.py .triadflow/.codex/hooks/stop_guard.py .triadflow/tests/test_triad_cli.py .triadflow/tests/test_triad_supervisor.py
python .triadflow/tools/triad.py status
```

On Windows, `py_compile` may need permission to write `__pycache__` under `.codex/hooks`.

## Safety Defaults

TriadFlow stops for destructive operations, deployment, package publishing, production data, secrets, credentials, external payments, missing handoff files, unsupported Codex CLI behavior, and unclear scope.

Planner and Reviewer are read-only roles. Developer uses workspace-write only for approved work.

Automated execution requires `PLAN.md` plus `/triad-approve` or `python .triadflow/tools/triad.py approve`.

Network access is disabled by default. Pushes, deployments, and external actions require explicit user approval.

Before publishing or packaging, run:

```powershell
python .triadflow/tools/triad.py audit
```

TriadFlow checks `manifest.lock` at command boundaries such as `approve`, `go`, `review`, `implement`, and `review-code`. It does not check before every file edit.

## Codex CLI

The default supervisor config uses:

```json
"codex_command": "codex"
```

If `codex` is not on `PATH`, edit `.agent/config.json` and set `codex_command` to your local Codex CLI executable.
<!-- TRIADFLOW:PROTECTED:END -->
