# Design: launchd backend

## Context

LazyCron is cron-coupled today: `crontab.py` owns the `Job`/`CrontabFile` model,
`state.py:Store` loads/saves via `crontab -l`/`crontab -`, and the UI renders one
list. Adding launchd cleanly means introducing a thin **source** seam without
disturbing the cron path or the stdlib+curses guardrail.

This document records the decisions that make the launchd backend correct on
modern macOS — each one is a direct contrast with the prior-art tool's mistakes.

## Decision 1 — Source abstraction, not a parallel app

Introduce a minimal `JobSource` protocol:

```
class JobSource(Protocol):
    name: str                       # "cron" | "launchd"
    def available(self) -> bool     # platform / tooling gate
    def list(self) -> list[Job]
    def set_enabled(self, job, enabled) -> str | None   # returns error or None
    def run_now(self, job) -> RunResult
    def last_run(self, job) -> LogEntry | None
```

`CronSource` wraps today's behavior (no functional change). `LaunchdSource` is
new. `Store` holds an ordered list of available sources and aggregates
`list()` into the existing single job list, tagging each `Job` with `.source`.

Rationale: keeps one TUI, one mental model, minimal new surface. A second "mode"
would duplicate navigation, filtering, and detail rendering for no user benefit.

## Decision 2 — Read scope: per-user agents only

`LaunchdSource.list()` scans, in order:

1. `~/Library/LaunchAgents` — read **and** lifecycle-controllable (no sudo).
2. `/Library/LaunchAgents` — read-only, marked `system` (no sudo to read).

`/Library/LaunchDaemons` is **excluded** — reading is fine but any control needs
root, and mixing controllable and uncontrollable rows invites the exact
confusion we want to avoid. Out of scope until a sudo story exists.

## Decision 3 — Parse with `plistlib` (stdlib), tolerate both plist formats

`plistlib.load(fp)` handles XML and binary plists natively. Extract:

- `Label` (required; skip files without it).
- Command: `ProgramArguments` (list → keep as list, render shell-quoted) or
  `Program` (string). **Do not** lossily space-join args internally; preserve the
  list so a future editor round-trips correctly.
- Schedule: `StartInterval` (seconds) **or** `StartCalendarInterval`, which may be
  a **dict or an array of dicts** — handle the array (a job can have many fire
  times; e.g. an `every 5 minutes` job is 12 entries). Render a faithful
  human-readable summary; never collapse an array to its first element.
- `Disabled` key (informational) and `RunAtLoad`.

Unknown keys are **retained in the parsed `Job.raw`** so nothing is lost if/when
editing lands.

## Decision 4 — Lifecycle via modern verbs, against the override DB

macOS `launchctl load`/`unload` are deprecated and unreliable in the per-user
GUI domain. Use the domain-target form with `gui/<uid>` (uid from `os.getuid()`):

| Action | Command | Touches plist file? |
|---|---|---|
| Disable | `launchctl disable gui/<uid>/<label>` then `launchctl bootout gui/<uid>/<label>` | **No** (override DB + in-memory) |
| Enable | `launchctl enable gui/<uid>/<label>` then `launchctl bootstrap gui/<uid> <plist-path>` | **No** |
| Run now | `launchctl kickstart -k gui/<uid>/<label>` | **No** |

`disable`/`enable` write to launchd's override database, so the disabled state
**persists across reboot without editing the plist** — strictly better than
flipping the plist's `Disabled` key, and non-destructive. `bootout`/`bootstrap`
apply the change to the running domain immediately. Treat a missing-label
`bootout` (job not loaded) as success, not error.

## Decision 5 — Native execution tracking, no wrapper

The cron `run.sh` wrapper exists to capture exit codes cron doesn't record and to
dodge the macOS provenance/exit-126 trap. launchd already records last exit and
PID (`launchctl print gui/<uid>/<label>` → `last exit code`, `pid`) and supports
`StandardOutPath`/`StandardErrorPath`. So:

- `LaunchdSource.last_run()` parses `launchctl print` for last exit code + state,
  and falls back to the job's `StandardErrorPath`/`StandardOutPath` mtime/tail.
- **Do not** wrap launchd `ProgramArguments` with `run.sh`. The provenance
  failure mode is a cron-execution artifact; launchd exec is direct.

This keeps the heatmap/last-run column populated for launchd jobs through native
signals rather than an injected wrapper.

## Decision 6 — UI: badge + filter, detail panel read-only for launchd

- Job list rows gain a short source badge (e.g. `[launchd]` / `[cron]`) — minimal,
  themable in `ui/theme.py`.
- A filter key cycles `all → cron → launchd`, reusing the existing filter plumbing.
- The detail panel shows launchd schedule as the human-readable description and
  marks the job `read-only (launchd editing not yet supported)` so users aren't
  surprised when `e` is inert for launchd rows in this increment.
- `s` (save) remains cron-only; launchd lifecycle is immediate (no dirty/save
  cycle), consistent with how `launchctl` applies changes.

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| `launchctl print` output format varies across macOS versions | Parse defensively (regex for `last exit code`/`state`); degrade to "unknown" not crash |
| A user's agent lacks any schedule (event/WatchPaths-driven) | Render `triggered (no time schedule)`; still listable and controllable |
| `bootstrap` fails if already loaded | Treat "already bootstrapped" as success; reconcile to desired state |
| Binary plists | `plistlib` handles natively — covered by a testdata fixture |

## Test strategy

- Unit: `tests/test_launchd.py` against plist **fixtures** (XML + binary, single &
  array `StartCalendarInterval`, `StartInterval`, `Program` vs `ProgramArguments`,
  missing `Label`) — pure parse/format, no system calls.
- Lifecycle command construction tested by injecting a fake runner (assert the
  exact `launchctl` argv, including `gui/<uid>/<label>`), not by invoking launchctl.
- Integration (guarded, opt-in): a temp agent in `~/Library/LaunchAgents` to
  exercise real enable/disable/kickstart, mirroring the existing integration-tag
  pattern. Never run in the default suite.
