---
name: triad-plan-loop
description: Use when the user asks for multi-agent development, independent review before and after implementation, automatic continuation through plan steps, or reduced single-agent context bias.
---

# Triad Plan Loop

Use this workflow when the user asks for:
- Multi-agent development.
- Independent review before or after implementation.
- Automatic continuation through approved plan steps.
- Reduced single-agent context bias.

## Required Behavior

- Use file-based handoff only.
- Do not share full chat history between roles.
- Planner and Reviewer are read-only roles.
- Developer writes code only after Reviewer approves the plan.
- Developer implements only the current approved task or approved fix plan.
- Reviewer must inspect the actual git diff after Developer work.
- Stop on high-risk operations, unclear requirements, unrelated dirty workspace, or missing required files.
- Keep PLAN.md and .agent/state.json updated.
- Keep .agent/reports/implementation_report.md current after each implementation.

## Role Boundaries

Planner:
- Creates and maintains PLAN.md.
- Creates .agent/reports/fix_plan.md from Reviewer findings.
- Does not edit implementation code.

Reviewer:
- Reviews PLAN.md, fix plans, implementation reports, git diff, and test output.
- Returns PASS, NEEDS_FIX, BLOCKED, or USER_APPROVAL_REQUIRED.
- Does not edit code.

Developer:
- Implements only approved plan steps.
- Writes .agent/reports/implementation_report.md.
- Does not approve its own work.

## References

Read these before running the workflow:
- references/workflow.md
- references/safety_policy.md
