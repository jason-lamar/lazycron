"""Platform-specific cron log reading (macOS/Linux).

Reads cron execution history from system logs to populate
the History panel.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class ExecutionRecord:
    """A single cron execution record parsed from system logs."""
    timestamp: Optional[datetime]
    command: str
    exit_code: int
    user: str
    raw_line: str

    @property
    def success(self) -> bool:
        return self.exit_code == 0

    @property
    def time_str(self) -> str:
        if self.timestamp:
            return self.timestamp.strftime("%m-%d %H:%M:%S")
        return "??-?? ??:??:??"


def get_cron_logs(limit: int = 50) -> list[str]:
    """Get raw cron log lines from the system.

    Returns a list of log line strings (newest last).
    """
    if sys.platform == "darwin":
        return _get_macos_logs(limit)
    else:
        return _get_linux_logs(limit)


def _get_macos_logs(limit: int) -> list[str]:
    """Read cron logs from macOS unified log."""
    try:
        result = subprocess.run(
            [
                "/usr/bin/log", "show",
                "--predicate", 'process == "cron" OR process == "com.apple.cron"',
                "--last", "24h",
                "--style", "compact",
            ],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            return []
        lines = result.stdout.strip().split("\n")
        # Skip header lines
        lines = [l for l in lines if l and not l.startswith("Filtering")]
        return lines[-limit:]
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return []


def _get_linux_logs(limit: int) -> list[str]:
    """Read cron logs from journalctl or syslog."""
    # Try journalctl first
    try:
        result = subprocess.run(
            ["journalctl", "-u", "cron", "-n", str(limit), "--no-pager"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split("\n")
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    # Fall back to syslog
    try:
        result = subprocess.run(
            ["grep", "CRON", "/var/log/syslog"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            return lines[-limit:]
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    return []


def get_job_history(command: str, limit: int = 10) -> list[ExecutionRecord]:
    """Get execution history for a specific job command.

    Attempts to match log entries against the command string.
    """
    all_logs = get_cron_logs(200)
    records: list[ExecutionRecord] = []

    # Normalize command for matching
    cmd_key = _normalize_command(command)

    for line in all_logs:
        if cmd_key and cmd_key in line.lower():
            rec = _parse_log_line(line)
            if rec:
                records.append(rec)

    # Return most recent entries
    return records[-limit:]


def _normalize_command(command: str) -> str:
    """Extract a searchable key from a command string."""
    # Use the base command name (last path component)
    parts = command.strip().split()
    if not parts:
        return ""
    cmd = parts[0].split("/")[-1].lower()
    return cmd


# macOS log format: 2026-03-01 09:15:00.123 ... CMD (command)
_MACOS_CMD_RE = re.compile(r"CMD\s*\((.+?)\)")
_MACOS_TS_RE = re.compile(r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})")

# Linux syslog format: Mar  1 09:15:01 host CRON[pid]: (user) CMD (command)
_LINUX_CMD_RE = re.compile(r"CMD\s*\((.+?)\)")
_LINUX_TS_RE = re.compile(r"(\w{3}\s+\d+\s+\d{2}:\d{2}:\d{2})")


def _parse_log_line(line: str) -> Optional[ExecutionRecord]:
    """Attempt to parse a cron log line into an ExecutionRecord."""
    # Try to extract timestamp
    ts = None
    ts_match = _MACOS_TS_RE.search(line) or _LINUX_TS_RE.search(line)
    if ts_match:
        try:
            ts = datetime.strptime(ts_match.group(1), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            try:
                # Linux syslog format — use current year
                ts_str = f"{datetime.now().year} {ts_match.group(1)}"
                ts = datetime.strptime(ts_str, "%Y %b %d %H:%M:%S")
            except ValueError:
                pass

    # Extract command
    cmd_match = _MACOS_CMD_RE.search(line) or _LINUX_CMD_RE.search(line)
    cmd = cmd_match.group(1) if cmd_match else ""

    # Exit code: we can't reliably get this from logs, default to 0
    # unless the log line contains error indicators
    exit_code = 0
    if "error" in line.lower() or "fail" in line.lower():
        exit_code = 1

    return ExecutionRecord(
        timestamp=ts,
        command=cmd,
        exit_code=exit_code,
        user="",
        raw_line=line,
    )
