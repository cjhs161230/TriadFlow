# Repository Agent Instructions

When working in this repository, follow any nested AGENTS.md or AGENTS.override.md files that apply to the files being changed.

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
