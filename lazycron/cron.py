"""Cron expression parser, validator, and human-readable translator.

Zero external dependencies — pure stdlib implementation.
Handles standard 5-field cron expressions (minute hour dom month dow).
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

# -- Constants ----------------------------------------------------------------

FIELD_NAMES = ("minute", "hour", "dom", "month", "dow")

FIELD_RANGES = {
    "minute": (0, 59),
    "hour": (0, 23),
    "dom": (1, 31),
    "month": (1, 12),
    "dow": (0, 7),  # 0 and 7 both = Sunday
}

DOW_NAMES = {
    "sun": 0, "mon": 1, "tue": 2, "wed": 3,
    "thu": 4, "fri": 5, "sat": 6,
}

MONTH_NAMES = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "may": 5, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

DOW_LABELS = ["Sunday", "Monday", "Tuesday", "Wednesday",
              "Thursday", "Friday", "Saturday"]

MONTH_LABELS = ["", "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December"]

# Common presets for the odometer builder
MINUTE_PRESETS = ["*", "0", "*/5", "*/10", "*/15", "*/30", "0,30"]
HOUR_PRESETS = ["*", "0", "*/2", "*/4", "*/6", "*/8", "*/12",
                "9-17", "0-8", "18-23", "6", "12", "18"]
DOM_PRESETS = ["*", "1", "15", "1,15", "1-7", "1-15", "15-28"]
MONTH_PRESETS = ["*", "1", "*/2", "*/3", "*/6", "1,4,7,10", "1-6", "7-12"]
DOW_PRESETS = ["*", "1-5", "0,6", "1", "2", "3", "4", "5", "0", "6"]

FIELD_PRESETS = {
    "minute": MINUTE_PRESETS,
    "hour": HOUR_PRESETS,
    "dom": DOM_PRESETS,
    "month": MONTH_PRESETS,
    "dow": DOW_PRESETS,
}

# Human-readable labels for each preset (value → label)
PRESET_LABELS = {
    "minute": {
        "*": "Every minute",
        "0": "On the hour (:00)",
        "*/5": "Every 5 minutes",
        "*/10": "Every 10 minutes",
        "*/15": "Every 15 minutes",
        "*/30": "Every 30 minutes",
        "0,30": "Twice per hour (:00, :30)",
    },
    "hour": {
        "*": "Every hour",
        "0": "Midnight (00:00)",
        "*/2": "Every 2 hours",
        "*/4": "Every 4 hours",
        "*/6": "Every 6 hours",
        "*/8": "Every 8 hours",
        "*/12": "Every 12 hours",
        "9-17": "Business hours (9a-5p)",
        "0-8": "Overnight (12a-8a)",
        "18-23": "Evening (6p-11p)",
        "6": "6:00 AM",
        "12": "Noon (12:00)",
        "18": "6:00 PM",
    },
    "dom": {
        "*": "Every day",
        "1": "1st of month",
        "15": "15th of month",
        "1,15": "1st and 15th",
        "1-7": "First week (1-7)",
        "1-15": "First half (1-15)",
        "15-28": "Second half (15-28)",
    },
    "month": {
        "*": "Every month",
        "1": "January only",
        "*/2": "Every 2 months",
        "*/3": "Every quarter",
        "*/6": "Every 6 months",
        "1,4,7,10": "Quarterly (Jan,Apr,Jul,Oct)",
        "1-6": "First half (Jan-Jun)",
        "7-12": "Second half (Jul-Dec)",
    },
    "dow": {
        "*": "Every day of week",
        "1-5": "Weekdays (Mon-Fri)",
        "0,6": "Weekends (Sat-Sun)",
        "1": "Monday",
        "2": "Tuesday",
        "3": "Wednesday",
        "4": "Thursday",
        "5": "Friday",
        "0": "Sunday",
        "6": "Saturday",
    },
}


# -- Parsing ------------------------------------------------------------------

def _normalize_names(token: str, names: dict[str, int]) -> str:
    """Replace 3-letter day/month names with their numeric equivalents."""
    result = token.lower()
    for name, num in names.items():
        result = result.replace(name, str(num))
    return result


def _parse_field(token: str, lo: int, hi: int, field_name: str) -> tuple[set[int], str]:
    """Parse a single cron field into a set of valid integers.

    Returns (values, error_message). error_message is empty on success.
    """
    if token == "*":
        return set(range(lo, hi + 1)), ""

    values: set[int] = set()

    for part in token.split(","):
        part = part.strip()
        if not part:
            return set(), f"{field_name}: empty element in list"

        # Handle step: */N or N-M/S
        step = 1
        if "/" in part:
            base, step_str = part.split("/", 1)
            try:
                step = int(step_str)
            except ValueError:
                return set(), f"{field_name}: invalid step '{step_str}'"
            if step < 1:
                return set(), f"{field_name}: step must be >= 1"
            part = base

        # Handle range: N-M
        if "-" in part:
            range_parts = part.split("-", 1)
            try:
                start = int(range_parts[0])
                end = int(range_parts[1])
            except ValueError:
                return set(), f"{field_name}: invalid range '{part}'"
            if start < lo or end > hi:
                return set(), f"{field_name}: range {start}-{end} outside {lo}-{hi}"
            if start > end:
                return set(), f"{field_name}: range start {start} > end {end}"
            values.update(range(start, end + 1, step))
        elif part == "*":
            values.update(range(lo, hi + 1, step))
        else:
            try:
                val = int(part)
            except ValueError:
                return set(), f"{field_name}: invalid value '{part}'"
            # Special case: dow 7 == 0 (Sunday)
            if field_name == "dow" and val == 7:
                val = 0
            elif val < lo or val > hi:
                return set(), f"{field_name}: value {val} outside {lo}-{hi}"
            if step > 1:
                values.update(range(val, hi + 1, step))
            else:
                values.add(val)

    return values, ""


def parse_field(token: str, field_name: str) -> tuple[set[int], str]:
    """Parse a cron field with name substitution."""
    lo, hi = FIELD_RANGES[field_name]

    # Substitute names
    if field_name == "dow":
        token = _normalize_names(token, DOW_NAMES)
    elif field_name == "month":
        token = _normalize_names(token, MONTH_NAMES)

    return _parse_field(token, lo, hi, field_name)


# -- CronExpression -----------------------------------------------------------

@dataclass
class CronExpression:
    """Parsed 5-field cron expression with human-readable translation."""

    raw: str
    minute: str
    hour: str
    dom: str
    month: str
    dow: str

    # Parsed value sets (lazily populated)
    _minute_vals: set[int] = field(default_factory=set, repr=False)
    _hour_vals: set[int] = field(default_factory=set, repr=False)
    _dom_vals: set[int] = field(default_factory=set, repr=False)
    _month_vals: set[int] = field(default_factory=set, repr=False)
    _dow_vals: set[int] = field(default_factory=set, repr=False)
    _parsed: bool = field(default=False, repr=False)

    def _ensure_parsed(self) -> Optional[str]:
        """Parse all fields, return error message or None."""
        if self._parsed:
            return None

        fields = [
            ("minute", self.minute),
            ("hour", self.hour),
            ("dom", self.dom),
            ("month", self.month),
            ("dow", self.dow),
        ]

        for name, token in fields:
            vals, err = parse_field(token, name)
            if err:
                return err
            setattr(self, f"_{name}_vals", vals)

        # Normalize dow: 7 -> 0
        if 7 in self._dow_vals:
            self._dow_vals.discard(7)
            self._dow_vals.add(0)

        self._parsed = True
        return None

    def validate(self) -> tuple[bool, str]:
        """Returns (valid, error_message)."""
        err = self._ensure_parsed()
        if err:
            return False, err
        return True, ""

    def describe(self) -> str:
        """Human-readable English description of this schedule."""
        err = self._ensure_parsed()
        if err:
            return f"Invalid: {err}"

        parts: list[str] = []

        # Minute clause
        parts.append(_describe_minute(self.minute, self._minute_vals))

        # Hour clause
        hour_desc = _describe_hour(self.hour, self._hour_vals)
        if hour_desc:
            parts.append(hour_desc)

        # Day-of-month clause
        dom_desc = _describe_dom(self.dom, self._dom_vals)
        if dom_desc:
            parts.append(dom_desc)

        # Month clause
        month_desc = _describe_month(self.month, self._month_vals)
        if month_desc:
            parts.append(month_desc)

        # Day-of-week clause
        dow_desc = _describe_dow(self.dow, self._dow_vals)
        if dow_desc:
            parts.append(dow_desc)

        result = ", ".join(parts)
        return result[0].upper() + result[1:] if result else "Every minute"

    def next_run(self, after: Optional[datetime] = None) -> Optional[datetime]:
        """Compute next execution time after the given datetime."""
        err = self._ensure_parsed()
        if err:
            return None

        if after is None:
            after = datetime.now()

        # Start from the next minute
        dt = after.replace(second=0, microsecond=0) + timedelta(minutes=1)

        # Search up to 4 years ahead (covers leap years + all month combos)
        limit = after + timedelta(days=366 * 4)

        while dt < limit:
            if dt.month not in self._month_vals:
                # Skip to next valid month
                dt = _next_month(dt, self._month_vals)
                continue

            dow = dt.isoweekday() % 7  # 0=Sun, 1=Mon, ..., 6=Sat

            # DOM and DOW interaction: standard cron OR behavior
            # (if both are restricted, match either)
            dom_restricted = self.dom != "*"
            dow_restricted = self.dow != "*"

            dom_match = dt.day in self._dom_vals
            dow_match = dow in self._dow_vals

            if dom_restricted and dow_restricted:
                day_ok = dom_match or dow_match
            elif dom_restricted:
                day_ok = dom_match
            elif dow_restricted:
                day_ok = dow_match
            else:
                day_ok = True

            if not day_ok:
                dt = dt.replace(hour=0, minute=0) + timedelta(days=1)
                continue

            if dt.hour not in self._hour_vals:
                dt = _next_hour(dt, self._hour_vals)
                continue

            if dt.minute not in self._minute_vals:
                dt = _next_minute(dt, self._minute_vals)
                continue

            return dt

        return None

    def next_n(self, n: int, after: Optional[datetime] = None) -> list[datetime]:
        """Compute next N execution times."""
        results: list[datetime] = []
        current = after
        for _ in range(n):
            nxt = self.next_run(current)
            if nxt is None:
                break
            results.append(nxt)
            current = nxt
        return results


# -- Next-run helpers ---------------------------------------------------------

def _next_month(dt: datetime, valid_months: set[int]) -> datetime:
    """Advance to the first day of the next valid month."""
    y, m = dt.year, dt.month
    for _ in range(48):  # Max 4 years of months
        m += 1
        if m > 12:
            m = 1
            y += 1
        if m in valid_months:
            return datetime(y, m, 1, 0, 0)
    return dt + timedelta(days=366 * 4)  # Give up


def _next_hour(dt: datetime, valid_hours: set[int]) -> datetime:
    """Advance to the next valid hour (minute=0)."""
    for h in sorted(valid_hours):
        if h > dt.hour:
            return dt.replace(hour=h, minute=0)
    # Wrap to next day
    return (dt + timedelta(days=1)).replace(hour=min(valid_hours), minute=0)


def _next_minute(dt: datetime, valid_minutes: set[int]) -> datetime:
    """Advance to the next valid minute within the current hour, or wrap."""
    for m in sorted(valid_minutes):
        if m > dt.minute:
            return dt.replace(minute=m)
    # Wrap: move to next hour, minute will be resolved in outer loop
    return dt.replace(minute=0) + timedelta(hours=1)


# -- Human-readable description helpers ---------------------------------------

def _describe_minute(token: str, vals: set[int]) -> str:
    if token == "*":
        return "every minute"
    if token.startswith("*/"):
        n = token[2:]
        return f"every {n} minutes"
    if len(vals) == 1:
        v = next(iter(vals))
        if v == 0:
            return "at minute 0"
        return f"at minute {v}"
    return f"at minutes {_format_set(vals)}"


def _describe_hour(token: str, vals: set[int]) -> str:
    if token == "*":
        return ""
    if token.startswith("*/"):
        n = token[2:]
        return f"every {n} hours"
    if "-" in token and "/" not in token and "," not in token:
        parts = token.split("-")
        return f"between {_fmt_hour(int(parts[0]))} and {_fmt_hour(int(parts[1]))}"
    if len(vals) == 1:
        v = next(iter(vals))
        return f"at {_fmt_hour(v)}"
    sorted_vals = sorted(vals)
    return f"during hours {', '.join(_fmt_hour(h) for h in sorted_vals)}"


def _describe_dom(token: str, vals: set[int]) -> str:
    if token == "*":
        return ""
    if len(vals) == 1:
        v = next(iter(vals))
        return f"on day {v} of the month"
    return f"on days {_format_set(vals)} of the month"


def _describe_month(token: str, vals: set[int]) -> str:
    if token == "*":
        return ""
    if len(vals) == 1:
        v = next(iter(vals))
        return f"in {MONTH_LABELS[v]}"
    names = [MONTH_LABELS[m] for m in sorted(vals)]
    return f"in {', '.join(names)}"


def _describe_dow(token: str, vals: set[int]) -> str:
    if token == "*":
        return ""
    if vals == {1, 2, 3, 4, 5}:
        return "Monday through Friday"
    if vals == {0, 6}:
        return "on weekends"
    if len(vals) == 1:
        v = next(iter(vals))
        return f"on {DOW_LABELS[v]}"
    names = [DOW_LABELS[d] for d in sorted(vals)]
    return f"on {', '.join(names)}"


def _format_set(vals: set[int]) -> str:
    """Format a set of integers as a readable list."""
    return ", ".join(str(v) for v in sorted(vals))


def _fmt_hour(h: int) -> str:
    """Format hour as HH:00."""
    return f"{h:02d}:00"


# -- Factory ------------------------------------------------------------------

def parse_expression(raw: str) -> CronExpression:
    """Parse a 5-field cron expression string."""
    parts = raw.strip().split()
    if len(parts) < 5:
        # Pad with wildcards for partial expressions
        parts.extend(["*"] * (5 - len(parts)))
    return CronExpression(
        raw=raw.strip(),
        minute=parts[0],
        hour=parts[1],
        dom=parts[2],
        month=parts[3],
        dow=parts[4],
    )
