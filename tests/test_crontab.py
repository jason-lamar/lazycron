"""Tests for crontab parsing, serialization, and round-trip fidelity."""

import unittest

from lazycron.crontab import CrontabFile, Job, EnvVar, parse, toggle_job, delete_job, add_job, update_job


# Sample crontab content for testing
SAMPLE_CRONTAB = """# System crontab
SHELL=/bin/bash
PATH=/usr/bin:/bin:/usr/local/bin
MAILTO=user@example.com

# Health check every 15 minutes during business hours
*/15 9-17 * * 1-5 /scripts/health-check.sh

# Nightly backup at 2 AM
0 2 * * * /scripts/nightly-backup.sh >> /var/log/backup.log 2>&1

# Weekly report - disabled
# 0 8 * * 1 /scripts/weekly-report.sh

# API ping every 5 minutes
*/5 * * * * curl -s https://api.example.com/ping > /dev/null
"""

MINIMAL_CRONTAB = "*/5 * * * * /usr/bin/command\n"

EMPTY_CRONTAB = ""

COMMENTS_ONLY = """# This is a comment
# Another comment
# Not a cron job
"""


class TestParse(unittest.TestCase):
    """Test crontab parsing."""

    def test_parse_sample(self):
        ct = parse(SAMPLE_CRONTAB)
        self.assertEqual(len(ct.jobs), 4)
        self.assertEqual(len(ct.env_vars), 3)

    def test_env_vars(self):
        ct = parse(SAMPLE_CRONTAB)
        self.assertEqual(ct.env_vars[0].key, "SHELL")
        self.assertEqual(ct.env_vars[0].value, "/bin/bash")
        self.assertEqual(ct.env_vars[1].key, "PATH")
        self.assertEqual(ct.env_vars[2].key, "MAILTO")

    def test_enabled_jobs(self):
        ct = parse(SAMPLE_CRONTAB)
        enabled = [j for j in ct.jobs if j.enabled]
        self.assertEqual(len(enabled), 3)

    def test_disabled_jobs(self):
        ct = parse(SAMPLE_CRONTAB)
        disabled = [j for j in ct.jobs if not j.enabled]
        self.assertEqual(len(disabled), 1)
        self.assertIn("weekly-report", disabled[0].command)

    def test_job_schedule(self):
        ct = parse(SAMPLE_CRONTAB)
        # First job: */15 9-17 * * 1-5
        job = ct.jobs[0]
        self.assertEqual(job.schedule.minute, "*/15")
        self.assertEqual(job.schedule.hour, "9-17")
        self.assertEqual(job.schedule.dow, "1-5")

    def test_job_command(self):
        ct = parse(SAMPLE_CRONTAB)
        self.assertIn("health-check", ct.jobs[0].command)

    def test_parse_minimal(self):
        ct = parse(MINIMAL_CRONTAB)
        self.assertEqual(len(ct.jobs), 1)
        self.assertEqual(ct.jobs[0].schedule.minute, "*/5")

    def test_parse_empty(self):
        ct = parse(EMPTY_CRONTAB)
        self.assertEqual(len(ct.jobs), 0)
        self.assertEqual(len(ct.env_vars), 0)

    def test_parse_comments_only(self):
        ct = parse(COMMENTS_ONLY)
        self.assertEqual(len(ct.jobs), 0)

    def test_display_name(self):
        ct = parse(SAMPLE_CRONTAB)
        name = ct.jobs[0].display_name
        self.assertEqual(name, "health-check.sh")


class TestRoundTrip(unittest.TestCase):
    """Test that parse(text).serialize() == text for unmodified crontabs."""

    def test_round_trip_sample(self):
        text = SAMPLE_CRONTAB.strip() + "\n"
        ct = parse(text)
        result = ct.serialize()
        self.assertEqual(result, text)

    def test_round_trip_minimal(self):
        ct = parse(MINIMAL_CRONTAB)
        result = ct.serialize()
        self.assertEqual(result, MINIMAL_CRONTAB)

    def test_round_trip_empty(self):
        ct = parse(EMPTY_CRONTAB)
        result = ct.serialize()
        self.assertEqual(result, "")


class TestToggle(unittest.TestCase):
    """Test enabling/disabling jobs."""

    def test_disable_job(self):
        ct = parse(SAMPLE_CRONTAB)
        job = ct.jobs[0]
        self.assertTrue(job.enabled)
        toggle_job(ct, job)
        self.assertFalse(job.enabled)
        self.assertTrue(ct.has_modifications())

    def test_enable_job(self):
        ct = parse(SAMPLE_CRONTAB)
        # Find the disabled job
        disabled = [j for j in ct.jobs if not j.enabled][0]
        toggle_job(ct, disabled)
        self.assertTrue(disabled.enabled)

    def test_toggle_roundtrip(self):
        ct = parse(SAMPLE_CRONTAB)
        job = ct.jobs[0]
        toggle_job(ct, job)  # Disable
        toggle_job(ct, job)  # Re-enable
        self.assertTrue(job.enabled)


class TestDelete(unittest.TestCase):
    """Test deleting jobs."""

    def test_delete_job(self):
        ct = parse(SAMPLE_CRONTAB)
        initial_count = len(ct.jobs)
        job = ct.jobs[0]
        delete_job(ct, job)
        self.assertEqual(len(ct.jobs), initial_count - 1)
        self.assertTrue(ct.has_modifications())

    def test_delete_preserves_others(self):
        ct = parse(SAMPLE_CRONTAB)
        job = ct.jobs[1]
        cmd = job.command
        delete_job(ct, ct.jobs[0])
        # Second job should still be there
        self.assertTrue(any(j.command == cmd for j in ct.jobs))


class TestAdd(unittest.TestCase):
    """Test adding new jobs."""

    def test_add_job(self):
        ct = parse(SAMPLE_CRONTAB)
        initial_count = len(ct.jobs)
        job = add_job(ct, "0 * * * *", "/usr/bin/new-command")
        self.assertEqual(len(ct.jobs), initial_count + 1)
        self.assertEqual(job.command, "/usr/bin/new-command")
        self.assertTrue(job.enabled)

    def test_add_job_with_comment(self):
        ct = parse(SAMPLE_CRONTAB)
        job = add_job(ct, "*/10 * * * *", "/scripts/test.sh",
                      comment="Test job")
        self.assertEqual(job.comment, "Test job")

    def test_add_job_serialized(self):
        ct = parse(MINIMAL_CRONTAB)
        add_job(ct, "0 0 * * *", "/scripts/midnight.sh")
        text = ct.serialize()
        self.assertIn("/scripts/midnight.sh", text)


class TestUpdate(unittest.TestCase):
    """Test updating existing jobs."""

    def test_update_schedule(self):
        ct = parse(SAMPLE_CRONTAB)
        job = ct.jobs[0]
        update_job(ct, job, "*/30 * * * *", job.command)
        self.assertEqual(job.schedule.raw, "*/30 * * * *")
        self.assertTrue(ct.has_modifications())

    def test_update_command(self):
        ct = parse(SAMPLE_CRONTAB)
        job = ct.jobs[0]
        update_job(ct, job, job.schedule.raw, "/new/command.sh")
        self.assertEqual(job.command, "/new/command.sh")


if __name__ == "__main__":
    unittest.main()
