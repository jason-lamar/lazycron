"""Main curses application loop for LazyCron.

Follows the monitor pattern: poll keys -> process input -> update state -> render -> refresh.
Non-blocking input with timeout for responsive UI.
"""

from __future__ import annotations

import curses
import sys
import time

from lazycron.crontab import load_system_crontab
from lazycron.executor import run_command
from lazycron.state import Action, Store
from lazycron.wrapper import ensure_wrapper
from lazycron.ui.layout import compute_geometry, draw_borders, _put, PanelGeometry
from lazycron.ui.modals import (
    show_edit_modal, show_help_modal,
    show_new_job_modal, show_quit_confirm, show_run_output_modal,
    show_search_modal,
)
from lazycron.ui.cronbuilder import show_cron_builder
from lazycron.ui.panels import (
    draw_detail_panel, draw_jobs_panel, draw_log_panel,
)
from lazycron.ui.splash import show_splash
from lazycron.ui.statusbar import draw_statusbar
from lazycron.ui.theme import C_DIM, C_RED, MIN_H, MIN_W, init_colors

POLL_MS = 100


def _run(scr) -> None:
    """Main curses loop."""
    curses.curs_set(0)
    scr.nodelay(True)
    scr.timeout(POLL_MS)
    init_colors()
    show_splash(scr)

    # Ensure wrapper script exists
    ensure_wrapper()

    # Load crontab
    ct, err = load_system_crontab()
    if ct is None:
        _show_error(scr, f"Failed to load crontab: {err}")
        return

    store = Store(ct)

    while True:
        # -- Input -----------------------------------------------------------
        try:
            key = scr.getch()
        except curses.error:
            key = -1

        if key != -1:
            handled = _handle_key(scr, key, store)
            if handled == "quit":
                break
            elif handled == "redraw":
                scr.clear()

        # -- Render ----------------------------------------------------------
        try:
            my, mx = scr.getmaxyx()
            if my < MIN_H or mx < MIN_W:
                scr.erase()
                _put(scr, 0, 0, "Terminal too small.",
                     curses.A_BOLD)
                _put(scr, 1, 0, f"Need {MIN_W}x{MIN_H}, have {mx}x{my}",
                     curses.color_pair(C_DIM))
                scr.refresh()
                continue

            geo = compute_geometry(my, mx)

            # Clear content areas (not borders)
            _clear_panels(scr, geo)

            # Draw borders and panel titles
            draw_borders(scr, geo, store.focused_panel)

            # Draw panel contents
            draw_jobs_panel(scr, geo, store)
            draw_detail_panel(scr, geo, store)
            draw_log_panel(scr, geo, store)
            draw_statusbar(scr, store)

            scr.refresh()

        except curses.error:
            try:
                scr.clear()
            except curses.error:
                pass


def _clear_panels(scr, geo: PanelGeometry) -> None:
    """Clear the content areas of all panels."""
    my, mx = scr.getmaxyx()
    for y in range(my):
        try:
            scr.move(y, 0)
            scr.clrtoeol()
        except curses.error:
            pass


def _handle_key(scr, key: int, store: Store) -> str | None:
    """Process a keypress. Returns 'quit', 'redraw', or None."""

    # -- Navigation --
    if key in (ord("j"), curses.KEY_DOWN):
        store.dispatch(Action.SELECT_NEXT)
    elif key in (ord("k"), curses.KEY_UP):
        store.dispatch(Action.SELECT_PREV)
    elif key == 9:  # Tab
        store.dispatch(Action.FOCUS_NEXT)

    # -- Job actions --
    elif key == ord(" "):
        store.dispatch(Action.TOGGLE)
    elif key == ord("d"):
        store.dispatch(Action.DELETE)
    elif key == ord("s"):
        store.dispatch(Action.SAVE)
    elif key == ord("u"):
        store.undo()
    elif key == 18:  # Ctrl+R
        store.redo()

    # -- Modals --
    elif key == ord("e"):
        _handle_edit(scr, store)
        return "redraw"
    elif key == ord("n"):
        _handle_new(scr, store)
        return "redraw"
    elif key == ord("b"):
        _handle_builder(scr, store)
        return "redraw"
    elif key == ord("/"):
        _handle_search(scr, store)
        return "redraw"
    elif key == ord("R"):  # Shift+R = run now
        _handle_run_now(scr, store)
        return "redraw"
    elif key == ord("?"):
        show_help_modal(scr)
        return "redraw"

    # -- Quit --
    elif key in (ord("q"), ord("Q")):
        if store.dirty:
            if show_quit_confirm(scr):
                return "quit"
            return "redraw"
        return "quit"

    # -- Resize --
    elif key == curses.KEY_RESIZE:
        return "redraw"

    return None


def _handle_edit(scr, store: Store) -> None:
    """Open the edit modal for the selected job."""
    job = store.selected_job
    if not job:
        return

    result = show_edit_modal(
        scr,
        schedule=job.schedule.raw,
        command=job.display_cmd,
        comment=job.comment,
    )
    if result:
        store.dispatch(Action.UPDATE, **result)


def _handle_new(scr, store: Store) -> None:
    """Open the new job wizard."""
    result = show_new_job_modal(scr)
    if result:
        store.dispatch(Action.CREATE, **result)


def _handle_builder(scr, store: Store) -> None:
    """Open the visual cron builder for the selected job."""
    job = store.selected_job
    initial = job.schedule.raw if job else "* * * * *"
    command = job.display_cmd if job else ""

    result = show_cron_builder(scr, initial=initial, command=command)
    if result and job:
        store.dispatch(Action.UPDATE, schedule=result)
    elif result and not job:
        # If no job selected, create a new one with the built schedule
        store._set_message(f"Schedule: {result} (use 'n' to create job)")


def _handle_search(scr, store: Store) -> None:
    """Open the search/filter overlay."""
    result = show_search_modal(scr, current_filter=store.filter_text)
    if result is not None:
        store.dispatch(Action.SET_FILTER, text=result)
    elif result is None and store.filter_text:
        # Escape clears filter
        store.dispatch(Action.SET_FILTER, text="")


def _handle_run_now(scr, store: Store) -> None:
    """Execute the selected job's command immediately."""
    job = store.selected_job
    if not job:
        return

    store._log(f"Running: {job.display_name}")
    store._set_message(f"Running {job.display_name}...")

    # Force screen refresh so the user sees "Running..." before we block
    my, mx = scr.getmaxyx()
    geo = compute_geometry(my, mx)
    _clear_panels(scr, geo)
    draw_borders(scr, geo, store.focused_panel)
    draw_jobs_panel(scr, geo, store)
    draw_detail_panel(scr, geo, store)
    draw_log_panel(scr, geo, store)
    draw_statusbar(scr, store)
    scr.refresh()

    # Build env vars from crontab
    env = {ev.key: ev.value for ev in store.crontab.env_vars}

    result = run_command(job.command, env_vars=env)
    ok = result.exit_code == 0
    if result.timed_out:
        msg = f"{job.display_name} — timed out"
    elif ok:
        msg = f"{job.display_name} — success"
    else:
        msg = f"{job.display_name} — failed (exit {result.exit_code})"
    store._log(msg, success=ok)

    show_run_output_modal(scr, job.display_cmd, result.output, result.exit_code)



def _show_error(scr, message: str) -> None:
    """Show an error message and wait for keypress."""
    scr.clear()
    _put(scr, 0, 0, "Error", curses.color_pair(C_RED) | curses.A_BOLD)
    _put(scr, 2, 0, message, curses.A_NORMAL)
    _put(scr, 4, 0, "Press any key to exit.",
         curses.color_pair(C_DIM) | curses.A_DIM)
    scr.refresh()
    scr.nodelay(False)
    scr.getch()


def main() -> None:
    """Entry point."""
    try:
        curses.wrapper(_run)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        # Ensure terminal is restored before printing error
        print(f"LazyCron error: {e}", file=sys.stderr)
        sys.exit(1)
