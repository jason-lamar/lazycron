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

- **5-panel layout** — jobs list, job details, execution history, environment variables, and command log
- **Human-readable schedules** — translates `*/15 9-17 * * 1-5` into plain English
- **Visual cron builder** — odometer-style field selector prevents syntax errors
- **Full crontab management** — create, edit, toggle, delete, and save jobs
- **Undo/redo** — every action is reversible (up to 50 levels)
- **Run Now** — test any job immediately with output capture
- **Collision detection** — warns when jobs overlap
- **Search/filter** — fuzzy-find jobs by name or command
- **Zero external dependencies** — pure Python stdlib + curses

## Layout

```
┌─ Jobs ──────────────┬─ Job Details ──────────────────────────┐
│ ● health-check.sh   │ ┌─────┬───────┬───────┬───────┬──────┐ │
│ ● nightly-backup.sh │ │ MIN │ HOUR  │  DOM  │  MON  │ DOW  │ │
│ ○ weekly-report.sh  │ ├─────┼───────┼───────┼───────┼──────┤ │
│ ● api-ping          │ │ */15│ 9-17  │   *   │   *   │  1-5 │ │
│                     │ │ :15 │ 09:00 │ Every │ Every │  Fri │ │
│                     │ └─────┴───────┴───────┴───────┴──────┘ │
│                     │ Every 15 min, 09:00–17:59, Mon–Fri     │
│                     │                                        │
│                     │ Command:   /scripts/health-check.sh    │
│                     │ Next Run:  Mon 09:15 (in 12 min)       │
│                     │ Status:    Active                      │
├─ History ───────────┼─ Env Vars ──────┬─ Cmd Log ────────────┤
│ 09:00 ✓ exit 0      │ SHELL=/bin/bash │ Job #2 disabled      │
│ 08:45 ✓ exit 0      │ PATH=/usr/bin:… │ Schedule updated     │
│ 08:30 ✗ exit 1      │ MAILTO=user@e…  │ Job #4 created       │
├─────────────────────┴─────────────────┴──────────────────────┤
│ ◆ modified | CST | q:Quit j/k:Nav Space:Toggle e:Edit ?:Help │
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
| `r` | Run Now |
| `s` | Save changes |
| `u` | Undo |
| `Ctrl+R` | Redo |
| `/` | Search/filter |
| `b` | Visual cron builder |
| `Tab` | Cycle panel focus |
| `L` | Log view |
| `?` | Help |
| `q` | Quit |

## How It Works

LazyCron reads your crontab via `crontab -l`, provides a visual interface for editing, and writes changes back via `crontab -`. All modifications are tracked with an undo stack. Changes are only applied to your system crontab when you explicitly save (`s`).

### Safety Features

- **Dry-run validation** — schedule syntax is validated before saving
- **Collision warnings** — alerts when jobs overlap
- **Two-press delete** — prevents accidental removal
- **Dirty indicator** — always know if you have unsaved changes
- **Quit confirmation** — prompts before discarding changes

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

The **Run Now** feature (`r`) executes commands directly from your crontab using `/bin/sh`. These are commands you have already configured in your own crontab — LazyCron does not accept or execute commands from any external source. Commands run with your user privileges and have a 30-second timeout.

## License

MIT
