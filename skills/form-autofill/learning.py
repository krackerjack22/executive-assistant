"""Synonym learning: derive tokens from PDF field labels and persist to synonyms.json."""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

_OPAQUE_ID_RE = re.compile(r"^[A-Za-z]+_?\d+$")


def _normalize(text: str) -> str:
    """Lowercase, strip non-alpha/digit/space, collapse whitespace."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _is_human_readable(s: str) -> bool:
    """True when the string looks like a human label rather than a machine ID."""
    s = s.strip()
    return " " in s and len(s) >= 3 and not _OPAQUE_ID_RE.match(s)


def derive_token(pdf_field_name: str, pdf_field_alt: str) -> str | None:
    """Pick the better label and normalize. Return None if neither is usable.

    Prefers alt text when human-readable; falls back to field name.
    Returns None if neither candidate is human-readable.
    """
    for candidate in (pdf_field_alt, pdf_field_name):
        if candidate and _is_human_readable(candidate):
            return _normalize(candidate)
    return None


def is_pollution_candidate(token: str) -> bool:
    """True if token is too short, all digits, or otherwise unsafe to learn."""
    if len(token) < 3:
        return True
    # All digits or all punctuation/whitespace after stripping
    if re.fullmatch(r"[\d\W]+", token):
        return True
    return False


def build_entry(
    dot_path: str,
    source_form: str,
    pdf_field_name: str,
    pdf_field_alt: str,
    learn_action: str,
    profile_id: str | None,
    notes: list[str],
) -> dict:
    """Construct a learned-entry dict with current UTC timestamp."""
    return {
        "dot_path": dot_path,
        "source_form": source_form,
        "pdf_field_name_original": pdf_field_name,
        "pdf_field_alt_original": pdf_field_alt,
        "learned_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "times_seen": 1,
        "learn_action": learn_action,
        "profile_id_at_learn": profile_id,
        "notes": list(notes),
    }


def save_learned(entries: dict[str, dict], synonyms_path: Path) -> None:
    """Atomic write: read existing synonyms.json, merge into 'learned' section.

    - Updates times_seen on duplicate tokens.
    - Appends a note if dot_path changes.
    - Uses temp-file + os.replace() for atomicity.
    - Raises PermissionError if the file is not writable.
    """
    with synonyms_path.open() as f:
        data = json.load(f)

    if "learned" not in data:
        data["learned"] = {}

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for token, new_entry in entries.items():
        if token in data["learned"]:
            existing = data["learned"][token]
            existing["times_seen"] = existing.get("times_seen", 1) + 1
            existing["learned_at"] = now_str
            if existing.get("dot_path") != new_entry["dot_path"]:
                note = (
                    f"Path changed from {existing['dot_path']} to "
                    f"{new_entry['dot_path']} on {now_str[:10]}"
                )
                existing.setdefault("notes", []).append(note)
                existing["dot_path"] = new_entry["dot_path"]
        else:
            data["learned"][token] = new_entry

    dir_path = synonyms_path.parent
    fd, tmp_path = tempfile.mkstemp(dir=str(dir_path), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump(data, fh, indent=2)
        os.replace(tmp_path, str(synonyms_path))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
