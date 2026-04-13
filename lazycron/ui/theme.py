"""Color pairs, border characters, and visual constants.

Mirrors the monitor's color-init pattern with additional pairs
for LazyCron's multi-panel layout.
"""

import curses

# -- Color pair IDs -----------------------------------------------------------
# Match monitor pattern: sequential IDs starting from 1

C_GREEN = 1
C_RED = 2
C_BLUE = 3
C_CYAN = 4
C_YELLOW = 5
C_DIM = 6
C_HDR = 7
C_WHITE = 8
C_MAGENTA = 9
C_STATUS = 10
C_ACTIVE = 11
C_DISABLED = 12
C_SELECTED = 13
C_BORDER = 14
C_TITLE = 15
C_ERROR = 16


def init_colors() -> None:
    """Initialize all color pairs. Call once after curses.initscr()."""
    curses.start_color()
    curses.use_default_colors()

    curses.init_pair(C_GREEN, curses.COLOR_GREEN, -1)
    curses.init_pair(C_RED, curses.COLOR_RED, -1)
    curses.init_pair(C_BLUE, curses.COLOR_BLUE, -1)
    curses.init_pair(C_CYAN, curses.COLOR_CYAN, -1)
    curses.init_pair(C_YELLOW, curses.COLOR_YELLOW, -1)
    curses.init_pair(C_DIM, curses.COLOR_WHITE, -1)
    curses.init_pair(C_HDR, curses.COLOR_WHITE, curses.COLOR_BLUE)
    curses.init_pair(C_WHITE, curses.COLOR_WHITE, -1)
    curses.init_pair(C_MAGENTA, curses.COLOR_MAGENTA, -1)
    curses.init_pair(C_STATUS, curses.COLOR_CYAN, -1)
    curses.init_pair(C_ACTIVE, curses.COLOR_GREEN, -1)
    curses.init_pair(C_DISABLED, curses.COLOR_WHITE, -1)
    curses.init_pair(C_SELECTED, curses.COLOR_BLACK, curses.COLOR_CYAN)
    curses.init_pair(C_BORDER, curses.COLOR_BLUE, -1)
    curses.init_pair(C_TITLE, curses.COLOR_CYAN, -1)
    curses.init_pair(C_ERROR, curses.COLOR_WHITE, curses.COLOR_RED)


# -- Border characters (Unicode box-drawing) ----------------------------------

BOX_H = "\u2500"   # ─
BOX_V = "\u2502"   # │
BOX_TL = "\u250c"  # ┌
BOX_TR = "\u2510"  # ┐
BOX_BL = "\u2514"  # └
BOX_BR = "\u2518"  # ┘
BOX_LT = "\u251c"  # ├
BOX_RT = "\u2524"  # ┤
BOX_TT = "\u252c"  # ┬
BOX_BT = "\u2534"  # ┴
BOX_X = "\u253c"   # ┼

# -- Status indicators -------------------------------------------------------

IND_ACTIVE = "\u25cf"    # ●
IND_DISABLED = "\u25cb"  # ○
IND_SUCCESS = "\u2713"   # ✓
IND_FAILURE = "\u2717"   # ✗
IND_MODIFIED = "\u25c6"  # ◆
IND_ARROW_UP = "\u25b2"  # ▲
IND_ARROW_DN = "\u25bc"  # ▼

# -- Layout constants ---------------------------------------------------------

JOBS_W = 26       # Fixed width for jobs list panel
MIN_W = 80        # Minimum terminal width
MIN_H = 20        # Minimum terminal height
STATUS_H = 3      # Bottom border + status bar + key hints
