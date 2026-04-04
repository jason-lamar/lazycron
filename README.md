```
 ██╗      █████╗ ███████╗██╗   ██╗ ██████╗██████╗  ██████╗ ███╗   ██╗
 ██║     ██╔══██╗╚══███╔╝╚██╗ ██╔╝██╔════╝██╔══██╗██╔═══██╗████╗  ██║
 ██║     ███████║  ███╔╝  ╚████╔╝ ██║     ██████╔╝██║   ██║██╔██╗ ██║
 ██║     ██╔══██║ ███╔╝    ╚██╔╝  ██║     ██╔══██╗██║   ██║██║╚██╗██║
 ███████╗██║  ██║███████╗   ██║   ╚██████╗██║  ██║╚██████╔╝██║ ╚████║
 ╚══════╝╚═╝  ╚═╝╚══════╝  ╚═╝    ╚═════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝
```

A LazyGit-style TUI for managing cron jobs. Navigate, edit, create, and monitor cron jobs from a beautiful terminal interface.

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
![Zero Dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen)

## Features

- **3-panel layout** — jobs list with run status, job details, and unified activity log
- **Execution tracking** — auto-wraps cron commands to log every run (success/failure, exit code, timestamp) — works for both cron-initiated and manual runs
- **Last run status** — each job shows its most recent result (`✓`/`✗`) in the jobs list and detail panel
- **Human-readable schedules** — translates `*/15 9-17 * * 1-5` into plain English
- **Visual cron builder** — odometer-style field selector prevents syntax errors
- **Full crontab management** — create, edit, toggle, delete, and save jobs
- **Undo/redo** — every action is reversible (up to 50 levels)
- **Run Now** — test any job immediately with `Shift+R`, with output capture
- **Collision detection** — warns when jobs overlap
- **Search/filter** — fuzzy-find jobs by name or command
- **Persistent activity log** — survives restarts, stored in `~/.lazycron/history.jsonl`
- **Zero external dependencies** — pure Python stdlib + curses

## Layout

```
┌─ Jobs ──────────────┬─ Job Details ──────────────────────────┐
│ ● health-check   ✓  │ ┌─────┬───────┬───────┬───────┬──────┐ │
│ ● nightly-backup ✓  │ │ MIN │ HOUR  │  DOM  │  MON  │ DOW  │ │
│ ○ weekly-report  ✗  │ ├─────┼───────┼───────┼───────┼──────┤ │
│ ● api-ping       ✓  │ │ */15│ 9-17  │   *   │   *   │  1-5 │ │
│                     │ │ :15 │ 09:00 │ Every │ Every │  Fri │ │
│                     │ └─────┴───────┴───────┴───────┴──────┘ │
│                     │ Every 15 min, 09:00–17:59, Mon–Fri     │
│                     │                                        │
│                     │ Command:   /scripts/health-check.sh    │
│                     │ Next Run:  Mon 09:15 (in 12 min)       │
│                     │ Last Run:  Mon Mar 20 09:00 — success  │
│                     │ Status:    Active                      │
├─ Log ────────────────────────────────────────────────────────┤
│ 09:00:02  ✓  health-check — success                         │
│ 08:45:01  ✓  nightly-backup — success                       │
│ 08:30:00  ✗  weekly-report — failed (exit 1)                │
├──────────────────────────────────────────────────────────────┤
│ ◆ modified | CST | q:Quit j/k:Nav Space:Toggle R:Run ?:Help │
└──────────────────────────────────────────────────────────────┘
```

## Install

```bash
# From source
pip install .

# Editable (development)
pip install -e .

# Or with pipx
pipx install .
```

## Usage

```bash
lazycron          # Launch the TUI
python -m lazycron  # Alternative
```

## Keybindings

| Key | Action |
|-----|--------|
| `j` / `↓` | Navigate down |
| `k` / `↑` | Navigate up |
| `Space` | Toggle enable/disable |
| `e` | Edit selected job |
| `n` | New job wizard |
| `d` | Delete (press twice to confirm) |
| `R` | Run Now (Shift+R) |
| `s` | Save changes |
| `u` | Undo |
| `Ctrl+R` | Redo |
| `/` | Search/filter |
| `b` | Visual cron builder |
| `Tab` | Cycle panel focus |
| `?` | Help |
| `q` | Quit |

## How It Works

LazyCron reads your crontab via `crontab -l`, provides a visual interface for editing, and writes changes back via `crontab -`. All modifications are tracked with an undo stack. Changes are only applied to your system crontab when you explicitly save (`s`).

### Execution Tracking

When you save through LazyCron, each job's command is automatically wrapped with `~/.lazycron/run.sh` — a lightweight shell wrapper that runs the original command and logs the result (timestamp, exit code, job name) to `~/.lazycron/history.jsonl`. This means:

- **Cron-initiated runs** are tracked automatically — no extra configuration
- **TUI-initiated runs** (`Shift+R`) are also logged to the same history
- **Last run status** is visible per-job in both the jobs list (`✓`/`✗`) and the detail panel
- **Activity log** at the bottom shows all events with timestamps and success/failure
- **History persists** across LazyCron restarts

The wrapper is transparent — the UI always shows the original unwrapped command when editing or viewing.

### Safety Features

- **Dry-run validation** — schedule syntax is validated before saving
- **Collision warnings** — alerts when jobs overlap
- **Two-press delete** — prevents accidental removal
- **Dirty indicator** — always know if you have unsaved changes
- **Quit confirmation** — prompts before discarding changes

## Customization

### Environment Variables (`~/.lazycron/env.sh`)

LazyCron regenerates `~/.lazycron/run.sh` on every save. To persist environment variables across regenerations, create `~/.lazycron/env.sh`:

```bash
# ~/.lazycron/env.sh — sourced before every job runs
export REPO_ROOT="$HOME/my-project"
export PATH="$HOME/.local/bin:$PATH"
```

This file is sourced by the wrapper if it exists, ignored if it doesn't. Put any env vars your cron jobs need here.

## Troubleshooting

### macOS Provenance (Exit Code 126)

On macOS Sequoia+, files created by sandboxed apps (Claude Code, Zed, Cursor, etc.) get a `com.apple.provenance` extended attribute. This causes cron to reject them with **exit code 126** (permission denied), even if the file has `+x`.

**Check if a script is affected:**

```bash
xattr your_script.sh
# If you see "com.apple.provenance", that's the cause
```

**LazyCron's wrapper is already immune** — it uses `cat | /bin/sh` to pipe the wrapper content rather than executing it directly, bypassing the provenance check.

**For your own scripts** called by cron jobs, use the same pattern:

```bash
# Instead of:
/path/to/script.sh

# Use:
cat /path/to/script.sh | bash

# If your script reads stdin, use process substitution:
bash <(cat /path/to/script.sh)

# For Python:
python3 - < /path/to/script.py
```

This affects any script written by a sandboxed editor on macOS Sequoia or later.

## Requirements

- Python 3.10+
- A Unix-like system with `crontab` (macOS or Linux)
- Terminal with Unicode support (most modern terminals)
- No external Python packages required

## Development

```bash
# Install in development mode
make dev

# Run tests
make test

# Run tests (no pytest required)
make unittest

# Lint
make lint
```

## Security Note

The **Run Now** feature (`Shift+R`) executes commands directly from your crontab using `/bin/sh`. These are commands you have already configured in your own crontab — LazyCron does not accept or execute commands from any external source. Commands run with your user privileges and have a 10-minute timeout.

## License

MIT
