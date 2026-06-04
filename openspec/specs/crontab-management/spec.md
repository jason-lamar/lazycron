# Crontab Management Specification

## Status

Current state: `implemented` for system crontab I/O, round-trip fidelity, job CRUD, and env var parsing. All features are tested in `test_crontab.py` (40+ tests).

## Requirements

### Requirement: Load crontab from system

The system SHALL load the current user's crontab via `crontab -l` and parse it into a `CrontabFile` struct.

Evidence:
- `lazycron/crontab.py:265-286` — `load_system_crontab()` runs `crontab -l`, returns `CrontabFile` or error.
- `lazycron/crontab.py:152-234` — `parse()` handles blank lines, comments, disabled jobs (`#`-prefixed cron lines), enabled jobs, and env var assignments (`KEY=value`).
- `lazycron/crontab.py:113-149` — `_is_cron_field()` heuristically distinguishes cron fields from shell variables.
- `tests/test_crontab.py` — Tests for empty crontab, minimal entries, disabled jobs, env vars, sample crontab.

### Requirement: Save crontab with round-trip fidelity

The system SHALL serialize the crontab back to text, preserving original formatting for unmodified lines, and write via `crontab -`.

Evidence:
- `lazycron/crontab.py:75-108` — `CrontabFile.serialize()` rebuilds text: unmodified lines use verbatim originals, deleted lines are omitted, modified lines use new text, appended lines are added at the end.
- `lazycron/crontab.py:289-309` — `save_system_crontab()` pipes serialized text to `crontab -`.
- `tests/test_crontab.py` — `TestRoundTrip` verifies parse-serialize-parse round trips preserve structure.

### Requirement: Support job CRUD operations

The system SHALL support toggle (enable/disable), update (schedule/command/comment), delete, and add operations on jobs within the crontab.

Evidence:
- `lazycron/crontab.py:314-326` — `toggle_job()` prepends/removes `# ` prefix, marks line modified.
- `lazycron/crontab.py:329-340` — `update_job()` replaces schedule, command, and comment, reconstructs the line.
- `lazycron/crontab.py:343-346` — `delete_job()` marks line deleted and removes job from list.
- `lazycron/crontab.py:349-365` — `add_job()` appends a new line, creates and returns a `Job` object.
- `tests/test_crontab.py` — `TestToggle`, `TestUpdate`, `TestDelete`, `TestAdd` test each operation.

### Requirement: Crontab supports inline comments as job names

The system SHALL extract inline comments (text after `#` in the command portion) and use them as the display name for jobs.

Evidence:
- `lazycron/crontab.py:30-47` — `Job.display_name` returns the comment if set, otherwise derives a name from the command.
- `lazycron/crontab.py:237-260` — `_split_command_comment()` splits at `#` outside quotes, respecting single/double quotes and backslash escaping.

### Requirement: Track dirty state via modification markers

The system SHALL track which lines are modified, deleted, or appended, enabling `has_modifications()` dirty detection.

Evidence:
- `lazycron/crontab.py:71-73` — `_modified_lines`, `_deleted_lines`, `_appended_lines` tracked separately.
- `lazycron/crontab.py:106-108` — `has_modifications()` returns `True` if any are non-empty.

## Non-Requirements

- The crontab does not support multi-line commands or `&&` chaining beyond what cron itself accepts.
- The system does not read or write alternate crontab files (e.g., `/etc/crontab`, per-user `cron.d`).
- The system does not validate that commands exist or are executable — it defers to cron's runtime behavior.
