"""Map PDF field names/alt text to resolved profile values via synonym lookup."""

from __future__ import annotations

import json
import re
from pathlib import Path

_SYNONYMS_PATH = Path(__file__).parent / "data" / "synonyms.json"
_synonyms_cache: dict | None = None


def _load_synonyms() -> dict:
    global _synonyms_cache
    if _synonyms_cache is None:
        with _SYNONYMS_PATH.open() as f:
            raw = json.load(f)
        # Flatten category dicts into one token→path map
        flat: dict[str, str] = {}
        for key, val in raw.items():
            if key.startswith("_"):
                continue
            if isinstance(val, dict):
                for token, path in val.items():
                    flat[token.lower()] = path
        _synonyms_cache = flat
    return _synonyms_cache


def _normalize(text: str) -> str:
    """Lowercase, strip non-alpha/space, collapse whitespace."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _resolve_path(profile: dict, dot_path: str) -> str | None:
    """Walk a dot-notation path through a profile dict. Returns str value or None."""
    parts = dot_path.split(".")
    cur = profile
    for part in parts:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    if cur is None or isinstance(cur, (dict, list)):
        return None
    return str(cur)


def map_pdf_field(
    pdf_field_name: str,
    pdf_field_alt: str,
    resolved_profile: dict,
    index: dict,
) -> tuple[str | None, str]:
    """Map a PDF field to a profile value.

    Returns:
        (value, source_explanation)
        value is None if no match found.
    """
    synonyms = _load_synonyms()

    # Try exact and normalized token matches across field name + alt text
    candidates = [pdf_field_name, pdf_field_alt]

    for raw_token in candidates:
        if not raw_token:
            continue
        norm = _normalize(raw_token)

        # Exact synonym match
        if norm in synonyms:
            dot_path = synonyms[norm]
            value = _resolve_path(resolved_profile, dot_path)
            if value is not None:
                return value, f"synonym match: '{norm}' → {dot_path}"

        # Substring match (longest matching token wins)
        best_token: str | None = None
        best_path: str | None = None
        for token, path in synonyms.items():
            if token in norm and (best_token is None or len(token) > len(best_token)):
                best_token = token
                best_path = path
        if best_token and best_path:
            value = _resolve_path(resolved_profile, best_path)
            if value is not None:
                return value, f"substring match: '{best_token}' in '{norm}' → {best_path}"

    return None, f"no match for field '{pdf_field_name}' / alt '{pdf_field_alt}'"
