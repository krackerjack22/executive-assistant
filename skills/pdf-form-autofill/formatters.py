"""Value formatters applied at fill-time: dates, phones, grades."""

from __future__ import annotations

import re
from datetime import date

# Ordered school grade progression (lowercase for matching).
_GRADE_ORDER = [
    "kindergarten",
    "1st", "2nd", "3rd", "4th", "5th", "6th",
    "7th", "8th", "9th", "10th", "11th", "12th",
]

# After this month/day in any year, increment stored grade by one.
_GRADE_CUTOFF_MONTH = 6
_GRADE_CUTOFF_DAY = 15


def format_date(value: str) -> str:
    """Convert an ISO-8601 date string (YYYY-MM-DD) to MM/DD/YYYY.

    Passes through any value that is not a recognised ISO date unchanged
    so existing formatted strings don't get double-processed.
    """
    if not value:
        return value
    # Already in US format — return as-is
    if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{2,4}", value):
        return value
    parts = value.split("-")
    if len(parts) == 3 and all(p.isdigit() for p in parts):
        yyyy, mm, dd = parts
        return f"{mm}/{dd}/{yyyy}"
    return value  # unrecognised format — pass through


def format_phone(value: str) -> str:
    """Format a phone number as NXX-NXX-XXXX.

    Falls back to the raw value if it cannot be parsed as a 10-digit US
    number (strips all non-digit characters first).
    """
    if not value:
        return value
    digits = re.sub(r"\D", "", value)
    if len(digits) == 11 and digits[0] == "1":
        digits = digits[1:]
    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    return value  # fallback: return as stored


def format_grade(value: str, today: date | None = None) -> str:
    """Return the current school grade, incrementing after June 15.

    If today is on or after June 15, the stored grade (as of the end of
    the previous school year) is bumped by one to reflect the upcoming
    school year.
    """
    if not value:
        return value
    if today is None:
        today = date.today()
    cutoff = date(today.year, _GRADE_CUTOFF_MONTH, _GRADE_CUTOFF_DAY)
    if today < cutoff:
        return value  # school year still in progress — use stored grade
    lower = value.strip().lower()
    try:
        idx = _GRADE_ORDER.index(lower)
        return _GRADE_ORDER[idx + 1] if idx + 1 < len(_GRADE_ORDER) else "N/A"
    except ValueError:
        return value  # unknown format — return as stored


def format_today(today: date | None = None) -> str:
    """Return today's date in MM/DD/YYYY format."""
    if today is None:
        today = date.today()
    return today.strftime("%m/%d/%Y")


# Paths whose values need formatting at fill-time.
_DATE_PATHS = {"date_of_birth", "date_of_death", "effective_date", "termination_date"}
_PHONE_KEYWORDS = {"phone", "fax"}


def apply_format(value: str, dot_path: str, today: date | None = None) -> str:
    """Apply the appropriate formatter for the given profile dot-path."""
    if not value:
        return value
    # Date fields
    last_segment = dot_path.rsplit(".", 1)[-1]
    if last_segment in _DATE_PATHS or last_segment.endswith("_date"):
        return format_date(value)
    # Phone / fax fields
    if any(kw in last_segment for kw in _PHONE_KEYWORDS):
        return format_phone(value)
    # Grade field
    if last_segment == "grade_or_year":
        return format_grade(value, today)
    return value
