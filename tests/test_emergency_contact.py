"""Tests for skills/form-autofill/emergency_contact.py"""

from __future__ import annotations

import sys
from pathlib import Path

_SKILL_DIR = Path(__file__).resolve().parent.parent / "skills" / "form-autofill"
if str(_SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(_SKILL_DIR))

from lib import profile_loader as pl
import emergency_contact as ec_mod


def _profile(profile_id: str) -> dict:
    return pl.load_profile(profile_id)


def _index() -> dict:
    return pl.load_index()


# ---------------------------------------------------------------------------
# Tyler: priority 1 = Madeline Miller (profile type)
# ---------------------------------------------------------------------------

def test_tyler_ec_priority1_is_madeline():
    tyler = _profile("tyler_combs")
    ec = ec_mod.get_emergency_contact(tyler, _index(), priority=1)
    assert ec is not None
    assert "Madeline" in ec["name"]


def test_tyler_ec_priority1_relationship():
    tyler = _profile("tyler_combs")
    ec = ec_mod.get_emergency_contact(tyler, _index(), priority=1)
    assert ec["relationship_label"] == "Domestic Partner"


def test_tyler_ec_priority1_has_phone():
    tyler = _profile("tyler_combs")
    ec = ec_mod.get_emergency_contact(tyler, _index(), priority=1)
    # Madeline's phone is in her profile — may be None if not set, but field should exist
    assert "phone" in ec


def test_tyler_ec_priority2_none():
    tyler = _profile("tyler_combs")
    ec = ec_mod.get_emergency_contact(tyler, _index(), priority=2)
    assert ec is None


# ---------------------------------------------------------------------------
# Charlotte: priority 1 = Tyler (profile), priority 2 = Lynsee (external_person)
# ---------------------------------------------------------------------------

def test_charlotte_ec_priority1_is_tyler():
    charlotte = _profile("charlotte_combs")
    ec = ec_mod.get_emergency_contact(charlotte, _index(), priority=1)
    assert ec is not None
    assert "Tyler" in ec["name"]


def test_charlotte_ec_priority1_relationship():
    charlotte = _profile("charlotte_combs")
    ec = ec_mod.get_emergency_contact(charlotte, _index(), priority=1)
    assert ec["relationship_label"] == "Father"


def test_charlotte_ec_priority1_phone():
    charlotte = _profile("charlotte_combs")
    ec = ec_mod.get_emergency_contact(charlotte, _index(), priority=1)
    # Tyler has a phone number
    assert ec["phone"] is not None
    assert "-" in ec["phone"]  # formatted as NXX-NXX-XXXX


def test_charlotte_ec_priority2_is_lynsee():
    charlotte = _profile("charlotte_combs")
    ec = ec_mod.get_emergency_contact(charlotte, _index(), priority=2)
    assert ec is not None
    assert "Lynsee" in ec["name"]


def test_charlotte_ec_priority2_relationship():
    charlotte = _profile("charlotte_combs")
    ec = ec_mod.get_emergency_contact(charlotte, _index(), priority=2)
    assert ec["relationship_label"] == "Mother"


def test_charlotte_ec_priority2_type_external():
    charlotte = _profile("charlotte_combs")
    ec = ec_mod.get_emergency_contact(charlotte, _index(), priority=2)
    assert ec["type"] == "external_person"


# ---------------------------------------------------------------------------
# Fiona: priority 1 = Tyler (profile), priority 2 = Lynsee (external_person)
# ---------------------------------------------------------------------------

def test_fiona_ec_priority1_is_tyler():
    fiona = _profile("fiona_combs")
    ec = ec_mod.get_emergency_contact(fiona, _index(), priority=1)
    assert ec is not None
    assert "Tyler" in ec["name"]


def test_fiona_ec_priority2_is_lynsee():
    fiona = _profile("fiona_combs")
    ec = ec_mod.get_emergency_contact(fiona, _index(), priority=2)
    assert ec is not None
    assert "Lynsee" in ec["name"]


# ---------------------------------------------------------------------------
# Isaac: priority 1 = Madeline (profile)
# ---------------------------------------------------------------------------

def test_isaac_ec_priority1_is_madeline():
    isaac = _profile("isaac_baron")
    ec = ec_mod.get_emergency_contact(isaac, _index(), priority=1)
    assert ec is not None
    assert "Madeline" in ec["name"]


def test_isaac_ec_priority1_relationship():
    isaac = _profile("isaac_baron")
    ec = ec_mod.get_emergency_contact(isaac, _index(), priority=1)
    assert ec["relationship_label"] == "Mother"


def test_isaac_ec_priority2_none():
    isaac = _profile("isaac_baron")
    ec = ec_mod.get_emergency_contact(isaac, _index(), priority=2)
    assert ec is None


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_no_emergency_contacts_returns_none():
    fake_profile = {"profile_id": "fake", "identity": {}}
    ec = ec_mod.get_emergency_contact(fake_profile, {}, priority=1)
    assert ec is None


def test_ec_returns_dict_shape():
    tyler = _profile("tyler_combs")
    ec = ec_mod.get_emergency_contact(tyler, _index(), priority=1)
    assert ec is not None
    for key in ("name", "phone", "relationship_label", "type"):
        assert key in ec, f"Missing key: {key}"
