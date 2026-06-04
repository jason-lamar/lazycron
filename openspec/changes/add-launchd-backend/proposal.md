# Change: Add launchd backend (macOS)

## Status

`proposed` — awaiting approval. No implementation has begun.

## Why

LazyCron manages cron jobs. On macOS, the system-native scheduler is **launchd**,
not cron — Apple has recommended launchd over cron for years, and most real
recurring work on a Mac (user agents in `~/Library/LaunchAgents`, Homebrew
services, app updaters, and the user's own daemons) runs under launchd. Today a
LazyCron user on macOS sees only their crontab and is blind to the jobs that
actually matter.

The only comparable TUI prior art (`mc7h/lazycron`, a single-commit MVP) does
include launchd, but its write path is **destructive**: editing a job
regenerates the plist from three keys and drops everything else
(`EnvironmentVariables`, `StandardOutPath`, `RunAtLoad`, `KeepAlive`, …), it
hardcodes every calendar schedule to midnight, and it uses the deprecated
`launchctl load`/`unload` verbs. Doing launchd **correctly** — non-destructive,
modern verbs, faithful schedule handling — is the differentiator and the reason
to build rather than adopt.

## What Changes

This change adds a **read + lifecycle** launchd backend, scoped to the
per-user domain. It deliberately does **not** add plist file editing in this
increment (that is a separate, higher-risk change — see Out of Scope).

- **New capability `launchd-management`**: discover, parse, and display launchd
  jobs from `~/Library/LaunchAgents` (and read-only from `/Library/LaunchAgents`).
- **Lifecycle control** via modern `launchctl` verbs: enable/disable
  (`enable`/`disable` against the override DB — persists across reboot without
  touching the plist file), and Run Now (`kickstart -k gui/<uid>/<label>`).
- **Native execution tracking**: last run / exit status read from
  `launchctl print` and the job's own `StandardOutPath`/`StandardErrorPath`.
  The cron `~/.lazycron/run.sh` wrapper is **not** applied to launchd jobs.
- **Source-aware UI**: launchd jobs appear in the existing three-panel job list
  with a source badge; a filter key narrows to cron-only or launchd-only.
- **Platform detection**: the launchd source is surfaced only on macOS; the
  cron experience is unchanged on every platform.

### Non-destructive guarantee (the core design commitment)

In this increment LazyCron **never rewrites a launchd plist file**. Enable/
disable and Run Now go through `launchctl` against the override DB and the
in-memory domain — the user's plist on disk is read-only to LazyCron. This makes
the launchd backend safe to ship before the editor exists, and it is the
explicit anti-pattern fix versus the prior-art tool.

## Out of Scope (explicit — follow-up changes)

- **Plist editing (create/edit schedule & command).** Requires a
  preserve-and-merge writer (load existing dict → mutate only changed keys →
  write back, never drop unknown keys) and a launchd-native schedule editor
  (the cron 5-field form cannot represent `StartCalendarInterval`). Tracked as a
  separate change `add-launchd-editing`.
- **System domain** (`/Library/LaunchDaemons`, `/Library/LaunchAgents` writes)
  — needs root/sudo + TTY, which the current no-sudo design excludes.
- **Adoption-readiness work** (LICENSE present already; CONTRIBUTING, CI,
  versioned releases, Homebrew tap) — tracked separately as
  `adoption-readiness` so this change stays focused on launchd.

## Impact

- **Affected specs**: new `launchd-management`; deltas to `tui-layout-and-panels`
  (source badge + filter) and `execution-tracking` (launchd history source).
- **Affected code**: new `lazycron/launchd.py`; a small source abstraction so
  `state.py` aggregates jobs from both cron and launchd; `ui/panels.py` and
  `ui/statusbar.py` for the source badge/filter; `app.py` key handling.
- **Dependencies**: none added — `plistlib`, `subprocess`, `os` are stdlib.
- **Risk**: low. No plist writes; lifecycle is reversible; cron path untouched;
  launchd source hidden off-macOS.
- **Backward compatibility**: fully preserved. On Linux and for cron-only users,
  behavior is identical to today.
