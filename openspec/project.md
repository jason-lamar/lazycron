# LazyCron OpenSpec

## Purpose

This OpenSpec tree records current implementation truth for LazyCron before additional feature work. It is documentation-only and must not be treated as a runtime behavior change.

## Truth Sources

Current-state specs may only claim behavior verified in one of these sources:

- `lazycron/*.py`
- `lazycron/ui/*.py`
- `tests/*.py`
- `Makefile`
- `README.md`
- `pyproject.toml`
- local verification commands listed below

`PROVENANCE_FIX_PLAN.md` is planning context, not implementation truth. `README.md` is a design reference where it describes features — verify behavior against code.

## Status Vocabulary

- `implemented`: code, schema, tests, or commands show the behavior exists today.
- `partial`: some behavior exists, but the README or planning docs describe a broader capability than current code supports.
- `stubbed`: the code has a named placeholder/interface, but the behavior is not substantively implemented.
- `planned`: described in docs or specs, but not implemented today.
- `not implemented`: neither current code nor tests provide the behavior.

## Architecture Guardrails

- Treat Python stdlib + curses as the complete dependency surface. Do not describe external packages as available.
- Treat `crontab -l` / `crontab -` as the sole persistence mechanism for job state. Do not describe a database or config file for job data.
- Treat `~/.lazycron/history.jsonl` as the execution history store.
- Treat `lazycron.app:main` as the entry point invoked through both `lazycron` CLI and `python -m lazycron`.
- Do not describe `logs.py` as an active system — it is a stubbed/unused module with no current callers.
- Runtime truth must be proven from code, tests, Makefile, or commands.

## Verification Commands

Run from `applications/Lazy-cron`:

```bash
make unittest
python3 -m unittest discover -s tests -v
python3 -m lazycron --help
make lint
```

Observed on 2026-05-30 during this OpenSpec creation:

- `python3 -m unittest discover -s tests -v` ran 86 tests and passed.
- `make unittest` ran the same test suite and passed.
- `make lint` requires `ruff` to be installed separately.

## Current-State Summary

- LazyCron is a pure-Python stdlib + curses TUI for managing cron jobs.
- The entry point is `lazycron.app:main` (exposed as both `lazycron` CLI and `python -m lazycron`).
- Three-panel layout: jobs list (left), job details (center), activity log (bottom).
- Crontab is loaded from the system via `crontab -l` and saved via `crontab -` with round-trip fidelity for unmodified lines.
- Cron expressions are parsed, validated, translated to human-readable descriptions, and used to compute next-run times.
- Jobs support enable/disable, create, edit, delete (two-press confirm), and Run Now execution.
- The execution wrapper (`~/.lazycron/run.sh`) transparently logs cron job execution to `~/.lazycron/history.jsonl` for both cron-initiated and TUI-initiated runs.
- Undo/redo is supported (up to 50 levels) for all job mutations.
- Search/filter uses case-insensitive substring matching on job name, command, and schedule.
- Visual cron builder and integrated 5-field schedule form with preset picklist and live validation.
- Splash screen on startup, help modal, dirty-quit confirmation, and Run Now output modal with macOS provenance hints.
- `logs.py` exists as a stubbed module — it reads system cron logs but is not imported or used anywhere in the app.
- The `_do_save()` method deep-copies the crontab before wrapping commands, so a failed write does not corrupt in-memory state.
- `get_last_run()` uses a 2-second TTL cache to avoid re-reading `history.jsonl` on every frame.

## Roadmap Mismatch Summary

- `logs.py` (system cron log reader) is stubbed: the module exists with macOS and Linux implementations, but is never imported in the running app. Execution history is handled entirely through `wrapper.py` + `state.py`.
- `PROVENANCE_FIX_PLAN.md` describes a broader provenance remediation plan than what wrapper.py currently implements (the wrapper already uses `cat | /bin/sh` to bypass provenance checks).
