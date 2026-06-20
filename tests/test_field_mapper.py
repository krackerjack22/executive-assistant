"""Tests for field_mapper.py — dict return shape, confidence tiers, synonym resolution."""

from __future__ import annotations

import pytest
from lib import profile_loader as pl
import field_mapper as fm

_VALID_CONFIDENCE = {"high", "medium", "low", "none"}
_RESULT_KEYS = {"pdf_field_name", "pdf_field_alt", "value", "confidence",
                "source", "alternatives", "notes"}


def _tyler():
    return pl.load_profile("tyler_combs")


def _index():
    return pl.load_index()


# ---------------------------------------------------------------------------
# Return shape contract
# ---------------------------------------------------------------------------

def test_return_is_dict():
    r = fm.map_pdf_field("patient name", "Patient Name", _tyler(), _index())
    assert isinstance(r, dict)


def test_return_has_all_keys():
    r = fm.map_pdf_field("patient name", "Patient Name", _tyler(), _index())
    assert _RESULT_KEYS.issubset(r.keys()), f"Missing keys: {_RESULT_KEYS - r.keys()}"


def test_confidence_is_valid_tier():
    r = fm.map_pdf_field("patient name", "Patient Name", _tyler(), _index())
    assert r["confidence"] in _VALID_CONFIDENCE


def test_unknown_field_confidence_is_none():
    r = fm.map_pdf_field("xyzunknownfield999", "", _tyler(), _index())
    assert r["confidence"] == "none"
    assert r["value"] is None


def test_unknown_field_source_describes_miss():
    r = fm.map_pdf_field("xyzunknownfield999", "", _tyler(), _index())
    assert "no match" in r["source"]


def test_alternatives_is_list():
    r = fm.map_pdf_field("patient name", "Patient Name", _tyler(), _index())
    assert isinstance(r["alternatives"], list)


def test_notes_is_list():
    r = fm.map_pdf_field("patient name", "Patient Name", _tyler(), _index())
    assert isinstance(r["notes"], list)


def test_pdf_field_name_echoed():
    r = fm.map_pdf_field("patient name", "Patient Name", _tyler(), _index())
    assert r["pdf_field_name"] == "patient name"


def test_pdf_field_alt_echoed():
    r = fm.map_pdf_field("patient name", "Patient Name", _tyler(), _index())
    assert r["pdf_field_alt"] == "Patient Name"


def test_alternative_shape():
    """Alternatives must have candidate_value, candidate_source, score."""
    # insurance company is expected to have 1 alternative (company → employer)
    r = fm.map_pdf_field("insurance company", "Insurance Carrier", _tyler(), _index())
    if r["alternatives"]:
        alt = r["alternatives"][0]
        assert "candidate_value" in alt
        assert "candidate_source" in alt
        assert "score" in alt
        assert isinstance(alt["score"], float)


# ---------------------------------------------------------------------------
# High-confidence fields (exact synonym match, no plausible alternatives)
# ---------------------------------------------------------------------------

def test_patient_name_high():
    r = fm.map_pdf_field("patient name", "Patient Name", _tyler(), _index())
    assert r["confidence"] == "high"
    assert r["value"] == "Tyler Combs"


def test_dob_high():
    r = fm.map_pdf_field("dob", "Date of Birth", _tyler(), _index())
    assert r["confidence"] == "high"
    assert "1981" in r["value"]


def test_phone_high():
    r = fm.map_pdf_field("phone", "Phone Number", _tyler(), _index())
    assert r["confidence"] == "high"
    assert "5035454177" in r["value"]


def test_city_high():
    r = fm.map_pdf_field("city", "City", _tyler(), _index())
    assert r["confidence"] == "high"
    assert r["value"] == "Lake Oswego"


def test_state_high():
    r = fm.map_pdf_field("state", "State", _tyler(), _index())
    assert r["confidence"] == "high"
    assert r["value"] == "OR"


def test_zip_high():
    r = fm.map_pdf_field("zip code", "Zip Code", _tyler(), _index())
    assert r["confidence"] == "high"
    assert r["value"] == "97035"


def test_member_id_high():
    r = fm.map_pdf_field("member id", "Member ID", _tyler(), _index())
    assert r["confidence"] == "high"
    assert "240272015" in r["value"]


def test_group_number_high():
    r = fm.map_pdf_field("group number", "Group Number", _tyler(), _index())
    assert r["confidence"] == "high"
    assert r["value"] == "37000201"


# ---------------------------------------------------------------------------
# Medium-confidence fields
# ---------------------------------------------------------------------------

def test_insurance_company_medium_or_better():
    """'insurance company' is exact for the carrier, but 'company' also matches employer."""
    r = fm.map_pdf_field("insurance company", "Insurance Carrier", _tyler(), _index())
    assert r["confidence"] in ("high", "medium")
    assert r["value"] is not None
    assert "Regence" in r["value"]


def test_pcp_medium_or_better():
    r = fm.map_pdf_field("primary care physician", "PCP Name", _tyler(), _index())
    assert r["confidence"] in ("high", "medium")
    assert r["value"] is not None
    assert "Coe" in r["value"] or "Ryan" in r["value"]


def test_email_matched():
    r = fm.map_pdf_field("email", "Email Address", _tyler(), _index())
    assert r["value"] is not None
    assert "@" in r["value"]
    assert r["confidence"] in ("high", "medium")


def test_employer_matched():
    r = fm.map_pdf_field("employer", "Employer Name", _tyler(), _index())
    assert r["value"] is not None
    assert "Clearcut" in r["value"]
    assert r["confidence"] in ("high", "medium")


def test_street_address_matched():
    r = fm.map_pdf_field("street address", "Address", _tyler(), _index())
    assert r["value"] is not None
    assert "Rockwood" in r["value"]
    assert r["confidence"] in ("high", "medium")


# ---------------------------------------------------------------------------
# Low-confidence field
# ---------------------------------------------------------------------------

def test_phone_email_is_low():
    """'phone email' matches contact.primary_phone and contact.email with equal scores → low."""
    r = fm.map_pdf_field("phone email", "Phone or Email", _tyler(), _index())
    assert r["confidence"] == "low"
    assert r["value"] is not None  # still picks a value
    assert len(r["alternatives"]) >= 1


def test_low_confidence_has_alternatives():
    r = fm.map_pdf_field("phone email", "Phone or Email", _tyler(), _index())
    assert r["confidence"] == "low"
    for alt in r["alternatives"]:
        assert "candidate_value" in alt
        assert "score" in alt
        assert alt["score"] >= 0.3


# ---------------------------------------------------------------------------
# Acceptance criteria: zero low and zero none for the 14 synthetic form fields
# ---------------------------------------------------------------------------

_SYNTHETIC_FIELDS = [
    ("patient name",            "Patient Name"),
    ("dob",                     "Date of Birth"),
    ("gender",                  "Gender"),
    ("phone",                   "Phone Number"),
    ("email",                   "Email Address"),
    ("street address",          "Address"),
    ("city",                    "City"),
    ("state",                   "State"),
    ("zip code",                "Zip Code"),
    ("employer",                "Employer Name"),
    ("insurance company",       "Insurance Carrier"),
    ("member id",               "Member ID"),
    ("group number",            "Group Number"),
    ("primary care physician",  "PCP Name"),
]


def test_zero_low_for_synthetic_fields():
    tyler = _tyler()
    idx = _index()
    low_fields = []
    for name, alt in _SYNTHETIC_FIELDS:
        r = fm.map_pdf_field(name, alt, tyler, idx)
        if r["confidence"] == "low":
            low_fields.append((name, r["confidence"], r["value"]))
    assert low_fields == [], f"Unexpected low-confidence fields: {low_fields}"


def test_zero_none_for_synthetic_fields():
    tyler = _tyler()
    idx = _index()
    none_fields = []
    for name, alt in _SYNTHETIC_FIELDS:
        r = fm.map_pdf_field(name, alt, tyler, idx)
        if r["confidence"] == "none":
            none_fields.append((name, r["confidence"]))
    assert none_fields == [], f"Unexpected none-confidence fields: {none_fields}"


def test_source_explanation_present_all_fields():
    """Every mapped field has a non-empty source explanation."""
    tyler = _tyler()
    idx = _index()
    for name, alt in _SYNTHETIC_FIELDS:
        r = fm.map_pdf_field(name, alt, tyler, idx)
        assert isinstance(r["source"], str) and len(r["source"]) > 0
