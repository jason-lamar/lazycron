"""Splash screen shown on startup."""

from __future__ import annotations

import curses
import time

from lazycron.ui.layout import _put
from lazycron.ui.theme import C_CYAN, C_DIM, C_GREEN, C_TITLE

LOGO = [
    " ██╗      █████╗ ███████╗██╗   ██╗ ██████╗██████╗  ██████╗ ███╗   ██╗",
    " ██║     ██╔══██╗╚══███╔╝╚██╗ ██╔╝██╔════╝██╔══██╗██╔═══██╗████╗  ██║",
    " ██║     ███████║  ███╔╝  ╚████╔╝ ██║     ██████╔╝██║   ██║██╔██╗ ██║",
    " ██║     ██╔══██║ ███╔╝    ╚██╔╝  ██║     ██╔══██╗██║   ██║██║╚██╗██║",
    " ███████╗██║  ██║███████╗   ██║   ╚██████╗██║  ██║╚██████╔╝██║ ╚████║",
    " ╚══════╝╚═╝  ╚═╝╚══════╝  ╚═╝    ╚═════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝",
]

TAGLINE = "your crontab, but comfortable."
HINT = "press any key"

SPLASH_DURATION = 3.0  # seconds


def show_splash(scr) -> None:
    """Display the splash screen, then return on keypress or timeout."""
    scr.erase()

    try:
        my, mx = scr.getmaxyx()
    except curses.error:
        return

    logo_h = len(LOGO)
    logo_w = max(len(line) for line in LOGO)

    # Total block height: logo + blank + tagline + blank + hint
    block_h = logo_h + 4
    start_y = max(0, (my - block_h) // 2)

    # Draw logo centered
    logo_attr = curses.color_pair(C_CYAN) | curses.A_BOLD
    for i, line in enumerate(LOGO):
        x = max(0, (mx - len(line)) // 2)
        _put(scr, start_y + i, x, line, logo_attr)

    # Tagline
    tag_y = start_y + logo_h + 1
    tag_x = max(0, (mx - len(TAGLINE)) // 2)
    _put(scr, tag_y, tag_x, TAGLINE, curses.color_pair(C_GREEN))

    # Hint
    hint_y = tag_y + 2
    hint_x = max(0, (mx - len(HINT)) // 2)
    _put(scr, hint_y, hint_x, HINT, curses.color_pair(C_DIM) | curses.A_DIM)

    scr.refresh()

    # Sleep for the full duration, ignoring all input.
    # Terminal resize and other spurious events fire at startup
    # and break getch-based loops, so we use napms instead.
    curses.napms(int(SPLASH_DURATION * 1000))

    # Drain any keys pressed during the splash
    scr.nodelay(True)
    curses.flushinp()
    while scr.getch() != -1:
        pass

    scr.erase()
