"""Bottom status bar: timezone, dirty indicator, key hints, messages."""

from __future__ import annotations

import curses
import time

from lazycron.state import Store
from lazycron.ui.layout import _put
from lazycron.ui.theme import (
    C_GREEN, C_RED, C_STATUS, C_YELLOW,
    IND_MODIFIED, MIN_W,
)

# Message display duration in seconds
MSG_DURATION = 3.0


def draw_statusbar(scr, store: Store) -> None:
    """Render the bottom status bar."""
    my, mx = scr.getmaxyx()
    if mx < MIN_W:
        return

    bar_y = my - 1
    attr = curses.color_pair(C_STATUS)

    # Clear the bar
    _put(scr, bar_y, 0, " " * mx, attr)

    x = 1

    # Dirty indicator
    if store.dirty:
        _put(scr, bar_y, x, f"{IND_MODIFIED} modified",
             curses.color_pair(C_YELLOW) | curses.A_BOLD)
        x += 11
    else:
        _put(scr, bar_y, x, "  saved   ",
             curses.color_pair(C_GREEN))
        x += 11

    # Separator
    _put(scr, bar_y, x, " | ", attr)
    x += 3

    # Timezone
    try:
        tz = time.tzname[0]
    except (IndexError, AttributeError):
        tz = "UTC"
    _put(scr, bar_y, x, tz, attr)
    x += len(tz) + 1

    # Separator
    _put(scr, bar_y, x, " | ", attr)
    x += 3

    # Transient message or key hints
    now = time.time()
    if store.message and (now - store.message_time) < MSG_DURATION:
        _put(scr, bar_y, x, store.message[:mx - x - 1],
             curses.color_pair(C_YELLOW) | curses.A_BOLD)
    else:
        # Delete pending warning
        if store.delete_pending and (now - store.delete_pending) < 3.0:
            _put(scr, bar_y, x, "Press d again to confirm delete",
                 curses.color_pair(C_RED) | curses.A_BOLD)
        else:
            hints = "q:Quit j/k:Nav Space:Toggle e:Edit n:New d:Del s:Save u:Undo ?:Help"
            _put(scr, bar_y, x, hints[:mx - x - 1], attr)
