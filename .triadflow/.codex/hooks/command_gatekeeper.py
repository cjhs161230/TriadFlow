#!/usr/bin/env python3
"""Conservative command gatekeeper for Codex hook use.

The Codex hook JSON contract can vary by CLI version. This script accepts JSON
on stdin when available, falls back to argv text, logs a decision, and exits
non-zero only for clearly denied commands.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / ".agent" / "logs" / "audit.jsonl"

DENY_PATTERNS = [
    r"\brm\s+-rf\s+/",
    r"\bRemove-Item\b.*\b-Recurse\b.*\b-Force\b.*(?:C:\\|/)",
    r"\bdel\s+/s\s+/q\s+C:\\",
    r"\bgit\s+push\b.*\b--force\b",
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+clean\s+-[a-zA-Z]*[fxd]",
    r"\bcurl\b.*\|\s*(?:sh|bash|powershell|pwsh)\b",
    r"\bwget\b.*\|\s*(?:sh|bash|powershell|pwsh)\b",
    r"\bpowershell\b.*\b-EncodedCommand\b",
    r"\bpwsh\b.*\b-EncodedCommand\b",
    r"(?:^|\s)(?:cat|type|Get-Content)\s+.*(?:\.env|id_rsa|id_ed25519|credentials|token|cookies?)",
    r"\bdeploy\b",
    r"\bpublish\b",
    r"\bproduction\b.*\bdelete\b",
    r"\bdrop\s+database\b",
]

ALLOW_PATTERNS = [
    r"^git\s+status\b",
    r"^git\s+diff\b",
    r"^git\s+log\b",
    r"^python\s+-m\s+pytest\b",
    r"^pytest\b",
    r"^npm\s+test\b",
    r"^npm\s+run\s+test\b",
    r"^npm\s+run\s+lint\b",
    r"^npm\s+run\s+build\b",
    r"^pnpm\s+test\b",
    r"^pnpm\s+lint\b",
    r"^tsc\s+--noEmit\b",
]


def log(decision: str, command: str, reason: str) -> None:
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "time": dt.datetime.now(dt.timezone.utc).isoformat(),
        "event": "command_gatekeeper",
        "decision": decision,
        "command": command,
        "reason": reason,
    }
    with AUDIT.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=True, sort_keys=True) + "\n")


def extract_command() -> str:
    raw = sys.stdin.read()
    if raw.strip():
        try:
            data = json.loads(raw)
            for key in ("command", "cmd", "input"):
                value = data.get(key) if isinstance(data, dict) else None
                if isinstance(value, str):
                    return value
            return raw.strip()
        except json.JSONDecodeError:
            return raw.strip()
    return " ".join(sys.argv[1:]).strip()


def main() -> int:
    command = extract_command()
    normalized = " ".join(command.split())
    for pattern in DENY_PATTERNS:
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            log("deny", normalized, pattern)
            print(json.dumps({"decision": "deny", "reason": pattern}))
            return 1
    for pattern in ALLOW_PATTERNS:
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            log("allow", normalized, pattern)
            print(json.dumps({"decision": "allow", "reason": pattern}))
            return 0
    log("defer", normalized, "uncertain command; defer to normal approval")
    print(json.dumps({"decision": "defer", "reason": "uncertain command; defer to normal approval"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
