"""Modal dialogs: edit, new job wizard, delete confirm, search, help, log view.

Modals are curses subwindows rendered on top of the main layout.
Each modal runs its own input loop and returns a result.

The edit and new-job modals use an integrated 5-field schedule form
with individual entry boxes per cron field, live validation preview,
and preset cycling via Up/Down arrows.
"""

from __future__ import annotations

import curses
import subprocess
from typing import Optional


def _clipboard_paste() -> str:
    """Read text from the system clipboard (macOS pbpaste)."""
    try:
        result = subprocess.run(
            ["pbpaste"], capture_output=True, text=True, timeout=2,
        )
        return result.stdout.replace("\n", " ").replace("\r", "")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


def _drain_paste(win, first_char: str) -> str:
    """Detect and drain a rapid paste burst from the terminal.

    When a user pastes text, the terminal sends all characters in a burst
    faster than any human can type.  We use nodelay mode to read all
    immediately-available characters and combine them with the first one.
    """
    buf = [first_char]
    win.nodelay(True)
    try:
        while True:
            ch = win.getch()
            if ch == -1:
                break
            if 32 <= ch <= 126:
                buf.append(chr(ch))
            # Absorb control chars from paste (tabs, etc) but don't add them
    finally:
        win.nodelay(False)
    return "".join(buf)

from lazycron.cron import (
    FIELD_NAMES, FIELD_PRESETS, FIELD_RANGES, PRESET_LABELS,
    parse_expression, parse_field,
)
from lazycron.ui.layout import _put
from lazycron.ui.theme import (
    BOX_BL, BOX_BR, BOX_H, BOX_TL, BOX_TR, BOX_V,
    C_BORDER, C_CYAN, C_DIM, C_GREEN, C_RED, C_SELECTED, C_TITLE,
    C_YELLOW, C_WHITE, IND_ARROW_DN, IND_ARROW_UP,
)

# ── Shared helpers ──────────────────────────────────────────────────────────

FIELD_LABELS = ["Minute", "Hour", "Day", "Month", "Weekday"]
FIELD_SHORT  = ["MIN", "HOUR", "DOM", "MON", "DOW"]
FIELD_W = 9       # Character width of each field input box
FIELD_GAP = 1     # Gap between field boxes
FORM_FIELDS = 7   # 5 cron fields + name + command
NAME_FIELD = 5
CMD_FIELD = 6


def _center_win(scr, height: int, width: int):
    """Create a centered window."""
    my, mx = scr.getmaxyx()
    cy = max(0, my // 2 - height // 2)
    cx = max(0, mx // 2 - width // 2)
    height = min(height, my - cy)
    width = min(width, mx - cx)
    try:
        win = curses.newwin(height, width, cy, cx)
    except curses.error:
        return None
    win.keypad(True)
    return win


def _draw_modal_frame(win, title: str) -> None:
    """Draw border and title on a modal window."""
    try:
        win.box()
    except curses.error:
        pass
    ta = curses.color_pair(C_TITLE) | curses.A_BOLD
    _put(win, 0, 2, f" {title} ", ta)


def _find_preset_index(value: str, presets: list[str]) -> int:
    """Find the index of a value in the presets list, or -1 if not found."""
    try:
        return presets.index(value)
    except ValueError:
        return -1


# ── Field box renderer ──────────────────────────────────────────────────────

def _draw_field_box(win, y: int, x: int, label: str, value: str,
                    active: bool, valid: bool) -> None:
    """Draw a single cron field input box with label.

    Layout (3 rows tall, FIELD_W + 2 wide):
        MINUTE
       ┌─────────┐
       │  */15   │
       └─────────┘
    """
    bw = FIELD_W + 2  # box width including borders
    ba = curses.color_pair(C_BORDER)

    # Label (above box)
    if active:
        la = curses.color_pair(C_CYAN) | curses.A_BOLD
    else:
        la = curses.color_pair(C_DIM)
    _put(win, y, x, f"{label:^{bw}}", la)

    # Box border color
    if active:
        bc = curses.color_pair(C_CYAN) | curses.A_BOLD
    elif not valid:
        bc = curses.color_pair(C_RED)
    else:
        bc = ba

    # Top border
    _put(win, y + 1, x, BOX_TL + BOX_H * FIELD_W + BOX_TR, bc)

    # Value row
    _put(win, y + 2, x, BOX_V, bc)
    if active:
        va = curses.color_pair(C_WHITE) | curses.A_BOLD
    elif not valid:
        va = curses.color_pair(C_RED) | curses.A_DIM
    else:
        va = curses.A_NORMAL
    # Center the value in the box
    display = value[:FIELD_W]
    _put(win, y + 2, x + 1, f"{display:^{FIELD_W}}", va)
    _put(win, y + 2, x + FIELD_W + 1, BOX_V, bc)

    # Bottom border
    _put(win, y + 3, x, BOX_BL + BOX_H * FIELD_W + BOX_BR, bc)


def _draw_text_field(win, y: int, x: int, width: int, label: str,
                     value: str, active: bool, cursor: int = -1,
                     rows: int = 1) -> tuple[int, int]:
    """Draw a labelled full-width text input field with wrapping.

    Args:
        rows: Number of visible text rows inside the box.

    Returns:
        (cursor_y, cursor_x) screen coordinates for the cursor, or (-1, -1).
        Total height consumed = 1 (label) + 1 (top border) + rows + 1 (bottom border).
    """
    inner_w = width - 2
    ba = curses.color_pair(C_BORDER)

    # Label
    la = curses.color_pair(C_CYAN) | curses.A_BOLD if active else curses.color_pair(C_DIM)
    _put(win, y, x, label, la)

    # Box border
    bc = curses.color_pair(C_CYAN) | curses.A_BOLD if active else ba
    _put(win, y + 1, x, BOX_TL + BOX_H * inner_w + BOX_TR, bc)

    # Break value into wrapped lines
    lines: list[str] = []
    for i in range(0, max(len(value), 1), inner_w):
        lines.append(value[i:i + inner_w])
    if not lines:
        lines = [""]

    # Scroll so the cursor line is visible
    cursor_line = max(0, cursor // inner_w) if cursor >= 0 else 0
    scroll_line = 0
    if cursor_line >= rows:
        scroll_line = cursor_line - rows + 1

    va = curses.A_NORMAL
    if active:
        va = curses.color_pair(C_WHITE) | curses.A_BOLD

    cur_y, cur_x = -1, -1
    for r in range(rows):
        line_idx = scroll_line + r
        ry = y + 2 + r
        _put(win, ry, x, BOX_V, bc)
        if line_idx < len(lines):
            _put(win, ry, x + 1, f"{lines[line_idx]:<{inner_w}}", va)
        else:
            _put(win, ry, x + 1, " " * inner_w, va)
        _put(win, ry, x + inner_w + 1, BOX_V, bc)

        # Compute cursor position
        if active and cursor >= 0 and line_idx == cursor_line:
            cur_x = x + 1 + (cursor - line_idx * inner_w)
            cur_y = ry

    _put(win, y + 2 + rows, x, BOX_BL + BOX_H * inner_w + BOX_BR, bc)
    return (cur_y, cur_x)


# ── Picklist dropdown ──────────────────────────────────────────────────────

def _show_picklist(parent_win, field_idx: int, current_value: str,
                   anchor_y: int, anchor_x: int) -> Optional[str]:
    """Show a scrollable picklist dropdown for a cron field.

    Renders as a bordered list anchored below the field box.
    Returns the selected preset value, or None if cancelled.
    """
    field_name = FIELD_NAMES[field_idx]
    presets = FIELD_PRESETS[field_name]
    labels = PRESET_LABELS[field_name]

    # Build display items: "value  — label"
    items: list[tuple[str, str]] = []
    for p in presets:
        lbl = labels.get(p, p)
        items.append((p, lbl))

    # Add "Custom..." option at the end
    items.append(("__custom__", "Custom value..."))

    # Dimensions
    max_label_len = max(len(lbl) for _, lbl in items)
    max_val_len = max(len(v) for v, _ in items if v != "__custom__")
    col_w = max_val_len + 3 + max_label_len + 2  # "value  — label" + padding
    list_w = min(col_w + 4, 44)  # border + padding
    list_h = min(len(items) + 2, 16)  # border top/bottom + items
    inner_h = list_h - 2
    inner_w = list_w - 4

    # Position: try below the anchor, fall back above if no room
    parent_h, parent_w = parent_win.getmaxyx()
    py, px = parent_win.getbegyx()

    drop_y = py + anchor_y
    drop_x = px + anchor_x

    # Clamp to screen
    screen_h = curses.LINES
    screen_w = curses.COLS
    if drop_y + list_h > screen_h:
        drop_y = max(0, py + anchor_y - list_h - 4)
    if drop_x + list_w > screen_w:
        drop_x = max(0, screen_w - list_w)

    try:
        win = curses.newwin(list_h, list_w, drop_y, drop_x)
    except curses.error:
        return None
    win.keypad(True)

    # Find initial selection matching current value
    selected = 0
    for i, (v, _) in enumerate(items):
        if v == current_value:
            selected = i
            break

    scroll = 0

    while True:
        win.erase()

        # Border
        bc = curses.color_pair(C_CYAN) | curses.A_BOLD
        try:
            win.attron(bc)
            win.box()
            win.attroff(bc)
        except curses.error:
            pass

        # Title
        title = f" {FIELD_LABELS[field_idx]} "
        _put(win, 0, 2, title, curses.color_pair(C_TITLE) | curses.A_BOLD)

        # Ensure selected item is visible
        if selected < scroll:
            scroll = selected
        if selected >= scroll + inner_h:
            scroll = selected - inner_h + 1

        # Draw items
        for i in range(inner_h):
            idx = scroll + i
            if idx >= len(items):
                break
            val, lbl = items[idx]
            y = 1 + i

            if idx == selected:
                attr = curses.color_pair(C_SELECTED) | curses.A_BOLD
                # Fill the row background
                _put(win, y, 1, " " * (list_w - 2), attr)
            else:
                attr = curses.A_NORMAL

            if val == "__custom__":
                _put(win, y, 2, f"  {lbl}", attr)
            else:
                # Show: "value — label"
                val_display = f"{val:<{max_val_len}}"
                entry = f"  {val_display}  {lbl}"
                _put(win, y, 2, entry[:inner_w], attr)

        # Scroll indicators
        if scroll > 0:
            _put(win, 1, list_w - 2, IND_ARROW_UP,
                 curses.color_pair(C_DIM))
        if scroll + inner_h < len(items):
            _put(win, list_h - 2, list_w - 2, IND_ARROW_DN,
                 curses.color_pair(C_DIM))

        win.refresh()

        try:
            key = win.getch()
        except curses.error:
            continue

        if key == 27:  # Escape
            return None
        elif key in (curses.KEY_ENTER, 10, 13, ord(" ")):
            val, _ = items[selected]
            if val == "__custom__":
                return "__custom__"
            return val
        elif key in (curses.KEY_UP, ord("k")):
            selected = max(0, selected - 1)
        elif key in (curses.KEY_DOWN, ord("j")):
            selected = min(len(items) - 1, selected + 1)
        elif key == curses.KEY_HOME or key == ord("g"):
            selected = 0
        elif key == curses.KEY_END or key == ord("G"):
            selected = len(items) - 1
        elif key == 9:  # Tab — select and move on
            val, _ = items[selected]
            if val == "__custom__":
                return "__custom__"
            return val


# ── Schedule form (shared by edit & new) ────────────────────────────────────

class _FormState:
    """State for the multi-field schedule + name + command form."""

    def __init__(self, fields: list[str], command: str, name: str):
        # Cron field values (5 entries)
        self.fields = list(fields)
        # Preset indices per field (-1 = custom value)
        self.preset_idx = [
            _find_preset_index(fields[i], FIELD_PRESETS[FIELD_NAMES[i]])
            for i in range(5)
        ]
        # Name (stored as crontab comment) + command
        self.name = name
        self.command = command
        # Cursor positions for text fields
        self.name_cursor = len(name)
        self.cmd_cursor = len(command)
        # Currently active form element (0-4 = cron fields, 5 = name, 6 = command)
        self.active = 0

    @property
    def schedule(self) -> str:
        return " ".join(self.fields)

    def validate_field(self, idx: int) -> bool:
        """Check if a single cron field is valid."""
        _, err = parse_field(self.fields[idx], FIELD_NAMES[idx])
        return err == ""

    def validate_all(self) -> tuple[bool, str]:
        """Validate the full schedule expression."""
        expr = parse_expression(self.schedule)
        return expr.validate()

    def describe(self) -> str:
        """Human-readable description."""
        expr = parse_expression(self.schedule)
        return expr.describe()

    def cycle_preset(self, direction: int) -> None:
        """Cycle the active cron field through its presets."""
        if self.active >= 5:
            return
        name = FIELD_NAMES[self.active]
        presets = FIELD_PRESETS[name]
        idx = self.preset_idx[self.active]
        if idx < 0:
            # Not on a preset — start from beginning
            idx = 0 if direction > 0 else len(presets) - 1
        else:
            idx = (idx + direction) % len(presets)
        self.preset_idx[self.active] = idx
        self.fields[self.active] = presets[idx]

    def type_char(self, ch: str) -> None:
        """Type a character into the active field."""
        if self.active < 5:
            # Cron field — replace entirely on first keystroke or append
            self.fields[self.active] += ch
            self.preset_idx[self.active] = -1  # Now custom
        elif self.active == NAME_FIELD:
            buf = list(self.name)
            buf.insert(self.name_cursor, ch)
            self.name = "".join(buf)
            self.name_cursor += 1
        elif self.active == CMD_FIELD:
            buf = list(self.command)
            buf.insert(self.cmd_cursor, ch)
            self.command = "".join(buf)
            self.cmd_cursor += 1

    def backspace(self) -> None:
        """Handle backspace in the active field."""
        if self.active < 5:
            if self.fields[self.active]:
                self.fields[self.active] = self.fields[self.active][:-1]
                self.preset_idx[self.active] = -1
        elif self.active == NAME_FIELD:
            if self.name_cursor > 0:
                buf = list(self.name)
                buf.pop(self.name_cursor - 1)
                self.name = "".join(buf)
                self.name_cursor -= 1
        elif self.active == CMD_FIELD:
            if self.cmd_cursor > 0:
                buf = list(self.command)
                buf.pop(self.cmd_cursor - 1)
                self.command = "".join(buf)
                self.cmd_cursor -= 1

    def clear_field(self) -> None:
        """Clear the active cron field (for quick re-entry)."""
        if self.active < 5:
            self.fields[self.active] = ""
            self.preset_idx[self.active] = -1

    def cursor_left(self) -> None:
        if self.active == NAME_FIELD:
            self.name_cursor = max(0, self.name_cursor - 1)
        elif self.active == CMD_FIELD:
            self.cmd_cursor = max(0, self.cmd_cursor - 1)

    def cursor_right(self) -> None:
        if self.active == NAME_FIELD:
            self.name_cursor = min(len(self.name), self.name_cursor + 1)
        elif self.active == CMD_FIELD:
            self.cmd_cursor = min(len(self.command), self.cmd_cursor + 1)

    def next_field(self) -> None:
        self.active = (self.active + 1) % FORM_FIELDS

    def prev_field(self) -> None:
        self.active = (self.active - 1) % FORM_FIELDS


def _run_form(win, form: _FormState, title: str,
              width: int, height: int,
              show_command: bool = True) -> bool:
    """Run the interactive form loop. Returns True if submitted, False if cancelled."""

    content_w = width - 6  # Padding inside modal

    while True:
        win.erase()
        _draw_modal_frame(win, title)

        # ── Cron field boxes ──

        # Calculate layout: 5 boxes with gaps
        box_w = FIELD_W + 2
        total_boxes_w = 5 * box_w + 4 * FIELD_GAP
        boxes_x = max(3, (width - total_boxes_w) // 2)
        fields_y = 2

        # Schedule label
        _put(win, fields_y, 3, "Schedule",
             curses.color_pair(C_TITLE) | curses.A_BOLD)
        fields_y += 1

        for i in range(5):
            fx = boxes_x + i * (box_w + FIELD_GAP)
            is_active = (form.active == i)
            is_valid = form.validate_field(i)
            _draw_field_box(win, fields_y, fx,
                            FIELD_LABELS[i], form.fields[i],
                            is_active, is_valid)

        # Picklist hint on active cron field (down arrow indicator)
        if form.active < 5:
            fx = boxes_x + form.active * (box_w + FIELD_GAP)
            arrow_attr = curses.color_pair(C_GREEN)
            _put(win, fields_y + 4, fx + box_w // 2, IND_ARROW_DN, arrow_attr)

        # ── Human-readable preview ──

        preview_y = fields_y + 5
        valid, err = form.validate_all()
        _put(win, preview_y, 3, " " * content_w, curses.A_NORMAL)
        if valid:
            desc = form.describe()
            _put(win, preview_y, 3, desc[:content_w],
                 curses.color_pair(C_GREEN))
        elif any(form.fields[i] for i in range(5)):
            _put(win, preview_y, 3, f"Invalid: {err}"[:content_w],
                 curses.color_pair(C_RED) | curses.A_DIM)

        # ── Raw expression line ──

        expr_y = preview_y + 1
        raw = form.schedule
        _put(win, expr_y, 3, f"Expression: {raw}"[:content_w],
             curses.color_pair(C_DIM) | curses.A_DIM)

        # ── Name field ──

        name_cur_pos = (-1, -1)
        cmd_cur_pos = (-1, -1)
        if show_command:
            name_y = expr_y + 2
            cursor = form.name_cursor if form.active == NAME_FIELD else -1
            name_cur_pos = _draw_text_field(
                win, name_y, 3, content_w, "Name",
                form.name, form.active == NAME_FIELD, cursor)

            # ── Command field (4 visible rows) ──
            # name field height: 1 label + 1 top + 1 row + 1 bottom = 4
            cmd_y = name_y + 4
            cursor = form.cmd_cursor if form.active == CMD_FIELD else -1
            cmd_cur_pos = _draw_text_field(
                win, cmd_y, 3, content_w, "Command",
                form.command, form.active == CMD_FIELD, cursor,
                rows=4)

        # ── Key hints ──

        hint_y = height - 2
        ha = curses.color_pair(C_DIM) | curses.A_DIM
        if form.active < 5:
            _put(win, hint_y, 3,
                 "Enter/Space: pick  "
                 + BOX_V + " Tab: next  "
                 + BOX_V + " Type: custom  "
                 + BOX_V + " Ctrl+S: apply  "
                 + BOX_V + " Esc: cancel",
                 ha)
        else:
            _put(win, hint_y, 3,
                 "Type value  "
                 + BOX_V + " Ctrl+V: paste  "
                 + BOX_V + " Tab: next  "
                 + BOX_V + " Enter/Ctrl+S: apply  "
                 + BOX_V + " Esc: cancel",
                 ha)

        # Position cursor for text fields
        if form.active >= 5:
            try:
                curses.curs_set(1)
                if form.active == NAME_FIELD and name_cur_pos[0] >= 0:
                    win.move(name_cur_pos[0], name_cur_pos[1])
                elif form.active == CMD_FIELD and cmd_cur_pos[0] >= 0:
                    win.move(cmd_cur_pos[0], cmd_cur_pos[1])
            except curses.error:
                pass
        else:
            try:
                curses.curs_set(0)
            except curses.error:
                pass

        win.refresh()

        # ── Input ──

        try:
            key = win.getch()
        except curses.error:
            continue

        if key == 27:  # Escape
            try:
                curses.curs_set(0)
            except curses.error:
                pass
            return False

        elif key == 19:  # Ctrl+S — submit from any field
            if not valid:
                _put(win, preview_y, 3, "Fix schedule errors first!",
                     curses.color_pair(C_RED) | curses.A_BOLD)
                win.refresh()
                curses.napms(800)
                continue
            if show_command and not form.command.strip():
                form.active = CMD_FIELD
                continue
            try:
                curses.curs_set(0)
            except curses.error:
                pass
            return True

        elif key in (curses.KEY_ENTER, 10, 13, ord(" ")) and form.active < 5:
            # Open picklist for cron field
            fx = boxes_x + form.active * (box_w + FIELD_GAP)
            pick = _show_picklist(win, form.active, form.fields[form.active],
                                  fields_y + 5, fx)
            if pick == "__custom__":
                # Enter custom value inline
                form.clear_field()
            elif pick is not None:
                form.fields[form.active] = pick
                form.preset_idx[form.active] = _find_preset_index(
                    pick, FIELD_PRESETS[FIELD_NAMES[form.active]])

        elif key in (curses.KEY_ENTER, 10, 13):
            # Submit (only reached when active field is name/command)
            if not valid:
                _put(win, preview_y, 3, "Fix schedule errors first!",
                     curses.color_pair(C_RED) | curses.A_BOLD)
                win.refresh()
                curses.napms(800)
                continue
            if show_command and not form.command.strip():
                form.active = CMD_FIELD
                _put(win, cmd_y, 3 + len("Command") + 1,
                     " Command is required",
                     curses.color_pair(C_RED) | curses.A_BOLD)
                win.refresh()
                curses.napms(800)
                continue
            try:
                curses.curs_set(0)
            except curses.error:
                pass
            return True

        elif key == 9:  # Tab
            form.next_field()
            # Skip name/command if not shown
            if not show_command and form.active >= NAME_FIELD:
                form.active = 0

        elif key == curses.KEY_BTAB:  # Shift+Tab
            form.prev_field()
            if not show_command and form.active >= NAME_FIELD:
                form.active = 4

        elif key in (curses.KEY_UP, curses.KEY_DOWN):
            if form.active < 5:
                # Open picklist for cron field
                fx = boxes_x + form.active * (box_w + FIELD_GAP)
                pick = _show_picklist(win, form.active,
                                      form.fields[form.active],
                                      fields_y + 5, fx)
                if pick == "__custom__":
                    form.clear_field()
                elif pick is not None:
                    form.fields[form.active] = pick
                    form.preset_idx[form.active] = _find_preset_index(
                        pick, FIELD_PRESETS[FIELD_NAMES[form.active]])

        elif key == curses.KEY_LEFT:
            if form.active < 5:
                form.prev_field()
                if form.active >= NAME_FIELD:
                    form.active = 4
            else:
                form.cursor_left()

        elif key == curses.KEY_RIGHT:
            if form.active < 5:
                form.next_field()
                if not show_command and form.active >= NAME_FIELD:
                    form.active = 0
            else:
                form.cursor_right()

        elif key in (curses.KEY_BACKSPACE, 127, 8):
            form.backspace()

        elif key == curses.KEY_DC:
            # Delete key — clear cron field, or delete-forward in text
            if form.active < 5:
                form.clear_field()

        elif key == 22:  # Ctrl+V — paste from clipboard
            clip = _clipboard_paste()
            if clip and show_command:
                # Always paste into command field
                if form.active < CMD_FIELD:
                    form.active = CMD_FIELD
                for ch in clip:
                    if 32 <= ord(ch) <= 126:
                        form.type_char(ch)

        elif 32 <= key <= 126:
            ch = chr(key)
            # Detect paste burst: drain all immediately-available chars
            pasted = _drain_paste(win, ch)
            if len(pasted) > 1 and show_command:
                # Multi-char burst = paste — redirect to command field
                if form.active < CMD_FIELD:
                    form.active = CMD_FIELD
                for c in pasted:
                    form.type_char(c)
            else:
                form.type_char(ch)


# ── Public modals ───────────────────────────────────────────────────────────

def show_edit_modal(scr, schedule: str, command: str,
                    comment: str = "") -> Optional[dict]:
    """Edit modal with integrated 5-field schedule builder.

    Returns dict with 'schedule', 'command', 'comment' or None if cancelled.
    """
    width = min(100, curses.COLS - 4)
    height = 29
    win = _center_win(scr, height, width)
    if not win:
        return None

    # Parse existing schedule into 5 fields
    parts = schedule.strip().split()
    while len(parts) < 5:
        parts.append("*")

    form = _FormState(parts[:5], command, comment)

    ok = _run_form(win, form, "Edit Job", width, height)
    if ok:
        return {
            "schedule": form.schedule,
            "command": form.command.strip(),
            "comment": form.name.strip(),
        }
    return None


def show_new_job_modal(scr) -> Optional[dict]:
    """New job wizard with integrated 5-field schedule builder.

    Returns dict with 'schedule', 'command', 'comment' or None if cancelled.
    """
    width = min(100, curses.COLS - 4)
    height = 29
    win = _center_win(scr, height, width)
    if not win:
        return None

    # Start with sensible defaults (every hour at :00)
    form = _FormState(["0", "*", "*", "*", "*"], "", "")

    ok = _run_form(win, form, "New Job", width, height)
    if ok:
        return {
            "schedule": form.schedule,
            "command": form.command.strip(),
            "comment": form.name.strip(),
        }
    return None


def show_search_modal(scr, current_filter: str = "") -> Optional[str]:
    """Search/filter overlay. Returns filter text or None if cancelled."""
    width = min(60, curses.COLS - 4)
    height = 5
    win = _center_win(scr, height, width)
    if not win:
        return None

    _draw_modal_frame(win, "Search / Filter")

    ha = curses.color_pair(C_DIM) | curses.A_DIM
    _put(win, 3, 2, "Enter: apply  Esc: cancel/clear", ha)
    win.refresh()

    result = _text_input(win, 2, 2, width - 4, initial=current_filter,
                         prompt="Filter: ")
    return result


def show_help_modal(scr) -> None:
    """Display help overlay with keybindings."""
    width = min(60, curses.COLS - 4)
    height = 22
    win = _center_win(scr, height, width)
    if not win:
        return

    _draw_modal_frame(win, "Help \u2014 Keybindings")

    la = curses.color_pair(C_CYAN) | curses.A_BOLD
    va = curses.A_NORMAL
    ha = curses.color_pair(C_DIM) | curses.A_DIM

    bindings = [
        ("j / Down", "Navigate down"),
        ("k / Up", "Navigate up"),
        ("Space", "Toggle enable/disable"),
        ("e", "Edit selected job"),
        ("n", "New job wizard"),
        ("d", "Delete (press again to confirm)"),
        ("R", "Run Now (Shift+R, execute immediately)"),
        ("s", "Save changes to crontab"),
        ("u", "Undo last action"),
        ("Ctrl+R", "Redo"),
        ("/", "Search/filter jobs"),
        ("b", "Visual cron builder"),
        ("Tab", "Cycle panel focus"),
        ("?", "This help screen"),
        ("q", "Quit (prompts if dirty)"),
    ]

    for i, (key, desc) in enumerate(bindings):
        y = 2 + i
        if y >= height - 2:
            break
        _put(win, y, 3, f"{key:>10s}", la)
        _put(win, y, 15, desc, va)

    _put(win, height - 2, 2, "Press any key to close", ha)
    win.refresh()
    win.getch()


def show_quit_confirm(scr) -> bool:
    """Dirty-quit confirmation. Returns True to quit, False to cancel."""
    width = min(50, curses.COLS - 4)
    height = 7
    win = _center_win(scr, height, width)
    if not win:
        return False

    _draw_modal_frame(win, "Unsaved Changes")

    _put(win, 2, 3, "You have unsaved changes.",
         curses.color_pair(C_YELLOW) | curses.A_BOLD)
    _put(win, 4, 3, "q: Quit without saving", curses.A_NORMAL)
    _put(win, 5, 3, "s: Save and quit       Esc: Cancel",
         curses.A_NORMAL)
    win.refresh()

    while True:
        try:
            key = win.getch()
        except curses.error:
            continue
        if key == ord("q"):
            return True
        elif key == ord("s"):
            return True  # Caller should save first
        elif key == 27:  # Escape
            return False


def show_run_output_modal(scr, command: str, output: str,
                          exit_code: int) -> None:
    """Show output from a Run Now command."""
    width = min(76, curses.COLS - 4)
    lines = output.split("\n")
    height = min(len(lines) + 6, curses.LINES - 4)
    height = max(height, 8)
    win = _center_win(scr, height, width)
    if not win:
        return

    _draw_modal_frame(win, "Run Now \u2014 Output")

    la = curses.color_pair(C_CYAN) | curses.A_BOLD
    _put(win, 2, 2, f"$ {command}"[:width - 4], la)

    if exit_code == 0:
        ec_attr = curses.color_pair(C_GREEN)
    else:
        ec_attr = curses.color_pair(C_RED)
    _put(win, 3, 2, f"Exit code: {exit_code}", ec_attr)

    for i, line in enumerate(lines[:height - 6]):
        _put(win, 4 + i, 2, line[:width - 4], curses.A_NORMAL)

    _put(win, height - 2, 2, "Press any key to close",
         curses.color_pair(C_DIM) | curses.A_DIM)
    win.refresh()
    win.getch()


def show_log_modal(scr, entries) -> None:
    """Show action log in a scrollable modal with success/failure indicators."""
    from lazycron.ui.theme import IND_SUCCESS, IND_FAILURE

    width = min(100, curses.COLS - 4)
    height = min(curses.LINES - 4, 30)
    win = _center_win(scr, height, width)
    if not win:
        return

    _draw_modal_frame(win, "Activity Log")

    if not entries:
        _put(win, 2, 2, "No activity yet.",
             curses.color_pair(C_DIM) | curses.A_DIM)
        _put(win, height - 2, 2, "Press any key to close",
             curses.color_pair(C_DIM) | curses.A_DIM)
        win.refresh()
        win.getch()
        return

    avail_h = height - 4
    avail_w = width - 4
    scroll = max(0, len(entries) - avail_h)

    while True:
        for i in range(avail_h):
            idx = scroll + i
            y = 2 + i
            if idx < len(entries):
                entry = entries[idx]
                if entry.success is True:
                    ind = IND_SUCCESS
                    attr = curses.color_pair(C_GREEN)
                elif entry.success is False:
                    ind = IND_FAILURE
                    attr = curses.color_pair(C_RED)
                else:
                    ind = "·"
                    attr = curses.color_pair(C_DIM)
                line = f"{entry.time_str}  {ind}  {entry.message}"
                _put(win, y, 2, " " * avail_w, curses.A_NORMAL)
                _put(win, y, 2, line[:avail_w], attr)
            else:
                _put(win, y, 2, " " * avail_w, curses.A_NORMAL)

        pos = f" {scroll + 1}-{min(scroll + avail_h, len(entries))}/{len(entries)} "
        _put(win, height - 2, 2, "j/k:scroll  q:close",
             curses.color_pair(C_DIM))
        _put(win, height - 2, width - len(pos) - 2, pos,
             curses.color_pair(C_DIM))
        win.refresh()

        try:
            key = win.getch()
        except curses.error:
            continue

        if key in (ord("q"), 27):
            break
        elif key in (ord("j"), curses.KEY_DOWN):
            scroll = min(scroll + 1, max(0, len(entries) - avail_h))
        elif key in (ord("k"), curses.KEY_UP):
            scroll = max(0, scroll - 1)
        elif key == ord("G"):
            scroll = max(0, len(entries) - avail_h)
        elif key == ord("g"):
            scroll = 0


# ── Simple text input (used by search) ──────────────────────────────────────

def _text_input(win, y: int, x: int, width: int,
                initial: str = "", prompt: str = "") -> Optional[str]:
    """Single-line text input field. Returns text or None on Escape."""
    buf = list(initial)
    cursor = len(buf)

    while True:
        _put(win, y, x, " " * width, curses.A_NORMAL)
        if prompt:
            _put(win, y, x, prompt, curses.color_pair(C_CYAN))

        px = x + len(prompt)
        text = "".join(buf)
        avail = width - len(prompt) - 1
        scroll = max(0, cursor - avail + 1)
        visible = text[scroll:scroll + avail]
        _put(win, y, px, visible, curses.A_NORMAL)

        cursor_x = px + cursor - scroll
        if 0 <= cursor_x < x + width:
            try:
                curses.curs_set(1)
                win.move(y, cursor_x)
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
            return "".join(buf)
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            if cursor > 0:
                buf.pop(cursor - 1)
                cursor -= 1
        elif key == curses.KEY_DC:
            if cursor < len(buf):
                buf.pop(cursor)
        elif key == curses.KEY_LEFT:
            cursor = max(0, cursor - 1)
        elif key == curses.KEY_RIGHT:
            cursor = min(len(buf), cursor + 1)
        elif key == curses.KEY_HOME:
            cursor = 0
        elif key == curses.KEY_END:
            cursor = len(buf)
        elif key == 22:  # Ctrl+V — paste from clipboard
            clip = _clipboard_paste()
            for ch in clip:
                if 32 <= ord(ch) <= 126:
                    buf.insert(cursor, ch)
                    cursor += 1
        elif 32 <= key <= 126:
            # Drain paste burst for speed
            pasted = _drain_paste(win, chr(key))
            for ch in pasted:
                buf.insert(cursor, ch)
                cursor += 1
