# TUI Layout and Panel Rendering Specification

## Status

Current state: `implemented` for 3-panel layout geometry, jobs list panel, job detail panel (with cron table), activity log panel, status bar, splash screen, and theme system.

## Requirements

### Requirement: Three-panel layout with adjustable proportions

The application SHALL render a 3-panel layout: jobs list (left, 26-char fixed width), job details (center, fills remaining), and activity log (bottom, 1/3 height). A status bar occupies the bottom 3 rows.

Evidence:
- `lazycron/ui/layout.py:30-75` — `PanelGeometry` computes panel sizes: top row = 2/3 usable height, bottom row = 1/3, jobs panel = `MIN_W` (26) or 1/3 max width, detail panel fills remainder.
- `lazycron/ui/layout.py:85-151` — `draw_borders()` renders Unicode box-drawing borders (`┌─┬─┐`, `├─┼─┤`, `└─┴─┘`) with panel titles.

### Requirement: Jobs list panel supports scrolling and selection

The jobs list SHALL display all jobs with active/inactive indicators, last-run status, scroll offset for long lists, and position indicator.

Evidence:
- `lazycron/ui/panels.py:27-94` — `draw_jobs_panel()` iterates visible jobs, computes scroll offset, draws `●`/`○` status indicators, `✓`/`✗` run indicators, highlights selected job with inverted colors, and shows `N/M` position at bottom.

### Requirement: Job detail panel shows cron table, status, timing, command, and collision warnings

The detail panel SHALL display a visual cron field table (MIN/HOUR/DOM/MON/DOW with raw and human-readable rows), job status (Active/Disabled), next run time (with relative offset), last run history, name/command, and collision warnings.

Evidence:
- `lazycron/ui/panels.py:134-208` — `_draw_cron_table()` draws a box-drawing table with headers, raw values, and human-friendly values per field.
- `lazycron/ui/panels.py:216-336` — `draw_detail_panel()` renders: schedule description, cron table, status line, next run with relative time, last run with result, name and command (with multi-line wrapping for long commands), and collision warnings.
- `lazycron/ui/panels.py:97-131` — `_friendly_value()` translates raw cron values to labels (":00", "Monday", "15th", etc.).
- `lazycron/ui/panels.py:339-360` — `_detect_collisions()` compares next 24 runs of selected job against all other enabled jobs to find overlaps.

### Requirement: Activity log panel shows most recent entries

The bottom panel SHALL display the most recent action log entries with timestamp, success/failure indicator, and message.

Evidence:
- `lazycron/ui/panels.py:363-394` — `draw_log_panel()` renders entries from `store.action_log`, showing the last `avail_h` entries with `✓`/`✗`/`·` indicators and color-coded success (green), failure (red), or info (dim).

### Requirement: Status bar shows dirty indicator, transient messages, and key hints

The status bar SHALL display a dirty indicator for unsaved changes, transient status messages (3-second TTL), delete confirmation prompts, and a full row of keybinding hints.

Evidence:
- `lazycron/ui/statusbar.py:16-45` — `draw_statusbar()` renders: dirty `◆ unsaved changes`, transient messages (disappear after `MSG_DURATION = 3.0s`), delete-pending prompt, and key hints row.

### Requirement: Splash screen on startup

The app SHALL display an ASCII logo splash screen on startup for 3 seconds before entering the main loop.

Evidence:
- `lazycron/ui/splash.py:11-23` — `LOGO` defines the lazycron ASCII art, `TAGLINE`, `HINT`, `SPLASH_DURATION = 3.0`.
- `lazycron/ui/splash.py:26-71` — `show_splash()` renders centered logo, tagline, hint, sleeps via `napms`, drains any keys pressed during splash, and erases.

### Requirement: Theme constants are centralized

All color pairs, border characters, indicators, and layout constants SHALL be defined in a single theme module.

Evidence:
- `lazycron/ui/theme.py:1-82` — Centralizes: 16 color pairs (`C_GREEN` through `C_ERROR`), Unicode box-drawing characters (`BOX_TL` through `BOX_X`), status indicators (`●`, `○`, `✓`, `✗`), and layout constants (`JOBS_W=26`, `MIN_W=80`, `MIN_H=20`, `STATUS_H=3`).
- `lazycron/ui/theme.py:30-50` — `init_colors()` initializes all pairs with `curses.init_pair()`.

## Non-Requirements

- The UI does not support mouse input — everything is keyboard-driven.
- There is no configuration file for customizing colors, keybindings, or layout.
- The splash screen is a fixed 3-second display and cannot be skipped or disabled.
