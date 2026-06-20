"""Atomic write-back for profile JSON files."""

from __future__ import annotations

import copy
import json
import os
import tempfile
from datetime import date
from pathlib import Path

from lib import env as _env


def _profile_path(profile_id: str) -> Path:
    return _env.profiles_dir() / f"{profile_id}.json"


def write_profile(
    profile_id: str,
    updated_dict: dict,
    source_note: dict,
) -> None:
    """Atomically write an updated profile JSON.

    source_note shape:
      {
        "field": "contact.primary_phone",
        "source_form": "LOCC Intake Form",
        "source_form_path": "/path/to/form.pdf",  # or None
        "applied_by": "user via interview"
      }

    Rules:
    - Write to a temp file in the same directory, then os.replace() (atomic)
    - Update profile["last_updated"] to today's ISO date (YYYY-MM-DD)
    - Append source_note to profile["source_extraction_notes"] list
    - Never mutate profile_id, schema_version, or relationships array
    - Raises ValueError if updated_dict["profile_id"] != profile_id
    - Raises ValueError if schema_version changed
    - Raises ValueError if relationships array changed
    """
    if updated_dict.get("profile_id") != profile_id:
        raise ValueError(
            f"profile_id mismatch: expected {profile_id!r}, "
            f"got {updated_dict.get('profile_id')!r}"
        )

    target = _profile_path(profile_id)
    with target.open() as f:
        original = json.load(f)

    if updated_dict.get("schema_version") != original.get("schema_version"):
        raise ValueError(
            f"schema_version must not change: original={original.get('schema_version')!r}, "
            f"updated={updated_dict.get('schema_version')!r}"
        )

    if updated_dict.get("relationships") != original.get("relationships"):
        raise ValueError("relationships array must not be modified via write_profile")

    out = copy.deepcopy(updated_dict)
    out["last_updated"] = date.today().isoformat()

    notes = list(out.get("source_extraction_notes") or [])
    notes.append(source_note)
    out["source_extraction_notes"] = notes

    dir_path = target.parent
    fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump(out, fh, indent=2)
        os.replace(tmp_path, target)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
