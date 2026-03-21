"""Run Now: execute a job command with timeout and output capture.

Runs the command in a subprocess, captures stdout/stderr, and returns
the result. Includes a timeout to prevent runaway processes.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass

DEFAULT_TIMEOUT = 600  # 10 minutes


@dataclass
class RunResult:
    """Result of a Run Now execution."""
    command: str
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool

    @property
    def output(self) -> str:
        """Combined stdout + stderr output."""
        parts = []
        if self.stdout.strip():
            parts.append(self.stdout.strip())
        if self.stderr.strip():
            parts.append(f"[stderr]\n{self.stderr.strip()}")
        if self.timed_out:
            parts.append(f"[timed out after {DEFAULT_TIMEOUT}s]")
        return "\n".join(parts) if parts else "(no output)"


def run_command(command: str, timeout: int = DEFAULT_TIMEOUT,
                env_vars: dict[str, str] | None = None) -> RunResult:
    """Execute a command string and capture output.

    Uses /bin/sh -c for shell interpretation, matching how cron executes commands.
    Environment variables from the crontab are merged into the environment.
    """
    # Build environment
    env = os.environ.copy()
    if env_vars:
        env.update(env_vars)

    timed_out = False
    try:
        result = subprocess.run(
            ["/bin/sh", "-c", command],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            cwd=os.path.expanduser("~"),
        )
        return RunResult(
            command=command,
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            timed_out=False,
        )
    except subprocess.TimeoutExpired as e:
        return RunResult(
            command=command,
            exit_code=-1,
            stdout=e.stdout.decode() if e.stdout else "",
            stderr=e.stderr.decode() if e.stderr else "",
            timed_out=True,
        )
    except FileNotFoundError:
        return RunResult(
            command=command,
            exit_code=127,
            stdout="",
            stderr="sh: command not found",
            timed_out=False,
        )
    except OSError as e:
        return RunResult(
            command=command,
            exit_code=1,
            stdout="",
            stderr=str(e),
            timed_out=False,
        )
