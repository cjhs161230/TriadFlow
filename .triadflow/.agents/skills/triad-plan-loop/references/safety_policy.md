# Triad Safety Policy

The workflow is conservative by default.

Stop and require user approval for:
- Destructive filesystem operations.
- Destructive git operations.
- Deployment or release publishing.
- Package publication.
- Push, force-push, merge, rebase, or history rewriting.
- Production data access or mutation.
- Database deletion or irreversible migration.
- External payments, billing, or purchases.
- Secrets, tokens, credentials, SSH keys, browser cookies, or credential stores.
- Unclear requirements or ambiguous scope.
- Unrelated dirty workspace changes.
- Missing required handoff files.
- Codex CLI failure or unsupported required feature.

Planner and Reviewer must run with read-only access. Developer may use workspace-write only for approved steps. Do not use `danger-full-access` or `--yolo`.

Network access is disabled by default. If a task needs network access, stop and ask the user.
