"""Map PDF field names/alt text to resolved profile values via synonym lookup."""

from __future__ import annotations

import json
import re
from pathlib import Path

_SYNONYMS_PATH = Path(__file__).parent / "data" / "synonyms.json"
_synonyms_cache: dict | None = None

# A candidate's score must be >= this to count as a "plausible alternative"
_PLAUSIBLE_THRESHOLD = 0.3
# The best candidate's score must be >= this to avoid "weak match" → low confidence
_WEAK_MATCH_THRESHOLD = 0.3


def _load_synonyms() -> dict:
    global _synonyms_cache
    if _synonyms_cache is None:
        with _SYNONYMS_PATH.open() as f:
            raw = json.load(f)
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
    """Lowercase, strip non-alpha/digit/space, collapse whitespace."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _resolve_path(profile: dict, dot_path: str) -> str | None:
    """Walk a dot-notation path through a profile dict. Returns str or None."""
    parts = dot_path.split(".")
    cur = profile
    for part in parts:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    if cur is None or isinstance(cur, (dict, list)):
        return None
    return str(cur)


def _score_match(token: str, norm: str) -> float:
    """Score how well a synonym token matches a normalised field label.

    Returns 1.0 for an exact match, len(token)/len(norm) for a substring
    match, and 0.0 if the token does not appear in the label at all.
    """
    if not norm:
        return 0.0
    if token == norm:
        return 1.0
    if token in norm:
        return len(token) / len(norm)
    return 0.0


def _determine_confidence(best_score: float, plausible_alt_count: int) -> str:
    """Map scoring facts to a confidence tier string.

    Rules (in priority order):
    1. Best score below weak threshold → low (match is too weak to trust)
    2. No plausible alternatives:
       - Exact match → high
       - Substring match → medium
    3. Exact best + exactly 1 plausible alt → medium
       (confident primary, one alternative worth noting)
    4. Everything else (non-exact best with alts, or exact + 2+ alts) → low
    """
    if best_score < _WEAK_MATCH_THRESHOLD:
        return "low"
    is_exact = best_score == 1.0
    if plausible_alt_count == 0:
        return "high" if is_exact else "medium"
    if is_exact and plausible_alt_count == 1:
        return "medium"
    # non-exact best with any alts, OR exact best with 2+ alts → genuinely ambiguous
    return "low"


def map_pdf_field(
    pdf_field_name: str,
    pdf_field_alt: str,
    resolved_profile: dict,
    index: dict,
) -> dict:
    """Map a PDF field to a profile value.

    Returns a result dict with keys:
        pdf_field_name, pdf_field_alt, value, confidence, source,
        alternatives, notes

    Never returns None — unmatched fields have confidence='none' and value=None.
    """
    synonyms = _load_synonyms()

    # Collect best-scored candidate per dot_path across both label sources.
    # Deduplication by dot_path ensures the same profile field reached by
    # multiple synonym tokens counts as a single candidate.
    best_by_path: dict[str, dict] = {}

    for raw_label in (pdf_field_name, pdf_field_alt):
        if not raw_label:
            continue
        norm = _normalize(raw_label)
        if not norm:
            continue

        for token, dot_path in synonyms.items():
            score = _score_match(token, norm)
            if score <= 0.0:
                continue
            value = _resolve_path(resolved_profile, dot_path)
            if value is None:
                continue  # no data in profile for this path; skip

            existing = best_by_path.get(dot_path)
            if existing is None or score > existing["score"]:
                best_by_path[dot_path] = {
                    "token": token,
                    "dot_path": dot_path,
                    "value": value,
                    "score": round(score, 4),
                }

    if not best_by_path:
        return {
            "pdf_field_name": pdf_field_name,
            "pdf_field_alt": pdf_field_alt,
            "value": None,
            "confidence": "none",
            "source": f"no match for field '{pdf_field_name}' / alt '{pdf_field_alt}'",
            "alternatives": [],
            "notes": [],
        }

    # Sort candidates: highest score first
    scored = sorted(best_by_path.values(), key=lambda c: c["score"], reverse=True)
    best = scored[0]
    rest = scored[1:]

    # Plausible alternatives are non-best candidates above the threshold
    plausible = [c for c in rest if c["score"] >= _PLAUSIBLE_THRESHOLD]

    confidence = _determine_confidence(best["score"], len(plausible))

    alternatives = [
        {
            "candidate_value": c["value"],
            "candidate_source": c["dot_path"],
            "score": c["score"],
        }
        for c in plausible
    ]

    notes: list[str] = []
    if confidence == "medium" and not plausible and best["score"] < 1.0:
        notes.append(
            f"Matched via substring (score={best['score']:.2f}); verify field label."
        )
    if confidence == "low" and plausible:
        notes.append(
            f"{len(plausible)} plausible alternative(s) found; review before commit."
        )

    return {
        "pdf_field_name": pdf_field_name,
        "pdf_field_alt": pdf_field_alt,
        "value": best["value"],
        "confidence": confidence,
        "source": f"{best['token']} → {best['dot_path']}",
        "alternatives": alternatives,
        "notes": notes,
    }
