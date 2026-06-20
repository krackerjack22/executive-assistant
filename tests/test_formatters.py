"""Tests for skills/form-autofill/formatters.py"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

# Ensure the skill directory is on sys.path
_SKILL_DIR = Path(__file__).resolve().parent.parent / "skills" / "form-autofill"
if str(_SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(_SKILL_DIR))

import formatters as fmt


# ---------------------------------------------------------------------------
# format_date
# ---------------------------------------------------------------------------

def test_iso_date_converts_to_us():
    assert fmt.format_date("1981-06-17") == "06/17/1981"


def test_iso_date_with_leading_zero():
    assert fmt.format_date("2013-12-04") == "12/04/2013"


def test_already_us_format_passthrough():
    assert fmt.format_date("06/17/1981") == "06/17/1981"


def test_non_date_string_passthrough():
    assert fmt.format_date("Tyler Combs") == "Tyler Combs"


def test_empty_string_passthrough():
    assert fmt.format_date("") == ""


# ---------------------------------------------------------------------------
# format_phone
# ---------------------------------------------------------------------------

def test_raw_10_digit_phone():
    assert fmt.format_phone("5035454177") == "503-545-4177"


def test_already_dashed_phone_passthrough():
    # 503-545-4177 strips to 5035454177, then re-formats to same
    assert fmt.format_phone("503-545-4177") == "503-545-4177"


def test_11_digit_with_country_code():
    assert fmt.format_phone("15035454177") == "503-545-4177"


def test_phone_with_parens():
    assert fmt.format_phone("(503) 545-4177") == "503-545-4177"


def test_short_phone_fallback():
    assert fmt.format_phone("12345") == "12345"


def test_empty_phone_passthrough():
    assert fmt.format_phone("") == ""


# ---------------------------------------------------------------------------
# format_grade — before cutoff (June 15)
# ---------------------------------------------------------------------------

def test_grade_before_cutoff_unchanged():
    before = date(2026, 6, 14)
    assert fmt.format_grade("7th", today=before) == "7th"


def test_grade_on_cutoff_increments():
    on_cutoff = date(2026, 6, 15)
    assert fmt.format_grade("7th", today=on_cutoff) == "8th"


def test_grade_after_cutoff_increments():
    after = date(2026, 9, 1)
    assert fmt.format_grade("5th", today=after) == "6th"


def test_kindergarten_increments_to_1st():
    after = date(2026, 9, 1)
    assert fmt.format_grade("Kindergarten", today=after) == "1st"


def test_kindergarten_case_insensitive():
    after = date(2026, 9, 1)
    assert fmt.format_grade("kindergarten", today=after) == "1st"


def test_grade_12th_maxes_at_na():
    after = date(2026, 9, 1)
    assert fmt.format_grade("12th", today=after) == "N/A"


def test_unknown_grade_passthrough():
    after = date(2026, 9, 1)
    assert fmt.format_grade("College Freshman", today=after) == "College Freshman"


# ---------------------------------------------------------------------------
# format_today
# ---------------------------------------------------------------------------

def test_format_today_returns_us_date():
    fixed = date(2026, 6, 19)
    assert fmt.format_today(fixed) == "06/19/2026"


def test_format_today_none_uses_real_today():
    result = fmt.format_today(None)
    # Should be MM/DD/YYYY
    parts = result.split("/")
    assert len(parts) == 3
    assert len(parts[2]) == 4


# ---------------------------------------------------------------------------
# apply_format dispatch
# ---------------------------------------------------------------------------

def test_apply_format_dob():
    result = fmt.apply_format("1981-06-17", "identity.date_of_birth")
    assert result == "06/17/1981"


def test_apply_format_phone():
    result = fmt.apply_format("5035454177", "contact.primary_phone")
    assert result == "503-545-4177"


def test_apply_format_grade_increments():
    after = date(2026, 9, 1)
    result = fmt.apply_format("7th", "school.grade_or_year", today=after)
    assert result == "8th"


def test_apply_format_non_formatted_passthrough():
    result = fmt.apply_format("Tyler Combs", "identity.legal_name")
    assert result == "Tyler Combs"
