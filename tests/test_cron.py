"""Tests for cron expression parsing, validation, and human-readable translation."""

import unittest
from datetime import datetime

from lazycron.cron import CronExpression, parse_expression, parse_field


class TestParseField(unittest.TestCase):
    """Test individual cron field parsing."""

    def test_wildcard(self):
        vals, err = parse_field("*", "minute")
        self.assertEqual(err, "")
        self.assertEqual(vals, set(range(0, 60)))

    def test_single_value(self):
        vals, err = parse_field("5", "minute")
        self.assertEqual(err, "")
        self.assertEqual(vals, {5})

    def test_range(self):
        vals, err = parse_field("1-5", "dow")
        self.assertEqual(err, "")
        self.assertEqual(vals, {1, 2, 3, 4, 5})

    def test_step(self):
        vals, err = parse_field("*/15", "minute")
        self.assertEqual(err, "")
        self.assertEqual(vals, {0, 15, 30, 45})

    def test_range_with_step(self):
        vals, err = parse_field("0-30/10", "minute")
        self.assertEqual(err, "")
        self.assertEqual(vals, {0, 10, 20, 30})

    def test_list(self):
        vals, err = parse_field("1,3,5", "dow")
        self.assertEqual(err, "")
        self.assertEqual(vals, {1, 3, 5})

    def test_list_with_range(self):
        vals, err = parse_field("1-3,5", "dow")
        self.assertEqual(err, "")
        self.assertEqual(vals, {1, 2, 3, 5})

    def test_dow_7_equals_0(self):
        vals, err = parse_field("7", "dow")
        self.assertEqual(err, "")
        self.assertEqual(vals, {0})

    def test_dow_names(self):
        vals, err = parse_field("mon-fri", "dow")
        self.assertEqual(err, "")
        self.assertEqual(vals, {1, 2, 3, 4, 5})

    def test_month_names(self):
        vals, err = parse_field("jan,apr,jul,oct", "month")
        self.assertEqual(err, "")
        self.assertEqual(vals, {1, 4, 7, 10})

    def test_out_of_range(self):
        vals, err = parse_field("60", "minute")
        self.assertIn("outside", err)

    def test_invalid_token(self):
        vals, err = parse_field("abc", "minute")
        self.assertIn("invalid", err)

    def test_invalid_range(self):
        vals, err = parse_field("5-2", "minute")
        self.assertIn("start", err)


class TestCronExpression(unittest.TestCase):
    """Test CronExpression parsing and validation."""

    def test_parse_basic(self):
        expr = parse_expression("*/15 * * * *")
        self.assertEqual(expr.minute, "*/15")
        self.assertEqual(expr.hour, "*")
        self.assertEqual(expr.dom, "*")
        self.assertEqual(expr.month, "*")
        self.assertEqual(expr.dow, "*")

    def test_validate_valid(self):
        expr = parse_expression("0 9 * * 1-5")
        valid, err = expr.validate()
        self.assertTrue(valid)
        self.assertEqual(err, "")

    def test_validate_invalid(self):
        expr = parse_expression("60 * * * *")
        valid, err = expr.validate()
        self.assertFalse(valid)

    def test_parse_partial(self):
        expr = parse_expression("0 9")
        self.assertEqual(expr.minute, "0")
        self.assertEqual(expr.hour, "9")
        self.assertEqual(expr.dom, "*")

    def test_raw_preserved(self):
        expr = parse_expression("  */5 9-17 * * mon-fri  ")
        self.assertEqual(expr.raw, "*/5 9-17 * * mon-fri")


class TestHumanReadable(unittest.TestCase):
    """Test human-readable description generation."""

    def test_every_minute(self):
        expr = parse_expression("* * * * *")
        self.assertEqual(expr.describe(), "Every minute")

    def test_every_15_minutes(self):
        desc = parse_expression("*/15 * * * *").describe()
        self.assertIn("15 minutes", desc)

    def test_at_midnight(self):
        desc = parse_expression("0 0 * * *").describe()
        self.assertIn("minute 0", desc.lower())
        self.assertIn("00:00", desc)

    def test_weekdays(self):
        desc = parse_expression("0 9 * * 1-5").describe()
        self.assertIn("Monday through Friday", desc)

    def test_monthly(self):
        desc = parse_expression("0 0 1 * *").describe()
        self.assertIn("day 1", desc.lower())

    def test_specific_months(self):
        desc = parse_expression("0 0 1 1,6 *").describe()
        self.assertIn("January", desc)
        self.assertIn("June", desc)

    def test_hourly(self):
        desc = parse_expression("0 * * * *").describe()
        self.assertIn("minute 0", desc.lower())

    def test_weekend(self):
        desc = parse_expression("0 8 * * 0,6").describe()
        self.assertIn("weekend", desc.lower())


class TestNextRun(unittest.TestCase):
    """Test next execution time computation."""

    def test_every_minute(self):
        after = datetime(2026, 3, 1, 10, 0, 0)
        expr = parse_expression("* * * * *")
        nxt = expr.next_run(after)
        self.assertIsNotNone(nxt)
        self.assertEqual(nxt, datetime(2026, 3, 1, 10, 1))

    def test_specific_time(self):
        after = datetime(2026, 3, 1, 8, 0, 0)
        expr = parse_expression("0 9 * * *")
        nxt = expr.next_run(after)
        self.assertIsNotNone(nxt)
        self.assertEqual(nxt.hour, 9)
        self.assertEqual(nxt.minute, 0)

    def test_next_day(self):
        after = datetime(2026, 3, 1, 23, 59, 0)
        expr = parse_expression("0 0 * * *")
        nxt = expr.next_run(after)
        self.assertIsNotNone(nxt)
        self.assertEqual(nxt.day, 2)
        self.assertEqual(nxt.hour, 0)

    def test_weekday_skip(self):
        # Friday evening
        after = datetime(2026, 2, 27, 18, 0, 0)  # Friday
        expr = parse_expression("0 9 * * 1-5")
        nxt = expr.next_run(after)
        self.assertIsNotNone(nxt)
        # Should be Monday
        self.assertEqual(nxt.weekday(), 0)  # Monday

    def test_next_n(self):
        after = datetime(2026, 3, 1, 10, 0, 0)
        expr = parse_expression("*/15 * * * *")
        results = expr.next_n(4, after)
        self.assertEqual(len(results), 4)
        self.assertEqual(results[0].minute, 15)  # next */15 after :00 is :15
        self.assertEqual(results[1].minute, 30)
        self.assertEqual(results[2].minute, 45)
        self.assertEqual(results[3].minute, 0)  # next hour


class TestInvalidExpressions(unittest.TestCase):
    """Test error handling for malformed expressions."""

    def test_describe_invalid(self):
        expr = parse_expression("99 * * * *")
        desc = expr.describe()
        self.assertIn("Invalid", desc)

    def test_next_run_invalid(self):
        expr = parse_expression("99 * * * *")
        nxt = expr.next_run()
        self.assertIsNone(nxt)


if __name__ == "__main__":
    unittest.main()
