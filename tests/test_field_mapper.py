"""Tests for field_mapper.py — synonym resolution against a synthetic field list."""

import pytest
from lib import profile_loader as pl
import field_mapper as fm


def _tyler():
    return pl.load_profile("tyler_combs")


def _index():
    return pl.load_index()


# Synthetic field names mimicking Tyler_Med_Data.pdf
_SYNTHETIC_FIELDS = [
    ("patient name", "Patient Name"),
    ("dob", "Date of Birth"),
    ("gender", "Gender"),
    ("phone", "Phone Number"),
    ("email", "Email Address"),
    ("street address", "Address"),
    ("city", "City"),
    ("state", "State"),
    ("zip code", "Zip Code"),
    ("insurance company", "Insurance Carrier"),
    ("member id", "Member ID"),
    ("group number", "Group Number"),
    ("primary care physician", "PCP Name"),
    ("employer", "Employer Name"),
]


def test_patient_name():
    val, src = fm.map_pdf_field("patient name", "Patient Name", _tyler(), _index())
    assert val == "Tyler Combs", f"Expected 'Tyler Combs', got {val!r} (source: {src})"


def test_dob():
    val, src = fm.map_pdf_field("dob", "Date of Birth", _tyler(), _index())
    assert val is not None
    assert "1981" in val


def test_phone():
    val, src = fm.map_pdf_field("phone", "Phone Number", _tyler(), _index())
    assert val is not None
    assert "5035454177" in val


def test_email():
    val, src = fm.map_pdf_field("email", "Email Address", _tyler(), _index())
    assert val is not None
    assert "@" in val


def test_street_address():
    val, src = fm.map_pdf_field("street address", "Address", _tyler(), _index())
    assert val is not None
    assert "Rockwood" in val


def test_city():
    val, src = fm.map_pdf_field("city", "City", _tyler(), _index())
    assert val == "Lake Oswego"


def test_state():
    val, src = fm.map_pdf_field("state", "State", _tyler(), _index())
    assert val == "OR"


def test_zip():
    val, src = fm.map_pdf_field("zip code", "Zip Code", _tyler(), _index())
    assert val == "97035"


def test_insurance_carrier():
    val, src = fm.map_pdf_field("insurance company", "Insurance Carrier", _tyler(), _index())
    assert val is not None
    assert "Regence" in val


def test_member_id():
    val, src = fm.map_pdf_field("member id", "Member ID", _tyler(), _index())
    assert val is not None
    # Tyler's member id contains "240272015"
    assert "240272015" in val


def test_group_number():
    val, src = fm.map_pdf_field("group number", "Group Number", _tyler(), _index())
    assert val == "37000201"


def test_pcp():
    val, src = fm.map_pdf_field("primary care physician", "PCP Name", _tyler(), _index())
    assert val is not None
    assert "Coe" in val or "Ryan" in val


def test_employer():
    val, src = fm.map_pdf_field("employer", "Employer Name", _tyler(), _index())
    assert val is not None
    assert "Clearcut" in val


def test_unknown_field_returns_none():
    val, src = fm.map_pdf_field("xyzunknownfield999", "", _tyler(), _index())
    assert val is None
    assert "no match" in src


def test_source_explanation_present():
    """Every mapped field returns a non-empty source explanation."""
    for name, alt in _SYNTHETIC_FIELDS:
        val, src = fm.map_pdf_field(name, alt, _tyler(), _index())
        assert isinstance(src, str) and len(src) > 0
