"""Tests for lib/role_resolver.py — relationship graph traversal."""

import pytest
from lib import profile_loader as pl
from lib import role_resolver as rr


def _load_all_profiles():
    index = pl.load_index()
    ids = list(index.get("profiles", {}).keys())
    return {pid: pl.load_profile(pid) for pid in ids}


def test_father_from_fiona():
    """'father' keyword on Fiona → Tyler (male parent)."""
    all_p = _load_all_profiles()
    index = pl.load_index()
    fiona = all_p["fiona_combs"]
    result = rr.resolve(fiona, "father", all_p, index["role_resolution_map"])
    assert result is not None
    assert result.get("profile_id") == "tyler_combs"


def test_mother_from_fiona():
    """'mother' keyword on Fiona → external_persons Lynsee (female parent)."""
    all_p = _load_all_profiles()
    index = pl.load_index()
    fiona = all_p["fiona_combs"]
    result = rr.resolve(fiona, "mother", all_p, index["role_resolution_map"])
    assert result is not None
    assert "Lynsee" in result.get("legal_name", "")


def test_secondary_emergency_contact_from_charlotte():
    """secondary_emergency_contact on Charlotte → external_persons Penny."""
    all_p = _load_all_profiles()
    index = pl.load_index()
    charlotte = all_p["charlotte_combs"]
    result = rr.resolve(charlotte, "secondary_emergency_contact", all_p, index["role_resolution_map"])
    assert result is not None
    assert "Penny" in result.get("legal_name", "")


def test_subscriber_from_fiona():
    """'subscriber' on Fiona's insurance → Tyler (via resolves_to_field)."""
    all_p = _load_all_profiles()
    index = pl.load_index()
    fiona = all_p["fiona_combs"]
    result = rr.resolve(fiona, "subscriber", all_p, index["role_resolution_map"])
    assert result is not None
    assert result.get("profile_id") == "tyler_combs"


def test_unverified_skipped_strict():
    """Unverified relationships are skipped when strict=True (default)."""
    all_p = _load_all_profiles()
    index = pl.load_index()
    # isaac_baron → tyler_combs is step_parent_of but UNVERIFIED
    isaac = all_p["isaac_baron"]
    # "step_parent" resolution from Isaac should skip Tyler (unverified)
    result = rr.resolve(isaac, "step_parent", all_p, index["role_resolution_map"])
    # With strict=True, unverified is skipped
    assert result is None or result.get("profile_id") != "tyler_combs"


def test_unverified_included_not_strict():
    """Unverified relationships ARE included when strict=False."""
    all_p = _load_all_profiles()
    index = pl.load_index()
    isaac = all_p["isaac_baron"]
    result = rr.resolve(isaac, "step_parent", all_p, index["role_resolution_map"], strict=False)
    assert result is not None
    assert result.get("profile_id") == "tyler_combs"


def test_unknown_keyword_returns_none():
    all_p = _load_all_profiles()
    index = pl.load_index()
    tyler = all_p["tyler_combs"]
    result = rr.resolve(tyler, "nonexistent_role_xyz", all_p, index["role_resolution_map"])
    assert result is None


def test_partner_from_tyler():
    """'partner' on Tyler → Madeline."""
    all_p = _load_all_profiles()
    index = pl.load_index()
    tyler = all_p["tyler_combs"]
    result = rr.resolve(tyler, "partner", all_p, index["role_resolution_map"])
    assert result is not None
    assert result.get("profile_id") == "madeline_miller"
