"""Job wrapper: transparent execution logging for both cron and TUI runs.

Creates ~/.lazycron/run.sh which wraps job commands to log execution
results to ~/.lazycron/history.jsonl. LazyCron auto-wraps on save
and unwraps for display.
"""

from __future__ import annotations

import json
import shlex as _shlex
import stat
import time as _time
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
bash -c "set -o pipefail; $CMD" </dev/null
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

_LAST_RUN_CACHE: dict[str, tuple[Optional[LogEntry], float]] = {}
_LAST_RUN_CACHE_TTL = 2.0


def ensure_wrapper() -> None:
    """Create the wrapper script if it doesn't exist or is outdated."""
    LAZYCRON_DIR.mkdir(parents=True, exist_ok=True)
    # Always update to latest version
    WRAPPER_PATH.write_text(_WRAPPER_SCRIPT)
    st = WRAPPER_PATH.stat()
    WRAPPER_PATH.chmod(st.st_mode | stat.S_IXUSR | stat.S_IXGRP)


def wrap_command(job_name: str, command: str) -> str:
    """Wrap a command with the logging wrapper."""
    if is_wrapped(command):
        return command
    safe_name = _shlex.quote(job_name)
    safe_cmd = _shlex.quote(command)
    return f'cat {WRAPPER_PATH} | /bin/sh -s {safe_name} {safe_cmd}'


def unwrap_command(command: str) -> Optional[str]:
    """Extract the original command from a wrapped command.

    Supports both current (shlex.quote) and legacy (manual quoting) formats.
    Returns the original command, or None if not wrapped.
    """
    wrapper_str = str(WRAPPER_PATH)
    cmd = command.strip()

    new_prefix = f"cat {wrapper_str} | /bin/sh -s "
    if cmd.startswith(new_prefix):
        rest = cmd[len(new_prefix):]
        try:
            parts = _shlex.split(rest)
            return parts[1] if len(parts) >= 2 else None
        except ValueError:
            return None

    if cmd.startswith(wrapper_str + " "):
        rest = cmd[len(wrapper_str):].strip()
        try:
            parts = _shlex.split(rest)
            return parts[1] if len(parts) >= 2 else None
        except ValueError:
            return None

    return None


def is_wrapped(command: str) -> bool:
    """Check if a command is already wrapped."""
    cmd = command.strip()
    wrapper_str = str(WRAPPER_PATH)
    return cmd.startswith(f"cat {wrapper_str}") or cmd.startswith(wrapper_str + " ")


def display_command(command: str) -> str:
    """Return the command as it should be displayed (unwrapped if needed)."""
    orig = unwrap_command(command)
    return orig if orig is not None else command


def get_last_run(job_name: str) -> Optional[LogEntry]:
    """Get the most recent log entry for a job by name.

    Uses a TTL cache to avoid re-reading history.jsonl on every frame.
    The cache expires after _LAST_RUN_CACHE_TTL seconds.
    """
    now = _time.time()
    cached = _LAST_RUN_CACHE.get(job_name)
    if cached is not None and (now - cached[1]) < _LAST_RUN_CACHE_TTL:
        return cached[0]

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
    _LAST_RUN_CACHE[job_name] = (last, now)
    return last
