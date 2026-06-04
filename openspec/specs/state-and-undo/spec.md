# State Management and Undo/Redo Specification

## Status

Current state: `implemented` for central Store, Action dispatch, undo/redo (50 levels), dirty detection, search/filter, and action log persistence. All features are tested in `test_state.py` (40+ tests).

## Requirements

### Requirement: Central state is managed through a Store with action dispatch

All state mutations SHALL flow through `Store.dispatch()` with an `Action` enum to maintain undo history and logging.

Evidence:
- `lazycron/state.py:23-34` — `Action` enum defines 10 action types (TOGGLE, DELETE, UPDATE, CREATE, SAVE, SELECT_NEXT, SELECT_PREV, SELECT_INDEX, FOCUS_NEXT, SET_FILTER).
- `lazycron/state.py:65-80` — `Store.__init__()` initializes crontab, selection, undo/redo stacks, action log, filter, panel focus, delete-pending timer, and transient message state.
- `lazycron/state.py:122-143` — `dispatch()` routes each action to its handler method.
- `lazycron/state.py:145-250` — Handler methods (`_do_toggle`, `_do_delete`, `_do_update`, etc.) each call `_push_undo()` before mutating.

### Requirement: Undo/redo supports up to 50 levels

The system SHALL support undo and redo of at least 50 previous states, deep-copying the entire crontab on each mutation.

Evidence:
- `lazycron/state.py:50-58` — `MAX_UNDO = 50` constant, `Snapshot` dataclass captures crontab, selection, and action log length.
- `lazycron/state.py:100-111` — `_snapshot()` creates a deep copy, `_push_undo()` adds to stack and clears redo.
- `lazycron/state.py:252-281` — `undo()` saves current state to redo stack, restores snapshot. `redo()` does the inverse.
- `tests/test_state.py:114-151` — `TestUndoRedo` tests undo toggle, redo, empty stacks, and new action clearing redo.

### Requirement: Dirty detection tracks unsaved changes

The store SHALL track whether the crontab has unsaved modifications and display a dirty indicator.

Evidence:
- `lazycron/state.py:77` — `self.dirty` flag set to `True` on TOGGLE, DELETE, UPDATE, CREATE actions.
- `lazycron/state.py:222` — `_do_save()` sets `self.dirty = False` on success.
- `lazycron/state.py:263` — `undo()` recalculates dirty from `crontab.has_modifications()`.
- `lazycron/ui/statusbar.py:28-29` — Shows `◆ unsaved changes` indicator when dirty.

### Requirement: Search/filter is case-insensitive substring matching

The system SHALL filter the jobs list by matching filter text against job command, display name, and raw schedule.

Evidence:
- `lazycron/state.py:83-90` — `Store.jobs` property filters if `filter_text` is set, checking lowercase match against command, display_name, and schedule raw.
- `lazycron/state.py:248-250` — `_do_set_filter()` updates filter and resets selection to 0.
- `tests/test_state.py:154-181` — `TestFilter` tests narrowing, case insensitivity, clearing, no match, and selection reset.

### Requirement: Action log persists to disk

All actions SHALL be logged both in-memory and persisted to `~/.lazycron/history.jsonl`, limited to 200 recent entries.

Evidence:
- `lazycron/state.py:60-62` — `LOG_DIR`, `LOG_FILE`, `MAX_LOG_ENTRIES = 200`.
- `lazycron/state.py:284-333` — `_persist_entry()` appends JSON line to file; `_load_log()` reads back, truncates to 200 on overflow.
- `lazycron/state.py:113-116` — `_log()` appends `LogEntry` to in-memory list and persists.

### Requirement: Save serializes a deep copy before writing

The save operation SHALL deep-copy the crontab, wrap commands in the copy, serialize to the system, and only apply changes on success.

Evidence:
- `lazycron/state.py:209-225` — `_do_save()` creates `copy.deepcopy(self.crontab)` as `staged`, wraps commands on `staged`, calls `save_system_crontab(staged)`, and only sets `self.crontab = staged` on success.

## Non-Requirements

- The store does not support multi-user state or remote synchronization.
- The undo system does not persist across restarts — the undo stack is in-memory only.
- The action log is append-only; there is no compaction or pruning beyond the 200-entry cap.
