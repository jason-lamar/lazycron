"""Bottom status bar: timezone, dirty indicator, key hints, messages."""

from __future__ import annotations

import curses
import time

from lazycron.state import Store
from lazycron.ui.layout import _put
from lazycron.ui.theme import C_STATUS, IND_MODIFIED, MIN_W

# Message display duration in seconds
MSG_DURATION = 3.0


def draw_statusbar(scr, store: Store) -> None:
    """Render the bottom status bar (2 rows: status + key hints)."""
    my, mx = scr.getmaxyx()
    if mx < MIN_W:
        return

    status_y = my - 2  # Status row (dirty, timezone, messages)
    hints_y = my - 1   # Key hints row (always visible)
    attr = curses.color_pair(C_STATUS)

    # -- Status row: build full-width string, write once --
    if store.dirty:
        dirty_str = f" {IND_MODIFIED} modified"
    else:
        dirty_str = "  saved   "

    try:
        tz = time.tzname[0]
    except (IndexError, AttributeError):
        tz = "UTC"

    msg = ""
    now = time.time()
    if store.message and (now - store.message_time) < MSG_DURATION:
        msg = store.message
    elif store.delete_pending and (now - store.delete_pending) < 3.0:
        msg = "Press d again to confirm delete"

    left = f"{dirty_str} | {tz} | {msg}"
    status_bar = left + " " * max(0, mx - len(left))
    _put(scr, status_y, 0, status_bar[:mx], attr)

    # -- Key hints row: build full-width string, write once --
    hints = " q:Quit  j/k:Nav  Space:Toggle  e:Edit  n:New  d:Del  R:Run  s:Save  u:Undo  ?:Help"
    hints_bar = hints + " " * max(0, mx - len(hints))
    _put(scr, hints_y, 0, hints_bar[:mx], attr)
