"""Tests for state management: dispatch, undo/redo, dirty detection."""

import unittest

from lazycron.crontab import parse
from lazycron.state import Action, Store


SAMPLE = """SHELL=/bin/bash

*/15 * * * * /scripts/job1.sh
0 9 * * * /scripts/job2.sh
0 0 * * 0 /scripts/weekly.sh
"""


class TestStore(unittest.TestCase):
    """Test Store state management."""

    def setUp(self):
        ct = parse(SAMPLE)
        self.store = Store(ct)

    def test_initial_state(self):
        self.assertEqual(self.store.selected, 0)
        self.assertFalse(self.store.dirty)
        self.assertEqual(len(self.store.undo_stack), 0)
        self.assertEqual(len(self.store.action_log), 0)

    def test_select_next(self):
        self.store.dispatch(Action.SELECT_NEXT)
        self.assertEqual(self.store.selected, 1)

    def test_select_prev(self):
        self.store.dispatch(Action.SELECT_NEXT)
        self.store.dispatch(Action.SELECT_PREV)
        self.assertEqual(self.store.selected, 0)

    def test_select_prev_at_zero(self):
        self.store.dispatch(Action.SELECT_PREV)
        self.assertEqual(self.store.selected, 0)

    def test_select_next_at_end(self):
        for _ in range(10):
            self.store.dispatch(Action.SELECT_NEXT)
        self.assertEqual(self.store.selected, len(self.store.jobs) - 1)

    def test_select_index(self):
        self.store.dispatch(Action.SELECT_INDEX, index=2)
        self.assertEqual(self.store.selected, 2)

    def test_focus_next(self):
        self.store.dispatch(Action.FOCUS_NEXT)
        self.assertEqual(self.store.focused_panel, 1)
        self.store.dispatch(Action.FOCUS_NEXT)
        self.assertEqual(self.store.focused_panel, 2)

    def test_focus_wraps(self):
        for _ in range(5):
            self.store.dispatch(Action.FOCUS_NEXT)
        self.assertEqual(self.store.focused_panel, 0)


class TestToggle(unittest.TestCase):
    """Test toggle action."""

    def setUp(self):
        ct = parse(SAMPLE)
        self.store = Store(ct)

    def test_toggle_marks_dirty(self):
        self.store.dispatch(Action.TOGGLE)
        self.assertTrue(self.store.dirty)

    def test_toggle_creates_undo(self):
        self.store.dispatch(Action.TOGGLE)
        self.assertEqual(len(self.store.undo_stack), 1)

    def test_toggle_logs_action(self):
        self.store.dispatch(Action.TOGGLE)
        self.assertTrue(any("disabled" in e.message or "enabled" in e.message
                            for e in self.store.action_log))


class TestDelete(unittest.TestCase):
    """Test delete action (two-press confirm)."""

    def setUp(self):
        ct = parse(SAMPLE)
        self.store = Store(ct)

    def test_single_delete_pending(self):
        initial = len(self.store.jobs)
        self.store.dispatch(Action.DELETE)
        # First press just sets pending
        self.assertEqual(len(self.store.jobs), initial)
        self.assertIsNotNone(self.store.delete_pending)

    def test_double_delete_confirms(self):
        initial = len(self.store.jobs)
        self.store.dispatch(Action.DELETE)
        self.store.dispatch(Action.DELETE)
        self.assertEqual(len(self.store.jobs), initial - 1)
        self.assertTrue(self.store.dirty)


class TestUndoRedo(unittest.TestCase):
    """Test undo/redo functionality."""

    def setUp(self):
        ct = parse(SAMPLE)
        self.store = Store(ct)

    def test_undo_toggle(self):
        job = self.store.selected_job
        was_enabled = job.enabled
        self.store.dispatch(Action.TOGGLE)
        self.assertNotEqual(job.enabled, was_enabled)
        self.store.undo()
        # After undo, the job should be back to original state
        # (note: undo restores a deep copy, so we need to re-fetch)
        job_after = self.store.selected_job
        self.assertEqual(job_after.enabled, was_enabled)

    def test_redo(self):
        self.store.dispatch(Action.TOGGLE)
        self.store.undo()
        self.store.redo()
        self.assertTrue(self.store.dirty)

    def test_undo_empty_stack(self):
        result = self.store.undo()
        self.assertFalse(result)

    def test_redo_empty_stack(self):
        result = self.store.redo()
        self.assertFalse(result)

    def test_new_action_clears_redo(self):
        self.store.dispatch(Action.TOGGLE)
        self.store.undo()
        self.assertEqual(len(self.store.redo_stack), 1)
        self.store.dispatch(Action.TOGGLE)
        self.assertEqual(len(self.store.redo_stack), 0)


class TestFilter(unittest.TestCase):
    """Test search/filter functionality."""

    def setUp(self):
        ct = parse(SAMPLE)
        self.store = Store(ct)

    def test_filter_narrows(self):
        self.store.dispatch(Action.SET_FILTER, text="job1")
        self.assertEqual(len(self.store.jobs), 1)

    def test_filter_case_insensitive(self):
        self.store.dispatch(Action.SET_FILTER, text="JOB1")
        self.assertEqual(len(self.store.jobs), 1)

    def test_clear_filter(self):
        self.store.dispatch(Action.SET_FILTER, text="job1")
        self.store.dispatch(Action.SET_FILTER, text="")
        self.assertEqual(len(self.store.jobs), 3)

    def test_filter_no_match(self):
        self.store.dispatch(Action.SET_FILTER, text="nonexistent")
        self.assertEqual(len(self.store.jobs), 0)

    def test_filter_resets_selection(self):
        self.store.dispatch(Action.SELECT_NEXT)
        self.store.dispatch(Action.SET_FILTER, text="job")
        self.assertEqual(self.store.selected, 0)


class TestCreate(unittest.TestCase):
    """Test creating new jobs."""

    def setUp(self):
        ct = parse(SAMPLE)
        self.store = Store(ct)

    def test_create_job(self):
        initial = len(self.store.jobs)
        self.store.dispatch(Action.CREATE,
                            schedule="*/10 * * * *",
                            command="/scripts/new.sh")
        self.assertEqual(len(self.store.jobs), initial + 1)
        self.assertTrue(self.store.dirty)

    def test_create_empty_command_ignored(self):
        initial = len(self.store.jobs)
        self.store.dispatch(Action.CREATE,
                            schedule="* * * * *",
                            command="")
        self.assertEqual(len(self.store.jobs), initial)

    def test_create_selects_new_job(self):
        self.store.dispatch(Action.CREATE,
                            schedule="* * * * *",
                            command="/scripts/test.sh")
        self.assertEqual(self.store.selected, len(self.store.jobs) - 1)


if __name__ == "__main__":
    unittest.main()
