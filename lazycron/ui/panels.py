"""Panel rendering: jobs list, job detail, history, env vars, cmd log.

Each draw_* function takes the main screen, geometry, and state,
and renders its content within the allocated region.
"""

from __future__ import annotations

import curses
import time
from datetime import datetime
from typing import Optional

from lazycron.cron import DOW_LABELS, MONTH_LABELS
from lazycron.crontab import Job, EnvVar
from lazycron.logs import ExecutionRecord
from lazycron.state import Store
from lazycron.ui.layout import PanelGeometry, _put
from lazycron.ui.theme import (
    BOX_H, BOX_V, BOX_TL, BOX_TR, BOX_BL, BOX_BR,
    BOX_TT, BOX_BT, BOX_LT, BOX_RT, BOX_X,
    C_ACTIVE, C_CYAN, C_DIM, C_DISABLED, C_GREEN, C_MAGENTA,
    C_RED, C_SELECTED, C_WHITE, C_YELLOW,
    IND_ACTIVE, IND_DISABLED, IND_SUCCESS, IND_FAILURE,
)


def draw_jobs_panel(scr, geo: PanelGeometry, store: Store) -> None:
    """Render the jobs list in the left panel."""
    # Content area: inside borders
    x_start = 1
    y_start = 1
    avail_w = geo.jobs_w - 2  # Border on each side
    avail_h = geo.jobs_h - 1  # Top border

    jobs = store.jobs
    if not jobs:
        _put(scr, y_start + 1, x_start + 1, "No cron jobs found",
             curses.color_pair(C_DIM) | curses.A_DIM)
        _put(scr, y_start + 2, x_start + 1, "Press 'n' to create one",
             curses.color_pair(C_DIM) | curses.A_DIM)
        return

    # Scrolling: keep selected job visible
    scroll_off = 0
    if store.selected >= avail_h:
        scroll_off = store.selected - avail_h + 1

    for i in range(avail_h):
        idx = scroll_off + i
        y = y_start + i
        if idx >= len(jobs):
            # Clear remaining lines
            _put(scr, y, x_start, " " * avail_w, curses.A_NORMAL)
            continue

        job = jobs[idx]
        is_selected = (idx == store.selected)

        # Build display line
        indicator = IND_ACTIVE if job.enabled else IND_DISABLED
        name = job.display_name
        # Truncate to fit
        max_name = avail_w - 3  # indicator + space + padding
        if len(name) > max_name:
            name = name[:max_name - 3] + "..."

        line = f" {indicator} {name}"
        line = line.ljust(avail_w)

        if is_selected:
            attr = curses.color_pair(C_SELECTED) | curses.A_BOLD
        elif job.enabled:
            attr = curses.color_pair(C_ACTIVE)
        else:
            attr = curses.color_pair(C_DISABLED) | curses.A_DIM

        _put(scr, y, x_start, line[:avail_w], attr)

    # Scroll indicator
    if len(jobs) > avail_h:
        total = len(jobs)
        pos = f"{store.selected + 1}/{total}"
        _put(scr, y_start + avail_h - 1, x_start + avail_w - len(pos) - 1,
             pos, curses.color_pair(C_DIM) | curses.A_DIM)


def _friendly_value(raw: str, field: str) -> str:
    """Translate a raw cron field value into a human-friendly label."""
    if raw.strip() == "*":
        return "Every"
    if "/" in raw or "," in raw or "-" in raw:
        return raw  # Complex expressions stay as-is

    try:
        val = int(raw)
    except ValueError:
        return raw

    if field == "dow":
        if 0 <= val <= 6:
            return DOW_LABELS[val]
        if val == 7:
            return DOW_LABELS[0]  # Sunday
    elif field == "month":
        if 1 <= val <= 12:
            return MONTH_LABELS[val]
    elif field == "dom":
        suffix = "th"
        if val % 10 == 1 and val != 11:
            suffix = "st"
        elif val % 10 == 2 and val != 12:
            suffix = "nd"
        elif val % 10 == 3 and val != 13:
            suffix = "rd"
        return f"{val}{suffix}"
    elif field == "hour":
        return f"{val:02d}:00"
    elif field == "minute":
        return f":{val:02d}"

    return raw


def _draw_cron_table(scr, row: int, x: int, avail_w: int, job) -> int:
    """Draw a visual cron field breakdown table. Returns next row."""
    headers = ["MIN", "HOUR", "DOM", "MON", "DOW"]
    raw_values = [
        job.schedule.minute,
        job.schedule.hour,
        job.schedule.dom,
        job.schedule.month,
        job.schedule.dow,
    ]
    fields = ["minute", "hour", "dom", "month", "dow"]
    display = [_friendly_value(v, f) for v, f in zip(raw_values, fields)]

    # Column widths: max of header, raw value, and display value, plus 2 padding
    col_w = [max(len(h), len(v), len(d)) + 2
             for h, v, d in zip(headers, raw_values, display)]
    table_w = sum(col_w) + len(col_w) + 1

    ba = curses.color_pair(C_DIM) | curses.A_DIM          # Border
    ha = curses.color_pair(C_CYAN) | curses.A_BOLD         # Headers
    val_a = curses.color_pair(C_GREEN) | curses.A_BOLD     # Values
    star_a = curses.color_pair(C_DIM)                      # Wildcard *
    disp_a = curses.color_pair(C_WHITE)                    # Display row
    desc_a = curses.color_pair(C_MAGENTA)                  # Description

    # -- Top border: ┌───┬───┬───┐
    top = BOX_TL
    for i, w in enumerate(col_w):
        top += BOX_H * w
        top += BOX_TT if i < len(col_w) - 1 else BOX_TR
    _put(scr, row, x, top, ba)
    row += 1

    # -- Header row: │ MIN │ HOUR │ ...
    for i, (h, w) in enumerate(zip(headers, col_w)):
        _put(scr, row, x + _col_offset(col_w, i), BOX_V, ba)
        _put(scr, row, x + _col_offset(col_w, i) + 1, h.center(w), ha)
    _put(scr, row, x + _col_offset(col_w, len(col_w)), BOX_V, ba)
    row += 1

    # -- Middle border: ├───┼───┼───┤
    mid = BOX_LT
    for i, w in enumerate(col_w):
        mid += BOX_H * w
        mid += BOX_X if i < len(col_w) - 1 else BOX_RT
    _put(scr, row, x, mid, ba)
    row += 1

    # -- Raw value row: │  0  │  12  │  *  │
    for i, (v, w) in enumerate(zip(raw_values, col_w)):
        _put(scr, row, x + _col_offset(col_w, i), BOX_V, ba)
        attr = star_a if v.strip() == "*" else val_a
        _put(scr, row, x + _col_offset(col_w, i) + 1, v.center(w), attr)
    _put(scr, row, x + _col_offset(col_w, len(col_w)), BOX_V, ba)
    row += 1

    # -- Display row: │ :00 │ 12:00│Every│ Every│Friday│
    for i, (d, v, w) in enumerate(zip(display, raw_values, col_w)):
        _put(scr, row, x + _col_offset(col_w, i), BOX_V, ba)
        attr = star_a if v.strip() == "*" else disp_a
        _put(scr, row, x + _col_offset(col_w, i) + 1, d.center(w), attr)
    _put(scr, row, x + _col_offset(col_w, len(col_w)), BOX_V, ba)
    row += 1

    # -- Bottom border: └───┴───┴───┘
    bot = BOX_BL
    for i, w in enumerate(col_w):
        bot += BOX_H * w
        bot += BOX_BT if i < len(col_w) - 1 else BOX_BR
    _put(scr, row, x, bot, ba)
    row += 1

    # -- Human-readable description below the table
    desc = job.schedule.describe()
    if len(desc) > avail_w:
        desc = desc[:avail_w - 3] + "..."
    _put(scr, row, x, desc, desc_a)
    row += 1

    return row


def _col_offset(col_w: list[int], col: int) -> int:
    """Compute the x offset to the left border of column `col`."""
    return sum(col_w[:col]) + col


def draw_detail_panel(scr, geo: PanelGeometry, store: Store) -> None:
    """Render job details in the center panel."""
    x_start = geo.detail_x + 1
    y_start = 1
    avail_w = geo.detail_w - 2
    avail_h = geo.detail_h - 1

    job = store.selected_job
    if not job:
        _put(scr, y_start + 1, x_start + 1, "No job selected",
             curses.color_pair(C_DIM) | curses.A_DIM)
        return

    la = curses.color_pair(C_CYAN) | curses.A_BOLD  # Label attribute
    va = curses.A_NORMAL  # Value attribute

    row = y_start

    # Schedule — visual cron field table
    row = _draw_cron_table(scr, row, x_start + 1, avail_w - 2, job)
    row += 1  # Blank line

    # Command (word-wrapped)
    _put(scr, row, x_start + 1, "Command:", la)
    cmd = job.command
    cmd_indent = 12  # Aligns with other values
    cmd_w = avail_w - cmd_indent - 1
    if cmd_w > 0:
        # First line after label
        _put(scr, row, x_start + cmd_indent, cmd[:cmd_w], va)
        row += 1
        # Continuation lines
        pos = cmd_w
        while pos < len(cmd):
            chunk = cmd[pos:pos + cmd_w]
            _put(scr, row, x_start + cmd_indent, chunk, va)
            row += 1
            pos += cmd_w
    else:
        row += 1

    # Name (stored as crontab comment)
    if job.comment:
        _put(scr, row, x_start + 1, "Name:", la)
        _put(scr, row, x_start + 12, job.comment[:avail_w - 13], va)
        row += 1

    row += 1  # Blank line

    # Next run
    valid, _ = job.schedule.validate()
    if valid:
        nxt = job.schedule.next_run()
        if nxt:
            _put(scr, row, x_start + 1, "Next Run:", la)
            now = datetime.now()
            delta = nxt - now
            mins = int(delta.total_seconds() / 60)
            if mins < 60:
                rel = f"in {mins} min"
            elif mins < 1440:
                rel = f"in {mins // 60}h {mins % 60}m"
            else:
                rel = f"in {mins // 1440}d"
            nxt_str = nxt.strftime("%a %H:%M")
            _put(scr, row, x_start + 12, f"{nxt_str} ({rel})", va)
            row += 1

    # Status
    _put(scr, row, x_start + 1, "Status:", la)
    if job.enabled:
        _put(scr, row, x_start + 12, "Active",
             curses.color_pair(C_GREEN) | curses.A_BOLD)
    else:
        _put(scr, row, x_start + 12, "Disabled",
             curses.color_pair(C_RED) | curses.A_DIM)
    row += 1

    # Timezone
    try:
        tz = time.tzname[0]
    except (IndexError, AttributeError):
        tz = "UTC"
    _put(scr, row, x_start + 1, "Timezone:", la)
    _put(scr, row, x_start + 12, tz, va)

    # Collision detection
    if valid and job.enabled:
        row += 2
        collisions = _detect_collisions(store, job)
        if collisions:
            _put(scr, row, x_start + 1, "Collisions:",
                 curses.color_pair(C_YELLOW) | curses.A_BOLD)
            row += 1
            for col_msg in collisions[:3]:
                _put(scr, row, x_start + 3,
                     f"! {col_msg}"[:avail_w - 4],
                     curses.color_pair(C_YELLOW))
                row += 1


def _detect_collisions(store: Store, job: Job) -> list[str]:
    """Check if other enabled jobs run at the same time as this one."""
    collisions = []
    try:
        my_times = set(job.schedule.next_n(24))
    except Exception:
        return []

    for other in store.crontab.jobs:
        if other is job or not other.enabled:
            continue
        try:
            other_times = set(other.schedule.next_n(24))
        except Exception:
            continue
        overlap = my_times & other_times
        if overlap:
            t = min(overlap)
            collisions.append(
                f"{other.display_name} at {t.strftime('%a %H:%M')}"
            )
    return collisions


def draw_history_panel(scr, geo: PanelGeometry, store: Store,
                       history: list[ExecutionRecord]) -> None:
    """Render execution history in the bottom-left panel."""
    x_start = geo.history_x + 1
    y_start = geo.history_y + 1
    avail_w = geo.history_w - 2
    avail_h = geo.bottom_h - 2

    if not history:
        _put(scr, y_start, x_start + 1, "No history",
             curses.color_pair(C_DIM) | curses.A_DIM)
        return

    for i, rec in enumerate(history[:avail_h]):
        y = y_start + i
        if rec.success:
            ind = IND_SUCCESS
            attr = curses.color_pair(C_GREEN)
        else:
            ind = IND_FAILURE
            attr = curses.color_pair(C_RED)

        line = f"{rec.time_str} {ind} exit {rec.exit_code}"
        _put(scr, y, x_start + 1, line[:avail_w - 2], attr)


def draw_env_panel(scr, geo: PanelGeometry, store: Store) -> None:
    """Render environment variables in the bottom-center panel."""
    x_start = geo.env_x + 1
    y_start = geo.env_y + 1
    avail_w = geo.env_w - 2
    avail_h = geo.bottom_h - 2

    env_vars = store.crontab.env_vars
    if not env_vars:
        _put(scr, y_start, x_start + 1, "No env vars",
             curses.color_pair(C_DIM) | curses.A_DIM)
        return

    for i, ev in enumerate(env_vars[:avail_h]):
        y = y_start + i
        line = f"{ev.key}={ev.value}"
        if len(line) > avail_w - 2:
            line = line[:avail_w - 5] + "..."
        _put(scr, y, x_start + 1, line, curses.A_NORMAL)


def draw_cmdlog_panel(scr, geo: PanelGeometry, store: Store) -> None:
    """Render the command log in the bottom-right panel."""
    x_start = geo.cmdlog_x + 1
    y_start = geo.cmdlog_y + 1
    avail_w = geo.cmdlog_w - 2
    avail_h = geo.bottom_h - 2

    entries = store.action_log
    if not entries:
        _put(scr, y_start, x_start + 1, "No actions yet",
             curses.color_pair(C_DIM) | curses.A_DIM)
        return

    # Show most recent entries
    visible = entries[-avail_h:] if len(entries) > avail_h else entries
    for i, entry in enumerate(visible):
        y = y_start + i
        line = f"{entry.message}"
        if len(line) > avail_w - 2:
            line = line[:avail_w - 5] + "..."
        _put(scr, y, x_start + 1, line, curses.color_pair(C_DIM))
