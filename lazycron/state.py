"""Central state management with undo/redo and dirty detection.

All mutations flow through Store.dispatch() to maintain undo history
and action logging.
"""

from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional

from lazycron.crontab import (
    CrontabFile, Job, add_job, delete_job, toggle_job, update_job,
)


class Action(Enum):
    """Actions that can be dispatched to the store."""
    TOGGLE = auto()
    DELETE = auto()
    UPDATE = auto()
    CREATE = auto()
    SAVE = auto()
    SELECT_NEXT = auto()
    SELECT_PREV = auto()
    SELECT_INDEX = auto()
    FOCUS_NEXT = auto()
    SET_FILTER = auto()


@dataclass
class LogEntry:
    """Entry in the command log."""
    timestamp: float
    message: str

    @property
    def time_str(self) -> str:
        t = time.localtime(self.timestamp)
        return f"{t.tm_hour:02d}:{t.tm_min:02d}:{t.tm_sec:02d}"


@dataclass
class Snapshot:
    """State snapshot for undo/redo."""
    crontab: CrontabFile
    selected: int
    action_log_len: int


MAX_UNDO = 50
PANEL_COUNT = 5


class Store:
    """Central application state."""

    def __init__(self, crontab: CrontabFile):
        self.crontab: CrontabFile = crontab
        self.original: CrontabFile = copy.deepcopy(crontab)
        self.selected: int = 0
        self.dirty: bool = False
        self.undo_stack: list[Snapshot] = []
        self.redo_stack: list[Snapshot] = []
        self.action_log: list[LogEntry] = []
        self.filter_text: str = ""
        self.focused_panel: int = 0  # 0=jobs, 1=detail, 2=history, 3=env, 4=cmdlog
        self.delete_pending: Optional[float] = None  # Timestamp of first 'd' press
        self.message: str = ""  # Transient status message
        self.message_time: float = 0.0

    @property
    def jobs(self) -> list[Job]:
        """Return jobs, filtered if a filter is active."""
        if not self.filter_text:
            return self.crontab.jobs
        ft = self.filter_text.lower()
        return [j for j in self.crontab.jobs
                if ft in j.command.lower() or ft in j.display_name.lower()
                or ft in j.schedule.raw.lower()]

    @property
    def selected_job(self) -> Optional[Job]:
        """Return the currently selected job, or None."""
        jobs = self.jobs
        if not jobs or self.selected < 0 or self.selected >= len(jobs):
            return None
        return jobs[self.selected]

    def _snapshot(self) -> Snapshot:
        return Snapshot(
            crontab=copy.deepcopy(self.crontab),
            selected=self.selected,
            action_log_len=len(self.action_log),
        )

    def _push_undo(self) -> None:
        self.undo_stack.append(self._snapshot())
        if len(self.undo_stack) > MAX_UNDO:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def _log(self, msg: str) -> None:
        self.action_log.append(LogEntry(timestamp=time.time(), message=msg))

    def _set_message(self, msg: str) -> None:
        self.message = msg
        self.message_time = time.time()

    def dispatch(self, action: Action, **kwargs: Any) -> None:
        """Dispatch an action to mutate state."""
        if action == Action.TOGGLE:
            self._do_toggle()
        elif action == Action.DELETE:
            self._do_delete()
        elif action == Action.UPDATE:
            self._do_update(**kwargs)
        elif action == Action.CREATE:
            self._do_create(**kwargs)
        elif action == Action.SAVE:
            self._do_save()
        elif action == Action.SELECT_NEXT:
            self._do_select_next()
        elif action == Action.SELECT_PREV:
            self._do_select_prev()
        elif action == Action.SELECT_INDEX:
            self._do_select_index(**kwargs)
        elif action == Action.FOCUS_NEXT:
            self._do_focus_next()
        elif action == Action.SET_FILTER:
            self._do_set_filter(**kwargs)

    def _do_toggle(self) -> None:
        job = self.selected_job
        if not job:
            return
        self._push_undo()
        was_enabled = job.enabled
        toggle_job(self.crontab, job)
        self.dirty = True
        action = "disabled" if was_enabled else "enabled"
        self._log(f"Job {action}: {job.display_name}")
        self._set_message(f"Job {action}")

    def _do_delete(self) -> None:
        job = self.selected_job
        if not job:
            return

        now = time.time()
        if self.delete_pending and (now - self.delete_pending) < 3.0:
            # Confirmed delete
            self._push_undo()
            name = job.display_name
            delete_job(self.crontab, job)
            self.dirty = True
            self.delete_pending = None
            # Adjust selection
            if self.selected >= len(self.jobs):
                self.selected = max(0, len(self.jobs) - 1)
            self._log(f"Job deleted: {name}")
            self._set_message(f"Deleted {name}")
        else:
            # First press — set pending
            self.delete_pending = now
            self._set_message("Press d again to confirm delete")

    def _do_update(self, **kwargs: Any) -> None:
        job = self.selected_job
        if not job:
            return
        schedule = kwargs.get("schedule", job.schedule.raw)
        command = kwargs.get("command", job.command)
        comment = kwargs.get("comment", job.comment)

        self._push_undo()
        update_job(self.crontab, job, schedule, command, comment)
        self.dirty = True
        self._log(f"Job updated: {job.display_name}")
        self._set_message("Job updated")

    def _do_create(self, **kwargs: Any) -> None:
        schedule = kwargs.get("schedule", "* * * * *")
        command = kwargs.get("command", "")
        comment = kwargs.get("comment", "")

        if not command:
            return

        self._push_undo()
        job = add_job(self.crontab, schedule, command, comment)
        self.dirty = True
        self.selected = len(self.jobs) - 1
        self._log(f"Job created: {job.display_name}")
        self._set_message("New job created")

    def _do_save(self) -> None:
        from lazycron.crontab import save_system_crontab
        err = save_system_crontab(self.crontab)
        if err:
            self._log(f"Save FAILED: {err}")
            self._set_message(f"Save failed: {err}")
        else:
            self.dirty = False
            self.original = copy.deepcopy(self.crontab)
            self._log("Crontab saved")
            self._set_message("Saved to crontab")

    def _do_select_next(self) -> None:
        jobs = self.jobs
        if jobs and self.selected < len(jobs) - 1:
            self.selected += 1
        self.delete_pending = None

    def _do_select_prev(self) -> None:
        if self.selected > 0:
            self.selected -= 1
        self.delete_pending = None

    def _do_select_index(self, **kwargs: Any) -> None:
        idx = kwargs.get("index", 0)
        jobs = self.jobs
        if jobs:
            self.selected = max(0, min(idx, len(jobs) - 1))
        self.delete_pending = None

    def _do_focus_next(self) -> None:
        self.focused_panel = (self.focused_panel + 1) % PANEL_COUNT

    def _do_set_filter(self, **kwargs: Any) -> None:
        self.filter_text = kwargs.get("text", "")
        self.selected = 0

    def undo(self) -> bool:
        """Undo the last action. Returns True if successful."""
        if not self.undo_stack:
            self._set_message("Nothing to undo")
            return False
        # Save current state for redo
        self.redo_stack.append(self._snapshot())
        snap = self.undo_stack.pop()
        self.crontab = snap.crontab
        self.selected = snap.selected
        self.action_log = self.action_log[:snap.action_log_len]
        self.dirty = self.crontab.has_modifications()
        self._log("Undo")
        self._set_message("Undone")
        return True

    def redo(self) -> bool:
        """Redo the last undone action. Returns True if successful."""
        if not self.redo_stack:
            self._set_message("Nothing to redo")
            return False
        self.undo_stack.append(self._snapshot())
        snap = self.redo_stack.pop()
        self.crontab = snap.crontab
        self.selected = snap.selected
        # Restore action log length
        self.dirty = self.crontab.has_modifications()
        self._log("Redo")
        self._set_message("Redone")
        return True
