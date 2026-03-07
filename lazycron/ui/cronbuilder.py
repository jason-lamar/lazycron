"""Visual cron expression builder — odometer-style field selector.

Five columns, each cycling through preset values for one cron field.
Arrow keys switch fields and cycle values. Live preview of the
human-readable schedule updates as you change fields.
"""

from __future__ import annotations

import curses
from typing import Optional

from lazycron.cron import FIELD_PRESETS, FIELD_NAMES, parse_expression
from lazycron.ui.layout import _put
from lazycron.ui.theme import (
    BOX_BL, BOX_BR, BOX_H, BOX_TL, BOX_TR, BOX_V,
    C_BORDER, C_CYAN, C_DIM, C_GREEN, C_RED, C_TITLE, C_YELLOW,
    IND_ARROW_DN, IND_ARROW_UP,
)

# Field display labels
FIELD_LABELS = ["Min", "Hour", "Dom", "Mon", "Dow"]


def _find_preset_index(value: str, presets: list[str]) -> int:
    """Find the index of a value in the presets list, or 0 if not found."""
    try:
        return presets.index(value)
    except ValueError:
        return 0


def show_cron_builder(scr, initial: str = "* * * * *",
                      command: str = "") -> Optional[str]:
    """Visual cron builder modal.

    Returns the new cron expression string, or None if cancelled.
    """
    # Parse initial expression into fields
    parts = initial.strip().split()
    while len(parts) < 5:
        parts.append("*")

    # Track current index into each field's preset list
    field_indices: list[int] = []
    field_values: list[str] = list(parts[:5])

    for i, name in enumerate(FIELD_NAMES):
        presets = FIELD_PRESETS[name]
        idx = _find_preset_index(parts[i], presets)
        field_indices.append(idx)
        # If the initial value isn't a preset, keep it but start at index 0
        if parts[i] not in presets:
            field_values[i] = parts[i]

    active_field = 0  # Currently focused field (0-4)
    custom_mode = False  # Whether we're in custom text entry mode

    # Modal dimensions
    width = min(62, curses.COLS - 4)
    height = 18
    my, mx = scr.getmaxyx()
    cy = max(0, my // 2 - height // 2)
    cx = max(0, mx // 2 - width // 2)

    try:
        win = curses.newwin(height, width, cy, cx)
    except curses.error:
        return None
    win.keypad(True)

    while True:
        win.erase()

        # Border and title
        try:
            win.box()
        except curses.error:
            pass
        ta = curses.color_pair(C_TITLE) | curses.A_BOLD
        _put(win, 0, 2, " Edit Schedule ", ta)

        # Draw 5 field columns
        col_w = 9  # Width of each column
        start_x = 3
        start_y = 2

        for i in range(5):
            cx = start_x + i * (col_w + 1)
            label = FIELD_LABELS[i]
            is_active = (i == active_field)

            # Label
            la = curses.color_pair(C_CYAN) | curses.A_BOLD if is_active else curses.A_NORMAL
            _put(win, start_y, cx, f"{label:^{col_w}}", la)

            # Up arrow
            arrow_attr = curses.color_pair(C_GREEN) if is_active else curses.color_pair(C_DIM)
            _put(win, start_y + 1, cx + col_w // 2, IND_ARROW_UP, arrow_attr)

            # Value box
            val = field_values[i]
            if is_active:
                val_attr = curses.color_pair(C_CYAN) | curses.A_BOLD | curses.A_REVERSE
            else:
                val_attr = curses.A_NORMAL

            # Draw value centered in column
            _put(win, start_y + 2, cx, f"{val:^{col_w}}", val_attr)

            # Down arrow
            _put(win, start_y + 3, cx + col_w // 2, IND_ARROW_DN, arrow_attr)

        # Compose the current expression
        expr_str = " ".join(field_values)
        expr = parse_expression(expr_str)
        valid, err = expr.validate()

        # Description preview
        desc_y = start_y + 5
        _put(win, desc_y, 3, " " * (width - 6), curses.A_NORMAL)
        if valid:
            desc = expr.describe()
            # Wrap long descriptions
            max_desc_w = width - 6
            if len(desc) <= max_desc_w:
                _put(win, desc_y, 3, desc,
                     curses.color_pair(C_GREEN) | curses.A_DIM)
            else:
                _put(win, desc_y, 3, desc[:max_desc_w],
                     curses.color_pair(C_GREEN) | curses.A_DIM)
                if len(desc) > max_desc_w:
                    _put(win, desc_y + 1, 3, desc[max_desc_w:max_desc_w * 2],
                         curses.color_pair(C_GREEN) | curses.A_DIM)
        else:
            _put(win, desc_y, 3, f"Invalid: {err}"[:width - 6],
                 curses.color_pair(C_RED))

        # Raw expression preview
        raw_y = desc_y + 2
        _put(win, raw_y, 3, f"Expression: {expr_str}",
             curses.color_pair(C_DIM))

        # Command preview (if provided)
        if command:
            _put(win, raw_y + 1, 3, f"Command: {command}"[:width - 6],
                 curses.color_pair(C_DIM))

        # Instructions
        inst_y = height - 3
        ha = curses.color_pair(C_DIM) | curses.A_DIM
        _put(win, inst_y, 3, "Left/Right: switch field  Up/Down: cycle value", ha)
        _put(win, inst_y + 1, 3, "c: custom value  Enter: apply  Esc: cancel", ha)

        win.refresh()

        # Input
        try:
            key = win.getch()
        except curses.error:
            continue

        if key == 27:  # Escape
            return None
        elif key in (curses.KEY_ENTER, 10, 13):
            if valid:
                return expr_str
            # Flash error
            _put(win, desc_y, 3, "Fix errors before applying!",
                 curses.color_pair(C_RED) | curses.A_BOLD)
            win.refresh()
            curses.napms(800)
        elif key == curses.KEY_LEFT:
            active_field = (active_field - 1) % 5
        elif key == curses.KEY_RIGHT:
            active_field = (active_field + 1) % 5
        elif key in (curses.KEY_UP, ord("k")):
            _cycle_field(field_indices, field_values, active_field, -1)
        elif key in (curses.KEY_DOWN, ord("j")):
            _cycle_field(field_indices, field_values, active_field, 1)
        elif key == ord("c"):
            # Custom value entry
            custom = _custom_value_input(win, active_field, field_values[active_field])
            if custom is not None:
                field_values[active_field] = custom


def _cycle_field(indices: list[int], values: list[str],
                 field_idx: int, direction: int) -> None:
    """Cycle through presets for a given field."""
    name = FIELD_NAMES[field_idx]
    presets = FIELD_PRESETS[name]
    current = indices[field_idx]

    new_idx = (current + direction) % len(presets)
    indices[field_idx] = new_idx
    values[field_idx] = presets[new_idx]


def _custom_value_input(win, field_idx: int, current: str) -> Optional[str]:
    """Allow typing a custom value for a field."""
    height, width = win.getmaxyx()
    prompt_y = height - 5

    _put(win, prompt_y, 3, " " * (width - 6), curses.A_NORMAL)
    _put(win, prompt_y, 3,
         f"Enter custom {FIELD_LABELS[field_idx]} value: ",
         curses.color_pair(C_CYAN))

    buf = list(current)
    cursor = len(buf)
    input_x = 3 + len(f"Enter custom {FIELD_LABELS[field_idx]} value: ")
    input_w = width - input_x - 3

    while True:
        # Draw input
        text = "".join(buf)
        _put(win, prompt_y, input_x, " " * input_w, curses.A_NORMAL)
        _put(win, prompt_y, input_x, text[:input_w], curses.A_NORMAL)
        try:
            curses.curs_set(1)
            win.move(prompt_y, input_x + min(cursor, input_w - 1))
        except curses.error:
            pass
        win.refresh()

        try:
            key = win.getch()
        except curses.error:
            continue

        if key == 27:
            try:
                curses.curs_set(0)
            except curses.error:
                pass
            return None
        elif key in (curses.KEY_ENTER, 10, 13):
            try:
                curses.curs_set(0)
            except curses.error:
                pass
            return "".join(buf) if buf else None
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            if cursor > 0:
                buf.pop(cursor - 1)
                cursor -= 1
        elif key == curses.KEY_LEFT:
            cursor = max(0, cursor - 1)
        elif key == curses.KEY_RIGHT:
            cursor = min(len(buf), cursor + 1)
        elif 32 <= key <= 126:
            buf.insert(cursor, chr(key))
            cursor += 1
