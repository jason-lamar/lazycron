# Cron Expression Engine Specification

## Status

Current state: `implemented` for 5-field cron parsing, validation, human-readable description, and next-run computation. All features are tested (207 lines of tests in `test_cron.py`).

## Requirements

### Requirement: Parse 5-field cron expressions

The engine SHALL parse standard 5-field cron expressions (minute, hour, day-of-month, month, day-of-week) into a structured `CronExpression` dataclass.

Evidence:
- `lazycron/cron.py:470-483` — `parse_expression()` splits raw string into 5 fields, pads missing fields with `*`.
- `lazycron/cron.py:129-186` — `_parse_field()` handles wildcards, single values, ranges, steps, and lists.
- `lazycron/cron.py:189-199` — `parse_field()` normalizes 3-letter day/month names (mon-fri, jan-dec) before parsing.
- `tests/test_cron.py:78-105` — `TestCronExpression` tests for parsing, partial expressions, and raw preservation.

### Requirement: Validate cron field values

The engine SHALL validate each field against its allowed range and return specific error messages for invalid values.

Evidence:
- `lazycron/cron.py:18-24` — `FIELD_RANGES` defines valid ranges for each field (minute 0-59, hour 0-23, dom 1-31, month 1-12, dow 0-7).
- `lazycron/cron.py:250-255` — `CronExpression.validate()` returns `(bool, error_message)`.
- `tests/test_cron.py:62-72` — Tests for out-of-range, invalid token, and invalid range errors.

### Requirement: Generate human-readable schedule descriptions

The engine SHALL translate a cron expression into an English sentence (e.g., "Every 15 minutes, Monday through Friday").

Evidence:
- `lazycron/cron.py:257-289` — `CronExpression.describe()` assembles a description from field-level clauses.
- `lazycron/cron.py:395-465` — Per-field description helpers (`_describe_minute`, `_describe_hour`, etc.) handle wildcards, intervals, ranges, sets, and named day/month labels.
- `tests/test_cron.py:108-143` — `TestHumanReadable` tests for every minute, weekdays, weekends, hourly, monthly, specific months.

### Requirement: Compute next execution time

The engine SHALL compute the next execution time after a given datetime, respecting standard cron OR behavior for DOM/DOW interaction.

Evidence:
- `lazycron/cron.py:291-345` — `CronExpression.next_run()` walks forward minute-by-minute through valid months, days, hours, and minutes.
- `lazycron/cron.py:316-329` — DOM/DOW interaction uses standard cron OR semantics: if both are restricted, either can match.
- `lazycron/cron.py:347-357` — `CronExpression.next_n()` computes multiple future runs.
- `lazycron/cron.py:362-390` — Helper functions `_next_month`, `_next_hour`, `_next_minute` for advancing through valid values.
- `tests/test_cron.py:146-189` — `TestNextRun` tests for every minute, specific time, next day, weekday skip, and next_n.

## Non-Requirements

- The engine does not support 6-field cron expressions (seconds field).
- The engine does not support non-standard macros like `@yearly`, `@reboot`.
- The engine does not persist parsed expressions — it re-parses from the raw string each time. This is intentional for simplicity given zero deps.
