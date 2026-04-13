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

    hints_y = my - 2   # Key hints row
    status_y = my - 1  # Status row (dirty, messages) — bottom-most
    attr = curses.color_pair(C_STATUS)

    # -- Status row: only show when there's something actionable --
    parts = []
    if store.dirty:
        parts.append(f"{IND_MODIFIED} unsaved changes")

    now = time.time()
    if store.message and (now - store.message_time) < MSG_DURATION:
        parts.append(store.message)
    elif store.delete_pending and (now - store.delete_pending) < 3.0:
        parts.append("Press d again to confirm delete")

    if parts:
        left = " " + " | ".join(parts)
        status_bar = left + " " * max(0, mx - len(left))
        _put(scr, status_y, 0, status_bar[:mx], attr)

    # -- Key hints row: build full-width string, write once --
    hints = " q:Quit  j/k:Nav  Space:Toggle  e:Edit  n:New  d:Del  R:Run  s:Save  u:Undo  ?:Help"
    hints_bar = hints + " " * max(0, mx - len(hints))
    _put(scr, hints_y, 0, hints_bar[:mx], attr)
