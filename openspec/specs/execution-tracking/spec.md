# Execution Tracking Specification

## Status

Current state: `implemented` for command wrapping, Run Now execution, and history persistence. `stubbed` for platform-specific cron log reading (`logs.py` is present but unused).

## Requirements

### Requirement: All cron-initiated runs are logged

When LazyCron saves the crontab, enabled jobs SHALL be auto-wrapped with a shell wrapper that logs execution results to `~/.lazycron/history.jsonl`.

Evidence:
- `lazycron/wrapper.py:23-44` — `_WRAPPER_SCRIPT` is a shell script that: sources `~/.lazycron/env.sh`, executes the command via `bash -c "set -o pipefail; $CMD"`, captures exit code, and appends a JSON line to the history file.
- `lazycron/wrapper.py:47-53` — `ensure_wrapper()` writes the script to `~/.lazycron/run.sh` and makes it executable.
- `lazycron/wrapper.py:55-68` — `wrap_command()` wraps a command as `cat run.sh | /bin/sh -s 'name' 'cmd'`, using `shlex.quote()` for shell safety.
- `lazycron/state.py:209-225` — `_do_save()` wraps all enabled commands before writing to the system crontab.

### Requirement: The wrapper is transparent to the user

The UI SHALL display the original (unwrapped) command, hiding the wrapping layer.

Evidence:
- `lazycron/wrapper.py:71-93` — `unwrap_command()` extracts the original command from a wrapped command by shell-parsing the arguments after `-s`.
- `lazycron/wrapper.py:97-100` — `display_command()` returns the unwrapped command for display.
- `lazycron/crontab.py:50-53` — `Job.display_cmd` calls `display_command()`.
- `lazycron/state.py:213` — Wrapping only happens during save, not in the in-memory display state.

### Requirement: Run Now executes a job with timeout and output capture

The system SHALL execute a job's command immediately via `Shift+R`, capturing stdout/stderr with a 10-minute timeout.

Evidence:
- `lazycron/executor.py:38-90` — `run_command()` executes via `["/bin/sh", "-c", command]` with merged crontab env vars, `DEFAULT_TIMEOUT = 600` seconds, handling `TimeoutExpired`, `FileNotFoundError`, and `OSError`.
- `lazycron/executor.py:16-35` — `RunResult` dataclass captures command, exit code, stdout, stderr, and timeout flag.
- `lazycron/app.py:218-250` — `_handle_run_now()` calls `run_command()`, logs the result, and shows `show_run_output_modal()`.

### Requirement: Last-run status is visible per job

Each job SHALL display its most recent execution result (`✓`/`✗`) in the jobs list and timing in the detail panel.

Evidence:
- `lazycron/wrapper.py:102-128` — `get_last_run()` reads `history.jsonl` to find the most recent entry matching a job name, with a 2-second TTL cache.
- `lazycron/ui/panels.py:63-69` — `draw_jobs_panel()` calls `get_last_run()` and appends `✓` or `✗` indicator per job.
- `lazycron/ui/panels.py:282-296` — `draw_detail_panel()` shows last run timestamp and success/failure in the detail panel.

### Requirement: Environment variables persist across wrapper regenerations

The system SHALL support a user-editable `~/.lazycron/env.sh` file that is sourced by the wrapper before each job runs.

Evidence:
- `lazycron/wrapper.py:31` — `[ -f "$HOME/.lazycron/env.sh" ] && . "$HOME/.lazycron/env.sh"` in the wrapper script.
- `README.md:127-136` — Documents the env.sh mechanism.

### Requirement: macOS provenance bypass for sandboxed scripts [implemented]

The wrapper SHALL use `cat | /bin/sh` piping to bypass macOS file provenance attributes that cause exit code 126.

Evidence:
- `lazycron/wrapper.py:62` — `wrap_command()` uses `cat {WRAPPER_PATH} | /bin/sh -s` pattern instead of executing the wrapper directly.
- `README.md:141-169` — Documents the macOS provenance issue and the bypass mechanism.

## Non-Requirements

- `logs.py` (platform cron log reader for macOS/Linux system logs) is stubbed but unused. Execution history uses `wrapper.py` + `state.py` instead.
- The system does not provide a web UI, notification service, or email alerts for job failures.
- The Run Now feature has a hard 10-minute timeout and does not support background/async execution for long-running jobs beyond that.
