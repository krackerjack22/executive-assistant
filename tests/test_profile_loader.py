"""Tests for lib/profile_loader.py — load all 5 profiles, verify inheritance."""

import pytest
from lib import profile_loader as pl


def test_load_index():
    index = pl.load_index()
    assert "profiles" in index
    assert "tyler_combs" in index["profiles"]


def test_list_profiles():
    profiles = pl.list_profiles()
    ids = [p["profile_id"] for p in profiles]
    assert set(ids) >= {"tyler_combs", "fiona_combs", "charlotte_combs", "madeline_miller", "isaac_baron"}


def test_load_tyler():
    p = pl.load_profile("tyler_combs")
    assert p["profile_id"] == "tyler_combs"
    assert p["identity"]["legal_name"] == "Tyler Combs"
    # same_as mailing should be resolved to home
    assert p["addresses"]["mailing"].get("city") == "Lake Oswego"
    # self-referential insurance subscriber
    assert p["insurance"]["primary"]["subscriber_profile_id"] == "tyler_combs"


def test_load_fiona_address_inherits_tyler():
    """Fiona's addresses.home = {same_as_profile: tyler_combs} → Tyler's home address."""
    p = pl.load_profile("fiona_combs")
    home = p["addresses"]["home"]
    # Must be a full address dict, not the raw same_as_profile marker
    assert "street_1" in home, f"Expected resolved address, got: {home}"
    assert home["city"] == "Lake Oswego"


def test_load_fiona_insurance_inherits_tyler():
    """Fiona's insurance inherits from Tyler as subscriber."""
    p = pl.load_profile("fiona_combs")
    ins = p["insurance"]["primary"]
    # Should have Tyler's carrier info merged in
    assert ins.get("carrier") == "Regence Blue Cross"
    # Local override preserved
    assert ins.get("subscriber_relationship_to_patient") == "father"


def test_load_charlotte():
    p = pl.load_profile("charlotte_combs")
    assert p["profile_id"] == "charlotte_combs"
    home = p["addresses"]["home"]
    assert "street_1" in home  # inherited from Tyler


def test_load_madeline():
    p = pl.load_profile("madeline_miller")
    assert p["profile_id"] == "madeline_miller"


def test_load_isaac():
    p = pl.load_profile("isaac_baron")
    assert p["profile_id"] == "isaac_baron"


def test_missing_profile_raises():
    with pytest.raises(FileNotFoundError):
        pl.load_profile("nonexistent_profile_xyz")
