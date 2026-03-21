"""Job wrapper: transparent execution logging for both cron and TUI runs.

Creates ~/.lazycron/run.sh which wraps job commands to log execution
results to ~/.lazycron/history.jsonl. LazyCron auto-wraps on save
and unwraps for display.
"""

from __future__ import annotations

import json
import os
import re
import shlex
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
# Use python3 for safe JSON encoding (handles quotes, backslashes, unicode)
python3 -c "
import json, sys
entry = {'ts': float(sys.argv[1]), 'msg': sys.argv[2], 'ok': sys.argv[3] == 'true'}
print(json.dumps(entry))
" "$TS" "$MSG" "$OK" >> "$LOG" 2>/dev/null || \
    printf '{"ts":%s,"msg":"log-encode-error","ok":null}\n' "$TS" >> "$LOG"
exit $EXIT
'''


def ensure_wrapper() -> None:
    """Create the wrapper script if it doesn't exist or is outdated."""
    LAZYCRON_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(LAZYCRON_DIR, 0o700)
    # Always update to latest version
    WRAPPER_PATH.write_text(_WRAPPER_SCRIPT)
    WRAPPER_PATH.chmod(0o700)


def wrap_command(job_name: str, command: str) -> str:
    """Wrap a command with the logging wrapper."""
    if is_wrapped(command):
        return command
    return f'{WRAPPER_PATH} {shlex.quote(job_name)} {shlex.quote(command)}'


def unwrap_command(command: str) -> Optional[str]:
    """Extract the original command from a wrapped command.

    Returns the original command, or None if not wrapped.
    """
    wrapper_str = str(WRAPPER_PATH)
    if not command.strip().startswith(wrapper_str):
        return None
    # Use shlex.split for safe parsing of both single- and double-quoted args
    try:
        parts = shlex.split(command.strip())
    except ValueError:
        return None
    # parts[0] = wrapper path, parts[1] = name, parts[2] = command
    if len(parts) >= 3 and parts[0] == wrapper_str:
        return parts[2]
    return None


def is_wrapped(command: str) -> bool:
    """Check if a command is already wrapped."""
    return command.strip().startswith(str(WRAPPER_PATH))


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
