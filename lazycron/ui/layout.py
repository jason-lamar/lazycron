"""5-panel layout geometry and render dispatch.

Creates derwin() subwindows within the main screen and dispatches
rendering to the panel modules.
"""

from __future__ import annotations

import curses
from dataclasses import dataclass
from typing import Optional

from lazycron.ui.theme import (
    BOX_BL, BOX_BR, BOX_BT, BOX_H, BOX_LT, BOX_RT, BOX_TL, BOX_TR,
    BOX_TT, BOX_V, BOX_X, C_BORDER, C_TITLE, JOBS_W, MIN_H, MIN_W,
    STATUS_H,
)


def _put(w, y: int, x: int, s: str, attr: int = 0) -> None:
    """Bounds-checked curses write — never crashes on edge."""
    try:
        my, mx = w.getmaxyx()
        if 0 <= y < my and 0 <= x < mx:
            w.addnstr(y, x, s, mx - x, attr)
    except curses.error:
        pass


@dataclass
class PanelGeometry:
    """Computed geometry for all 5 panels + status bar."""
    max_h: int
    max_w: int

    # Top row
    jobs_h: int = 0
    jobs_w: int = JOBS_W
    detail_h: int = 0
    detail_w: int = 0

    # Bottom row
    bottom_h: int = 0
    history_w: int = 0
    env_w: int = 0
    cmdlog_w: int = 0

    # Offsets (y, x) for each panel content area (inside borders)
    jobs_y: int = 0
    jobs_x: int = 0
    detail_y: int = 0
    detail_x: int = 0
    history_y: int = 0
    history_x: int = 0
    env_y: int = 0
    env_x: int = 0
    cmdlog_y: int = 0
    cmdlog_x: int = 0

    def compute(self) -> None:
        """Compute panel sizes from terminal dimensions."""
        usable_h = self.max_h - STATUS_H  # Reserve bottom row for status

        # Top row = 2/3 height, bottom row = 1/3
        self.jobs_h = usable_h * 2 // 3
        self.detail_h = self.jobs_h
        self.bottom_h = usable_h - self.jobs_h

        self.jobs_w = min(JOBS_W, self.max_w // 3)
        self.detail_w = self.max_w - self.jobs_w

        # Bottom row: 3 panels sharing width
        third = self.max_w // 3
        self.history_w = third
        self.env_w = third
        self.cmdlog_w = self.max_w - 2 * third

        # Content area offsets (1 for border on each side)
        self.jobs_y = 0
        self.jobs_x = 0
        self.detail_y = 0
        self.detail_x = self.jobs_w
        self.history_y = self.jobs_h
        self.history_x = 0
        self.env_y = self.jobs_h
        self.env_x = self.history_w
        self.cmdlog_y = self.jobs_h
        self.cmdlog_x = self.history_w + self.env_w


def compute_geometry(max_h: int, max_w: int) -> PanelGeometry:
    """Create and compute panel geometry for the given terminal size."""
    geo = PanelGeometry(max_h=max_h, max_w=max_w)
    geo.compute()
    return geo


def draw_borders(scr, geo: PanelGeometry, focused: int = 0) -> None:
    """Draw the panel borders and titles on the main screen."""
    ba = curses.color_pair(C_BORDER)
    ta = curses.color_pair(C_TITLE) | curses.A_BOLD
    fa = curses.color_pair(C_TITLE) | curses.A_BOLD | curses.A_REVERSE

    panel_titles = [
        " Jobs ", " Job Details ", " History ", " Env Vars ", " Cmd Log ",
    ]

    # -- Top-left corner
    _put(scr, 0, 0, BOX_TL, ba)

    # -- Top border with jobs title
    title = panel_titles[0]
    title_attr = fa if focused == 0 else ta
    top_border_jobs = BOX_H * (geo.jobs_w - 2)
    _put(scr, 0, 1, top_border_jobs, ba)
    if len(title) < geo.jobs_w - 2:
        _put(scr, 0, 2, title, title_attr)

    # -- Top T-junction between jobs and detail
    _put(scr, 0, geo.jobs_w, BOX_TT, ba)

    # -- Top border with detail title
    title = panel_titles[1]
    title_attr = fa if focused == 1 else ta
    top_border_detail = BOX_H * (geo.detail_w - 2)
    _put(scr, 0, geo.jobs_w + 1, top_border_detail, ba)
    if len(title) < geo.detail_w - 2:
        _put(scr, 0, geo.jobs_w + 2, title, title_attr)

    # -- Top-right corner
    _put(scr, 0, geo.max_w - 1, BOX_TR, ba)

    # -- Vertical borders for top row
    for y in range(1, geo.jobs_h):
        _put(scr, y, 0, BOX_V, ba)
        _put(scr, y, geo.jobs_w, BOX_V, ba)
        _put(scr, y, geo.max_w - 1, BOX_V, ba)

    # -- Middle horizontal divider
    mid_y = geo.jobs_h
    _put(scr, mid_y, 0, BOX_LT, ba)
    for x in range(1, geo.max_w - 1):
        _put(scr, mid_y, x, BOX_H, ba)
    _put(scr, mid_y, geo.max_w - 1, BOX_RT, ba)

    # -- T-junctions on middle divider
    _put(scr, mid_y, geo.jobs_w, BOX_BT, ba)

    # Bottom panel T-junctions
    if geo.history_w > 0 and geo.history_w < geo.max_w - 1:
        _put(scr, mid_y, geo.history_w, BOX_TT, ba)
    if geo.history_w + geo.env_w > 0 and geo.history_w + geo.env_w < geo.max_w - 1:
        _put(scr, mid_y, geo.history_w + geo.env_w, BOX_TT, ba)

    # -- Bottom panel titles on the middle divider
    titles_bottom = [
        (2, panel_titles[2], geo.history_w - 2, geo.history_x),
        (3, panel_titles[3], geo.env_w - 2, geo.env_x),
        (4, panel_titles[4], geo.cmdlog_w - 2, geo.cmdlog_x),
    ]
    for panel_idx, title, avail, x_off in titles_bottom:
        title_attr = fa if focused == panel_idx else ta
        if len(title) < avail:
            _put(scr, mid_y, x_off + 2, title, title_attr)

    # -- Vertical borders for bottom row
    bot_end = geo.jobs_h + geo.bottom_h
    for y in range(mid_y + 1, bot_end):
        _put(scr, y, 0, BOX_V, ba)
        if geo.history_w < geo.max_w - 1:
            _put(scr, y, geo.history_w, BOX_V, ba)
        if geo.history_w + geo.env_w < geo.max_w - 1:
            _put(scr, y, geo.history_w + geo.env_w, BOX_V, ba)
        _put(scr, y, geo.max_w - 1, BOX_V, ba)

    # -- Bottom border
    _put(scr, bot_end, 0, BOX_BL, ba)
    for x in range(1, geo.max_w - 1):
        _put(scr, bot_end, x, BOX_H, ba)
    _put(scr, bot_end, geo.max_w - 1, BOX_BR, ba)

    # Bottom T-junctions
    if geo.history_w < geo.max_w - 1:
        _put(scr, bot_end, geo.history_w, BOX_BT, ba)
    if geo.history_w + geo.env_w < geo.max_w - 1:
        _put(scr, bot_end, geo.history_w + geo.env_w, BOX_BT, ba)
