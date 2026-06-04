"""Tests for edit/new modal form navigation behavior."""

import unittest

from lazycron.ui.modals import CMD_FIELD, NAME_FIELD, _FormState


class TestFormStateNavigation(unittest.TestCase):
    def setUp(self):
        self.form = _FormState(["0", "*", "*", "*", "*"], "echo hi", "test")

    def test_move_down_from_cron_goes_to_name(self):
        self.form.active = 2

        self.form.move_vertical(1)

        self.assertEqual(self.form.active, NAME_FIELD)
        self.assertEqual(self.form.last_cron_active, 2)

    def test_move_up_from_cron_goes_to_command(self):
        self.form.active = 3

        self.form.move_vertical(-1)

        self.assertEqual(self.form.active, CMD_FIELD)
        self.assertEqual(self.form.last_cron_active, 3)

    def test_move_between_text_fields_and_back_to_same_cron_column(self):
        self.form.active = 4
        self.form.move_vertical(1)
        self.form.move_vertical(1)
        self.form.move_vertical(1)

        self.assertEqual(self.form.active, 4)

    def test_move_up_from_command_reaches_name_then_cron(self):
        self.form.active = 1
        self.form.move_vertical(1)
        self.form.move_vertical(1)

        self.assertEqual(self.form.active, CMD_FIELD)

        self.form.move_vertical(-1)
        self.assertEqual(self.form.active, NAME_FIELD)

        self.form.move_vertical(-1)
        self.assertEqual(self.form.active, 1)


if __name__ == "__main__":
    unittest.main()
