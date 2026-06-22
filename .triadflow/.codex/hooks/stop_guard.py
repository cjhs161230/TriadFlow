#!/usr/bin/env python3
"""Fail-safe stop guard for the Triad Agent Workflow."""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / ".agent" / "state.json"
AUDIT = ROOT / ".agent" / "logs" / "audit.jsonl"


def log(decision: str, reason: str) -> None:
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "time": dt.datetime.now(dt.timezone.utc).isoformat(),
        "event": "stop_guard",
        "decision": decision,
        "reason": reason,
    }
    with AUDIT.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=True, sort_keys=True) + "\n")


def main() -> int:
    try:
        state = json.loads(STATE.read_text(encoding="utf-8"))
    except Exception as exc:
        log("stop", f"state unavailable: {exc}")
        print(json.dumps({"decision": "stop", "reason": "state unavailable"}))
        return 0

    safety = state.get("safety", {})
    if not state.get("active"):
        reason = "workflow inactive"
    elif not safety.get("allow_auto_continue"):
        reason = "auto-continue disabled"
    elif state.get("requires_user_approval"):
        reason = "user approval required"
    elif state.get("blocked_reason"):
        reason = "blocked reason present"
    elif int(state.get("iteration") or 0) >= int(state.get("max_iterations") or 0):
        reason = "iteration limit reached"
    elif state.get("next_action") in {None, "", "await_user_request", "done"}:
        reason = "no clear next action"
    else:
        log("continue", str(state.get("next_action")))
        print(json.dumps({"decision": "continue", "next_action": state.get("next_action")}))
        return 0

    log("stop", reason)
    print(json.dumps({"decision": "stop", "reason": reason}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
