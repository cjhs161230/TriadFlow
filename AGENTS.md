# Repository Agent Instructions

<!-- TRIADFLOW:PROTECTED:START -->
When working in this repository, follow any nested AGENTS.md or AGENTS.override.md files that apply to the files being changed.

This repository uses TriadFlow. Before executing workflow commands, read and follow `.triadflow/TRIAD_AGENT_WORKFLOW.md`.

Do not modify `.triadflow/` unless the user explicitly asks for scaffold maintenance.

## Triad Agent Workflow Addendum

When working in this repository, respect the Triad Agent Workflow.

- Do not let a single agent plan, implement, and approve its own work.
- Planner and Reviewer are read-only roles.
- Developer implements only approved tasks.
- Use PLAN.md and .agent/state.json as the source of truth.
- After each implementation, update implementation_report.md.
- Reviewer must inspect git diff before PASS.
- Stop for destructive, deployment, secret, credential, production, or ambiguous operations.
- Do not auto-continue unless .agent/state.json explicitly allows it.
- TriadFlow lives under `.triadflow/`; do not modify `.triadflow/` unless the user explicitly asks for scaffold maintenance.
- TriadFlow scaffold integrity is checked at command boundaries through `manifest.lock`, not before every file edit.

## Project Planning Rules

- PLAN.md is the source of truth for executable plans.
- Do not execute PLAN.md unless it contains `Status: Active` and has been human-approved through the workflow.
- After a plan is approved, do not change objectives, scope, steps, priorities, validation approach, risk assessment, or next actions without explicit user approval.
- During execution, only update existing step execution status in PLAN.md.

## Documentation Rules

- Update README.md when changes affect user-visible behavior, commands, configuration, setup, dependencies, usage, project structure, known limitations, publishing notes, or installation instructions.
- Keep responses concise, but always include validation performed, skipped validation, blockers, risks, and important assumptions.

## Publishing Safety

- Before publishing, packaging, or pushing, run the available audit workflow.
- Do not include local logs, reports, caches, test artifacts, real environment files, credentials, local-only paths, or secrets.
<!-- TRIADFLOW:PROTECTED:END -->
