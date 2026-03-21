"""Crontab file parser and serializer with round-trip fidelity.

Reads from `crontab -l` and writes via `crontab -`. Preserves comments,
blank lines, and formatting for untouched lines.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Optional

from lazycron.cron import CronExpression, parse_expression

# -- Data structures ----------------------------------------------------------


@dataclass
class Job:
    """A single cron job entry."""
    schedule: CronExpression
    command: str
    comment: str          # Inline comment (text after # in the command portion)
    enabled: bool         # False = line is commented out
    line_number: int      # 0-based line index in the crontab
    raw_line: str         # Original line text for round-trip fidelity

    @property
    def display_name(self) -> str:
        """Job name: uses comment if set, otherwise derives from command."""
        if self.comment and self.comment.strip():
            name = self.comment.strip()
        else:
            from lazycron.wrapper import display_command
            cmd = display_command(self.command).strip()
            # Use the last path component or first word
            if "/" in cmd:
                parts = cmd.split()
                name = parts[0].rstrip(";").split("/")[-1]
            else:
                name = cmd.split()[0] if cmd.split() else cmd
        # Truncate long names
        if len(name) > 30:
            name = name[:27] + "..."
        return name

    @property
    def display_cmd(self) -> str:
        """Command as displayed in the UI (unwrapped if needed)."""
        from lazycron.wrapper import display_command
        return display_command(self.command)


@dataclass
class EnvVar:
    """A crontab environment variable assignment (KEY=value)."""
    key: str
    value: str
    line_number: int
    raw_line: str


@dataclass
class CrontabFile:
    """Parsed representation of a complete crontab."""
    jobs: list[Job] = field(default_factory=list)
    env_vars: list[EnvVar] = field(default_factory=list)
    raw_lines: list[str] = field(default_factory=list)
    _modified_lines: dict[int, str] = field(default_factory=dict, repr=False)
    _deleted_lines: set[int] = field(default_factory=set, repr=False)
    _appended_lines: list[str] = field(default_factory=list, repr=False)

    def serialize(self) -> str:
        """Rebuild crontab text. Untouched lines use verbatim originals."""
        lines: list[str] = []
        for i, raw in enumerate(self.raw_lines):
            if i in self._deleted_lines:
                continue
            if i in self._modified_lines:
                lines.append(self._modified_lines[i])
            else:
                lines.append(raw)
        lines.extend(self._appended_lines)
        if not lines:
            return ""
        text = "\n".join(lines)
        # Ensure trailing newline (crontab convention)
        if not text.endswith("\n"):
            text += "\n"
        return text

    def mark_modified(self, line_number: int, new_line: str) -> None:
        """Mark a line as modified for serialization."""
        self._modified_lines[line_number] = new_line

    def mark_deleted(self, line_number: int) -> None:
        """Mark a line for deletion."""
        self._deleted_lines.add(line_number)

    def append_line(self, line: str) -> None:
        """Append a new line to the crontab."""
        self._appended_lines.append(line)

    def has_modifications(self) -> bool:
        """Check if any modifications have been made."""
        return bool(self._modified_lines or self._deleted_lines or self._appended_lines)


# -- Parsing ------------------------------------------------------------------

# Matches: optional leading #, then 5 cron fields, then the command
_CRON_RE = re.compile(
    r"^(?P<disabled>#\s*)?"
    r"(?P<m>\S+)\s+"
    r"(?P<h>\S+)\s+"
    r"(?P<dom>\S+)\s+"
    r"(?P<mon>\S+)\s+"
    r"(?P<dow>\S+)\s+"
    r"(?P<cmd>.+)$"
)

# Matches: KEY=value (env var assignment)
_ENV_RE = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<val>.*)$")


def _is_cron_field(token: str) -> bool:
    """Heuristic: does this look like a cron field (not a shell variable)?

    Cron fields are: *, a number, */N, N-M, N-M/S, N,M,P, or 3-letter
    day/month names (sun-sat, jan-dec). Plain English words like "Health"
    should NOT match.
    """
    if token == "*":
        return True
    # Must contain at least one digit, *, or a known 3-letter name
    has_cron_char = bool(re.search(r"[\d\*/]", token))
    if has_cron_char:
        # Verify overall structure: digits, *, -, /, commas, and short alpha names
        return bool(re.match(r"^[\d\*\-/,a-zA-Z]+$", token))
    # Check if it's purely a known name pattern (e.g., "mon-fri", "jan,apr")
    normalized = token.lower()
    known_names = {"sun", "mon", "tue", "wed", "thu", "fri", "sat",
                   "jan", "feb", "mar", "apr", "may", "jun",
                   "jul", "aug", "sep", "oct", "nov", "dec"}
    # Split on , and - to get individual tokens
    parts = re.split(r"[,\-]", normalized)
    return all(p in known_names for p in parts if p)


def parse(text: str) -> CrontabFile:
    """Parse crontab text into a CrontabFile."""
    ct = CrontabFile()
    lines = text.split("\n")
    # Remove trailing empty line if present (from trailing newline)
    if lines and lines[-1] == "":
        lines = lines[:-1]
    ct.raw_lines = lines

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Skip blank lines
        if not stripped:
            continue

        # Check for env var assignment (before comment check, since
        # commented-out env vars aren't env vars)
        if not stripped.startswith("#"):
            env_match = _ENV_RE.match(stripped)
            if env_match:
                ct.env_vars.append(EnvVar(
                    key=env_match.group("key"),
                    value=env_match.group("val").strip().strip('"').strip("'"),
                    line_number=i,
                    raw_line=line,
                ))
                continue

        # Pure comments (not disabled cron jobs)
        if stripped.startswith("#"):
            # Try to parse as a disabled cron job
            # Remove leading # and optional whitespace
            uncommented = re.sub(r"^#\s*", "", stripped)
            cron_match = _CRON_RE.match(uncommented)
            if cron_match and _is_cron_field(cron_match.group("m")):
                # This is a commented-out cron job
                cmd_full = cron_match.group("cmd")
                comment = ""
                # Extract inline comment
                cmd_part, _, comment_part = _split_command_comment(cmd_full)
                if comment_part:
                    comment = comment_part

                schedule = parse_expression(
                    f"{cron_match.group('m')} {cron_match.group('h')} "
                    f"{cron_match.group('dom')} {cron_match.group('mon')} "
                    f"{cron_match.group('dow')}"
                )
                ct.jobs.append(Job(
                    schedule=schedule,
                    command=cmd_part,
                    comment=comment,
                    enabled=False,
                    line_number=i,
                    raw_line=line,
                ))
                continue
            # Otherwise it's just a comment, skip
            continue

        # Try to parse as a cron job
        cron_match = _CRON_RE.match(stripped)
        if cron_match and _is_cron_field(cron_match.group("m")):
            cmd_full = cron_match.group("cmd")
            cmd_part, _, comment_part = _split_command_comment(cmd_full)
            comment = comment_part or ""

            schedule = parse_expression(
                f"{cron_match.group('m')} {cron_match.group('h')} "
                f"{cron_match.group('dom')} {cron_match.group('mon')} "
                f"{cron_match.group('dow')}"
            )
            ct.jobs.append(Job(
                schedule=schedule,
                command=cmd_part,
                comment=comment,
                enabled=True,
                line_number=i,
                raw_line=line,
            ))

    return ct


def _split_command_comment(cmd_full: str) -> tuple[str, bool, str]:
    """Split command from inline comment, respecting quoting.

    Returns (command, has_comment, comment_text).
    """
    in_single = False
    in_double = False
    escaped = False

    for i, ch in enumerate(cmd_full):
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            return cmd_full[:i].rstrip(), True, cmd_full[i + 1:].strip()

    return cmd_full.strip(), False, ""


# -- System crontab I/O ------------------------------------------------------

def load_system_crontab() -> tuple[Optional[CrontabFile], str]:
    """Load the current user's crontab.

    Returns (CrontabFile, error_message). error_message is empty on success.
    """
    try:
        result = subprocess.run(
            ["crontab", "-l"],
            capture_output=True, text=True, timeout=10,
        )
    except FileNotFoundError:
        return None, "crontab command not found"
    except subprocess.TimeoutExpired:
        return None, "crontab -l timed out"

    if result.returncode != 0:
        stderr = result.stderr.strip()
        if "no crontab for" in stderr.lower():
            return CrontabFile(), ""
        return None, f"crontab -l failed: {stderr}"

    return parse(result.stdout), ""


def save_system_crontab(ct: CrontabFile) -> str:
    """Write the crontab back to the system.

    Returns empty string on success, error message on failure.
    """
    text = ct.serialize()

    try:
        result = subprocess.run(
            ["crontab", "-"],
            input=text, capture_output=True, text=True, timeout=10,
        )
    except FileNotFoundError:
        return "crontab command not found"
    except subprocess.TimeoutExpired:
        return "crontab write timed out"

    if result.returncode != 0:
        return f"crontab write failed: {result.stderr.strip()}"

    return ""


# -- Job manipulation helpers -------------------------------------------------

def toggle_job(ct: CrontabFile, job: Job) -> None:
    """Toggle a job between enabled and disabled."""
    if job.enabled:
        # Disable: prepend #
        new_line = f"# {job.raw_line}" if not job.raw_line.startswith("#") else job.raw_line
        job.enabled = False
    else:
        # Enable: remove leading # and whitespace
        new_line = re.sub(r"^#\s*", "", job.raw_line)
        job.enabled = True

    job.raw_line = new_line
    ct.mark_modified(job.line_number, new_line)


def update_job(ct: CrontabFile, job: Job, schedule: str, command: str,
               comment: str = "") -> None:
    """Update a job's schedule and/or command."""
    job.schedule = parse_expression(schedule)
    job.command = command
    job.comment = comment

    prefix = "" if job.enabled else "# "
    comment_suffix = f" # {comment}" if comment else ""
    new_line = f"{prefix}{schedule} {command}{comment_suffix}"
    job.raw_line = new_line
    ct.mark_modified(job.line_number, new_line)


def delete_job(ct: CrontabFile, job: Job) -> None:
    """Delete a job from the crontab."""
    ct.mark_deleted(job.line_number)
    ct.jobs.remove(job)


def add_job(ct: CrontabFile, schedule: str, command: str,
            comment: str = "") -> Job:
    """Add a new job to the crontab."""
    comment_suffix = f" # {comment}" if comment else ""
    line = f"{schedule} {command}{comment_suffix}"
    ct.append_line(line)

    job = Job(
        schedule=parse_expression(schedule),
        command=command,
        comment=comment,
        enabled=True,
        line_number=len(ct.raw_lines) + len(ct._appended_lines) - 1,
        raw_line=line,
    )
    ct.jobs.append(job)
    return job
