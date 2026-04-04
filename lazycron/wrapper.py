"""Job wrapper: transparent execution logging for both cron and TUI runs.

Creates ~/.lazycron/run.sh which wraps job commands to log execution
results to ~/.lazycron/history.jsonl. LazyCron auto-wraps on save
and unwraps for display.
"""

from __future__ import annotations

import json
import os
import re
import stat
from pathlib import Path
from typing import Optional

from lazycron.state import LogEntry

LAZYCRON_DIR = Path.home() / ".lazycron"
WRAPPER_PATH = LAZYCRON_DIR / "run.sh"
HISTORY_FILE = LAZYCRON_DIR / "history.jsonl"

_WRAPPER_SCRIPT = r'''#!/bin/sh
# LazyCron job wrapper — logs execution to history
# Usage: run.sh "job_name" "command"
NAME="$1"
CMD="$2"
LOG="$HOME/.lazycron/history.jsonl"
mkdir -p "$(dirname "$LOG")"
# Source user env if present (survives wrapper regeneration)
[ -f "$HOME/.lazycron/env.sh" ] && . "$HOME/.lazycron/env.sh"
/bin/sh -c "$CMD"
EXIT=$?
TS=$(python3 -c "import time; print(time.time())" 2>/dev/null || date +%s)
if [ $EXIT -eq 0 ]; then
    MSG="$NAME — success"
    OK=true
else
    MSG="$NAME — failed (exit $EXIT)"
    OK=false
fi
printf '{"ts":%s,"msg":"%s","ok":%s}\n' "$TS" "$MSG" "$OK" >> "$LOG"
exit $EXIT
'''


def ensure_wrapper() -> None:
    """Create the wrapper script if it doesn't exist or is outdated."""
    LAZYCRON_DIR.mkdir(parents=True, exist_ok=True)
    # Always update to latest version
    WRAPPER_PATH.write_text(_WRAPPER_SCRIPT)
    WRAPPER_PATH.chmod(WRAPPER_PATH.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)


def wrap_command(job_name: str, command: str) -> str:
    """Wrap a command with the logging wrapper."""
    if is_wrapped(command):
        return command
    # Escape double quotes in name and command for shell safety
    safe_name = job_name.replace('"', '\\"')
    safe_cmd = command.replace('"', '\\"')
    return f'cat {WRAPPER_PATH} | /bin/sh -s "{safe_name}" "{safe_cmd}"'


def unwrap_command(command: str) -> Optional[str]:
    """Extract the original command from a wrapped command.

    Returns the original command, or None if not wrapped.
    """
    wrapper_str = str(WRAPPER_PATH)
    cmd = command.strip()
    # New format: cat /path/run.sh | /bin/sh -s "name" "command"
    m = re.match(
        rf'^cat\s+{re.escape(wrapper_str)}\s*\|\s*/bin/sh\s+-s\s+"[^"]*"\s+"(.*)"$',
        cmd,
    )
    if m:
        return m.group(1).replace('\\"', '"')
    # Legacy format: /path/run.sh "name" "command"
    if cmd.startswith(wrapper_str):
        m = re.match(
            rf'^{re.escape(wrapper_str)}\s+"[^"]*"\s+"(.*)"$',
            cmd,
        )
        if m:
            return m.group(1).replace('\\"', '"')
    return None


def is_wrapped(command: str) -> bool:
    """Check if a command is already wrapped."""
    cmd = command.strip()
    wrapper_str = str(WRAPPER_PATH)
    return cmd.startswith(f"cat {wrapper_str}") or cmd.startswith(wrapper_str)


def display_command(command: str) -> str:
    """Return the command as it should be displayed (unwrapped if needed)."""
    orig = unwrap_command(command)
    return orig if orig is not None else command


def get_last_run(job_name: str) -> Optional[LogEntry]:
    """Get the most recent log entry for a job by name."""
    if not HISTORY_FILE.exists():
        return None
    last: Optional[LogEntry] = None
    try:
        with open(HISTORY_FILE) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    msg = d.get("msg", "")
                    # Match by job name prefix (before the " — ")
                    if msg.startswith(f"{job_name} — "):
                        last = LogEntry(
                            timestamp=d["ts"],
                            message=msg,
                            success=d.get("ok"),
                        )
                except (json.JSONDecodeError, KeyError):
                    continue
    except OSError:
        pass
    return last
