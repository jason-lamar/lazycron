# Tasks: Add launchd backend

Ordered for incremental, always-green delivery. Each top group should land as its
own commit. Nothing here writes a plist file.

## 1. Source abstraction (no behavior change)
- [ ] 1.1 Add `JobSource` protocol (`list/set_enabled/run_now/last_run/available`) in `lazycron/sources.py`
- [ ] 1.2 Add `Job.source` field (default `"cron"`); thread through `crontab.py` model
- [ ] 1.3 Wrap existing cron behavior as `CronSource` (pure refactor; all 86 tests stay green)
- [ ] 1.4 `Store` holds an ordered `sources` list and aggregates `list()`; cron-only path unchanged

## 2. launchd read (`lazycron/launchd.py`)
- [ ] 2.1 Discover plists in `~/Library/LaunchAgents` (controllable) + `/Library/LaunchAgents` (read-only/system)
- [ ] 2.2 Parse via `plistlib`: `Label`, `ProgramArguments`/`Program`, `Disabled`, `RunAtLoad`; retain unknown keys in `Job.raw`
- [ ] 2.3 Schedule parse: `StartInterval`; `StartCalendarInterval` as **dict and array**; render faithful human description; handle no-time-schedule (event-driven) jobs
- [ ] 2.4 `available()` returns True only on macOS (`sys.platform == "darwin"`)
- [ ] 2.5 Unit tests `tests/test_launchd.py` against XML + binary fixtures (all parse cases above)

## 3. launchd lifecycle (modern verbs, no plist writes)
- [ ] 3.1 Resolve `gui/<uid>` from `os.getuid()`; central `_target(label)` helper
- [ ] 3.2 `set_enabled(False)`: `launchctl disable` + `bootout`; treat not-loaded as success
- [ ] 3.3 `set_enabled(True)`: `launchctl enable` + `bootstrap <plist>`; treat already-loaded as success
- [ ] 3.4 `run_now()`: `launchctl kickstart -k gui/<uid>/<label>`
- [ ] 3.5 Inject the command runner; unit-test exact `launchctl` argv (no real launchctl in default suite)

## 4. launchd execution tracking (native)
- [ ] 4.1 `last_run()`: parse `launchctl print gui/<uid>/<label>` for `last exit code` + state
- [ ] 4.2 Fallback to `StandardErrorPath`/`StandardOutPath` mtime/tail when print is unavailable
- [ ] 4.3 Confirm `run.sh` wrapper is **never** applied to launchd jobs
- [ ] 4.4 execution-tracking spec delta reflects the launchd history source

## 5. UI integration
- [ ] 5.1 Source badge in job-list rows (`ui/panels.py`, themed in `ui/theme.py`)
- [ ] 5.2 Filter key cycles `all → cron → launchd` (reuse existing filter plumbing)
- [ ] 5.3 Detail panel: render launchd schedule description; mark launchd rows `read-only (editing not yet supported)`
- [ ] 5.4 Gate `e` (edit) and `s` (save) to cron rows; launchd lifecycle (`space`, `r`) is immediate
- [ ] 5.5 tui-layout-and-panels spec delta for badge + filter

## 6. Docs & verification
- [ ] 6.1 README: macOS launchd section (what's supported, per-user scope, read+lifecycle, editing deferred)
- [ ] 6.2 `make unittest` green incl. new launchd tests; `python3 -m lazycron` lists real launchd jobs on this Mac
- [ ] 6.3 Manual check against the owner's real agents (e.g. `com.guardiansage.*`): list, disable/enable round-trip, run-now, last-exit display — **no plist file mtime change** from lifecycle ops
- [ ] 6.4 Update `openspec/project.md` Current-State Summary after merge (per repo convention)

## Definition of done
- New `launchd-management` capability behaves per its spec on macOS.
- Cron behavior byte-for-byte unchanged; Linux unaffected (launchd source hidden).
- No code path writes a launchd plist file.
- All unit tests green with no new runtime dependencies.
