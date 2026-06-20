"""Tests for lib/profile_writer.write_profile()."""

from __future__ import annotations

import copy
import json
import os
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAL_PROFILE = {
    "profile_id": "test_person",
    "schema_version": "2.0.0",
    "last_updated": "2025-01-01",
    "relationships": [{"role": "self", "profile_id": "test_person"}],
    "source_extraction_notes": [
        {"field": "identity.legal_name", "source_form": "Old Form", "applied_by": "test"}
    ],
    "identity": {"legal_name": "Test Person"},
}

SAMPLE_NOTE = {
    "field": "contact.primary_phone",
    "source_form": "Test Form",
    "source_form_path": None,
    "applied_by": "user via interview",
}


@pytest.fixture()
def profile_dir(tmp_path: Path) -> Path:
    profile = copy.deepcopy(MINIMAL_PROFILE)
    (tmp_path / "test_person.json").write_text(json.dumps(profile, indent=2))
    return tmp_path


@pytest.fixture(autouse=True)
def patch_profiles_dir(profile_dir: Path, monkeypatch):
    monkeypatch.setenv("EXEC_ASSISTANT_PROFILES_DIR", str(profile_dir))


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _load(profile_dir: Path, pid: str = "test_person") -> dict:
    return json.loads((profile_dir / f"{pid}.json").read_text())


def _updated() -> dict:
    d = copy.deepcopy(MINIMAL_PROFILE)
    d["identity"]["legal_name"] = "Test Person Updated"
    return d


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_write_updates_last_updated(profile_dir: Path) -> None:
    from lib import profile_writer

    profile_writer.write_profile("test_person", _updated(), SAMPLE_NOTE)

    saved = _load(profile_dir)
    assert saved["last_updated"] == date.today().isoformat()


def test_write_appends_source_note(profile_dir: Path) -> None:
    from lib import profile_writer

    original_count = len(MINIMAL_PROFILE["source_extraction_notes"])
    profile_writer.write_profile("test_person", _updated(), SAMPLE_NOTE)

    saved = _load(profile_dir)
    assert len(saved["source_extraction_notes"]) == original_count + 1
    last = saved["source_extraction_notes"][-1]
    assert last["field"] == SAMPLE_NOTE["field"]
    assert last["applied_by"] == SAMPLE_NOTE["applied_by"]


def test_write_is_atomic(profile_dir: Path) -> None:
    from lib import profile_writer

    original_text = (profile_dir / "test_person.json").read_text()

    with patch("os.replace", side_effect=OSError("simulated crash")):
        with pytest.raises(OSError, match="simulated crash"):
            profile_writer.write_profile("test_person", _updated(), SAMPLE_NOTE)

    assert (profile_dir / "test_person.json").read_text() == original_text
    # No leftover temp files
    tmp_files = list(profile_dir.glob("*.tmp"))
    assert tmp_files == []


def test_write_rejects_changed_profile_id(profile_dir: Path) -> None:
    from lib import profile_writer

    bad = _updated()
    bad["profile_id"] = "someone_else"

    with pytest.raises(ValueError, match="profile_id mismatch"):
        profile_writer.write_profile("test_person", bad, SAMPLE_NOTE)

    # Original file must be untouched
    saved = _load(profile_dir)
    assert saved["last_updated"] == MINIMAL_PROFILE["last_updated"]


def test_write_rejects_changed_schema_version(profile_dir: Path) -> None:
    from lib import profile_writer

    bad = _updated()
    bad["schema_version"] = "3.0.0"

    with pytest.raises(ValueError, match="schema_version"):
        profile_writer.write_profile("test_person", bad, SAMPLE_NOTE)


def test_write_rejects_changed_relationships(profile_dir: Path) -> None:
    from lib import profile_writer

    bad = _updated()
    bad["relationships"] = [{"role": "parent", "profile_id": "other_person"}]

    with pytest.raises(ValueError, match="relationships"):
        profile_writer.write_profile("test_person", bad, SAMPLE_NOTE)
