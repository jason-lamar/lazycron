# launchd Management Specification (delta)

This delta introduces a new capability. All requirements are `ADDED`.

Status on merge of this change: `planned` → `implemented` per the tasks checklist.
Until implemented, this spec is the contract, not a record of current behavior.

## ADDED Requirements

### Requirement: Discover per-user launchd jobs

The system SHALL discover launchd jobs by reading `.plist` files from
`~/Library/LaunchAgents` (controllable) and `/Library/LaunchAgents` (read-only,
marked as system). The system SHALL NOT read or control `/Library/LaunchDaemons`.

#### Scenario: User agents are listed
- **WHEN** the user opens LazyCron on macOS with plists present in `~/Library/LaunchAgents`
- **THEN** each valid plist appears as a job tagged `source = launchd`
- **AND** jobs from `/Library/LaunchAgents` are listed and marked read-only/system

#### Scenario: launchd is hidden off-macOS
- **WHEN** LazyCron runs on a non-macOS platform
- **THEN** no launchd source is presented and the cron experience is unchanged

### Requirement: Parse plist command and schedule faithfully

The system SHALL parse each plist with `plistlib`, supporting XML and binary
formats, and SHALL extract the command from `ProgramArguments` (list) or
`Program` (string), and the schedule from `StartInterval` or
`StartCalendarInterval`. `StartCalendarInterval` MAY be a dict or an array of
dicts; the system SHALL represent all entries and SHALL NOT collapse an array to
its first element. The system SHALL retain unrecognized plist keys.

#### Scenario: Array calendar interval
- **WHEN** a plist defines `StartCalendarInterval` as an array of N time entries
- **THEN** the rendered schedule reflects all N fire times, not just the first

#### Scenario: Event-driven job with no time schedule
- **WHEN** a plist has neither `StartInterval` nor `StartCalendarInterval`
- **THEN** the job is listed with a `triggered (no time schedule)` description
- **AND** remains selectable and controllable

#### Scenario: Missing Label
- **WHEN** a `.plist` file lacks a `Label` key
- **THEN** it is skipped without aborting discovery of other jobs

### Requirement: Control lifecycle with modern launchctl verbs

The system SHALL enable, disable, and run launchd jobs using domain-targeted
`launchctl` verbs against `gui/<uid>` (uid from the current process). The system
SHALL NOT use the deprecated `load`/`unload` verbs.

#### Scenario: Disable persists without editing the plist
- **WHEN** the user disables a launchd job
- **THEN** the system runs `launchctl disable gui/<uid>/<label>` and `bootout`
- **AND** the on-disk plist file is not modified
- **AND** the job remains disabled across reboot

#### Scenario: Enable
- **WHEN** the user enables a previously disabled launchd job
- **THEN** the system runs `launchctl enable gui/<uid>/<label>` and `bootstrap <plist>`
- **AND** an already-loaded job is reconciled to enabled without error

#### Scenario: Run now
- **WHEN** the user triggers Run Now on a launchd job
- **THEN** the system runs `launchctl kickstart -k gui/<uid>/<label>`

### Requirement: Non-destructive to plist files

In this capability the system SHALL NOT create, rewrite, or delete any launchd
plist file. All control operations act on the launchd override database and the
running domain only.

#### Scenario: Lifecycle leaves files untouched
- **WHEN** any enable/disable/run-now operation completes
- **THEN** the modification time and contents of the target `.plist` are unchanged

### Requirement: Report launchd execution status natively

The system SHALL report a launchd job's last run and exit status from
`launchctl print gui/<uid>/<label>`, falling back to the job's configured
`StandardOutPath`/`StandardErrorPath`. The system SHALL NOT wrap launchd
`ProgramArguments` with the cron `run.sh` logging wrapper.

#### Scenario: Last exit shown
- **WHEN** a launchd job has previously run
- **THEN** its last exit code and run time are shown in the detail/heatmap view

### Requirement: Surface source and editing scope in the UI

The system SHALL display a source badge distinguishing launchd jobs from cron
jobs, SHALL allow filtering by source, and SHALL indicate that launchd jobs are
read-only for schedule/command editing in this increment while remaining
controllable (enable/disable/run-now).

#### Scenario: Edit is gated for launchd
- **WHEN** the user presses the edit key on a launchd job
- **THEN** the system indicates editing is not yet supported for launchd
- **AND** enable/disable and run-now remain available

## Non-Requirements (this change)

- Creating or editing launchd plist files (schedule/command) — deferred to
  `add-launchd-editing`.
- Any operation requiring root/sudo, including `/Library/LaunchDaemons`.
- Translating cron expressions into launchd schedules or vice versa.
