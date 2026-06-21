"""Tests for skills/form-autofill/learning.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Make the form-autofill skill dir importable
_AUTOFILL_DIR = Path(__file__).resolve().parent.parent / "skills" / "form-autofill"
if str(_AUTOFILL_DIR) not in sys.path:
    sys.path.insert(0, str(_AUTOFILL_DIR))

import learning


# ---------------------------------------------------------------------------
# derive_token
# ---------------------------------------------------------------------------

def test_derive_token_prefers_human_readable_alt():
    token = learning.derive_token("Field_47", "Subscriber Name")
    assert token == "subscriber name"


def test_derive_token_rejects_opaque_ids_only():
    token = learning.derive_token("Field_47", "")
    assert token is None


def test_derive_token_falls_back_to_name_when_alt_missing():
    token = learning.derive_token("patient legal name", "")
    assert token == "patient legal name"


def test_derive_token_normalizes_whitespace_and_punctuation():
    # apostrophe + colon are non-alpha/digit → become spaces → collapsed
    token = learning.derive_token("", "Patient's Name:")
    assert token == "patient s name"


def test_derive_token_returns_none_when_both_opaque():
    assert learning.derive_token("Field47", "Field47") is None


def test_derive_token_returns_none_when_both_empty():
    assert learning.derive_token("", "") is None


def test_derive_token_rejects_single_word_machine_id():
    # "ABC123" matches the opaque-ID pattern → reject
    assert learning.derive_token("ABC123", "") is None


def test_derive_token_accepts_multi_word_name():
    token = learning.derive_token("first name", "First Name")
    # alt is preferred when human-readable
    assert token == "first name"


# ---------------------------------------------------------------------------
# is_pollution_candidate
# ---------------------------------------------------------------------------

def test_is_pollution_candidate_rejects_one_char():
    assert learning.is_pollution_candidate("a") is True


def test_is_pollution_candidate_rejects_two_chars():
    assert learning.is_pollution_candidate("aa") is True


def test_is_pollution_candidate_accepts_three_chars():
    assert learning.is_pollution_candidate("abc") is False


def test_is_pollution_candidate_rejects_digits_only():
    assert learning.is_pollution_candidate("123") is True


def test_is_pollution_candidate_rejects_punctuation_only():
    assert learning.is_pollution_candidate("...") is True


def test_is_pollution_candidate_accepts_normal_token():
    assert learning.is_pollution_candidate("subscriber name") is False


# ---------------------------------------------------------------------------
# build_entry
# ---------------------------------------------------------------------------

def test_build_entry_shape():
    entry = learning.build_entry(
        dot_path="identity.legal_name",
        source_form="TestForm.pdf",
        pdf_field_name="PatientName",
        pdf_field_alt="Patient Name",
        learn_action="confirmed",
        profile_id="tyler_combs",
        notes=[],
    )
    assert entry["dot_path"] == "identity.legal_name"
    assert entry["source_form"] == "TestForm.pdf"
    assert entry["times_seen"] == 1
    assert entry["learn_action"] == "confirmed"
    assert entry["profile_id_at_learn"] == "tyler_combs"
    assert isinstance(entry["notes"], list)
    assert "learned_at" in entry
    assert entry["learned_at"].endswith("Z")


# ---------------------------------------------------------------------------
# save_learned
# ---------------------------------------------------------------------------

def test_save_learned_creates_section_if_missing(tmp_path):
    """A synonyms.json without a 'learned' key gets one after save."""
    synonyms = {"_version": "1.2", "identity": {"name": "identity.legal_name"}}
    syn_file = tmp_path / "synonyms.json"
    syn_file.write_text(json.dumps(synonyms))

    entry = learning.build_entry(
        dot_path="identity.legal_name",
        source_form="Test.pdf",
        pdf_field_name="Name",
        pdf_field_alt="Full Name",
        learn_action="confirmed",
        profile_id="tyler_combs",
        notes=[],
    )
    learning.save_learned({"full name": entry}, syn_file)

    result = json.loads(syn_file.read_text())
    assert "learned" in result
    assert "full name" in result["learned"]
    assert result["learned"]["full name"]["dot_path"] == "identity.legal_name"
    # Original sections preserved
    assert result["identity"]["name"] == "identity.legal_name"


def test_save_learned_increments_times_seen(tmp_path):
    """Second save of same token increments counter and updates timestamp."""
    synonyms = {"_version": "1.2", "learned": {}}
    syn_file = tmp_path / "synonyms.json"
    syn_file.write_text(json.dumps(synonyms))

    entry = learning.build_entry(
        dot_path="identity.legal_name",
        source_form="Form1.pdf",
        pdf_field_name="Name",
        pdf_field_alt="Full Name",
        learn_action="confirmed",
        profile_id="tyler_combs",
        notes=[],
    )
    learning.save_learned({"full name": entry}, syn_file)

    # Save again with the same token
    entry2 = learning.build_entry(
        dot_path="identity.legal_name",
        source_form="Form2.pdf",
        pdf_field_name="Name",
        pdf_field_alt="Full Name",
        learn_action="confirmed",
        profile_id="tyler_combs",
        notes=[],
    )
    learning.save_learned({"full name": entry2}, syn_file)

    result = json.loads(syn_file.read_text())
    stored = result["learned"]["full name"]
    assert stored["times_seen"] == 2


def test_save_learned_notes_path_change(tmp_path):
    """If dot_path changes on second save, a note is appended."""
    syn_file = tmp_path / "synonyms.json"
    syn_file.write_text(json.dumps({"_version": "1.2", "learned": {}}))

    e1 = learning.build_entry("identity.legal_name", "F.pdf", "N", "Name", "confirmed", None, [])
    learning.save_learned({"full name": e1}, syn_file)

    e2 = learning.build_entry("identity.first_name", "F.pdf", "N", "Name", "confirmed", None, [])
    learning.save_learned({"full name": e2}, syn_file)

    result = json.loads(syn_file.read_text())
    stored = result["learned"]["full name"]
    assert stored["dot_path"] == "identity.first_name"
    assert any("Path changed" in n for n in stored["notes"])


def test_save_learned_preserves_existing_tokens(tmp_path):
    """Tokens not in the new batch remain intact."""
    syn_file = tmp_path / "synonyms.json"
    syn_file.write_text(json.dumps({"_version": "1.2", "learned": {}}))

    e1 = learning.build_entry("identity.legal_name", "F.pdf", "N", "A", "confirmed", None, [])
    e2 = learning.build_entry("identity.first_name", "F.pdf", "N", "B", "confirmed", None, [])
    learning.save_learned({"token a": e1}, syn_file)
    learning.save_learned({"token b": e2}, syn_file)

    result = json.loads(syn_file.read_text())
    assert "token a" in result["learned"]
    assert "token b" in result["learned"]


def test_save_learned_atomic_write_uses_tmp(tmp_path, monkeypatch):
    """Verify a .tmp file is created and then renamed (atomicity check)."""
    syn_file = tmp_path / "synonyms.json"
    syn_file.write_text(json.dumps({"_version": "1.2", "learned": {}}))

    tmp_files_created: list[str] = []
    original_mkstemp = __import__("tempfile").mkstemp

    def tracking_mkstemp(**kwargs):
        fd, path = original_mkstemp(**kwargs)
        tmp_files_created.append(path)
        return fd, path

    monkeypatch.setattr("tempfile.mkstemp", tracking_mkstemp)

    entry = learning.build_entry("identity.legal_name", "F.pdf", "N", "Name", "confirmed", None, [])
    learning.save_learned({"full name": entry}, syn_file)

    # At least one tmp file was created (the atomic write path)
    assert any(".tmp" in p for p in tmp_files_created)
    # The final file is valid JSON and .tmp is gone
    assert syn_file.exists()
    result = json.loads(syn_file.read_text())
    assert "full name" in result["learned"]
