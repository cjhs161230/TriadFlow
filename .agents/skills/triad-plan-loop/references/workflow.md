# Triad Agent Workflow

The supervisor is the only component that decides phase transitions.

Default state flow:

1. User requirement or existing PLAN.md.
2. Planner creates or updates PLAN.md and planner_report.md.
3. Reviewer reviews PLAN.md and writes plan_review.md.
4. Developer implements only an approved next step and writes implementation_report.md.
5. Supervisor saves latest_diff.patch and optional test_output.txt.
6. Reviewer reviews actual diff, report, and test output and writes code_review.md.
7. If NEEDS_FIX, Planner writes fix_plan.md.
8. Reviewer reviews fix_plan.md.
9. Developer applies approved fix.
10. Repeat until PASS, BLOCKED, USER_APPROVAL_REQUIRED, DONE, or max iterations.

Communication is through files only. Fresh `codex exec` calls should be used for each role. Do not use `codex exec resume` across roles.

Key files:
- PLAN.md is the plan source of truth.
- .agent/state.json is the workflow state source of truth.
- .agent/reports/*.md contains handoff reports.
- .agent/reports/latest_diff.patch contains the reviewed diff.
- .agent/logs/audit.jsonl records supervisor and hook events.
