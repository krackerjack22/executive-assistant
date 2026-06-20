"""Map PDF field names/alt text to resolved profile values via synonym lookup."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import formatters as _fmt
import emergency_contact as _ec

_SYNONYMS_PATH = Path(__file__).parent / "data" / "synonyms.json"
_synonyms_cache: dict | None = None

_CONTEXT_RULES_PATH = Path(__file__).parent / "data" / "field_context_rules.json"
_context_rules_cache: list | None = None

# Minimum score for a candidate to enter the pool at all.
# Scores below this threshold are treated as noise (no match).
_WEAK_MATCH_THRESHOLD = 0.3

# Minimum score for a non-best candidate to count as a "plausible alternative".
_PLAUSIBLE_THRESHOLD = 0.3


def _load_context_rules() -> list:
    global _context_rules_cache
    if _context_rules_cache is None:
        with _CONTEXT_RULES_PATH.open() as f:
            data = json.load(f)
        _context_rules_cache = data.get("rules", [])
    return _context_rules_cache


def _is_permitted_by_context(
    dot_path: str, profile_id: str | None, norm_name: str, norm_alt: str
) -> bool:
    """Return False when a context rule blocks this dot_path for the given field label."""
    for rule in _load_context_rules():
        if rule.get("profile_id") != profile_id:
            continue
        if rule.get("dot_path") != dot_path:
            continue
        # Rule applies — require a permit keyword in the combined field label.
        combined = f"{norm_name} {norm_alt}"
        keywords = rule.get("keywords_that_permit_use", [])
        if any(kw.lower() in combined for kw in keywords):
            return True
        return False
    return True


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


def _resolve_and_format(
    profile: dict, dot_path: str, today: date | None
) -> str | None:
    """Resolve a dot-path from the profile and apply value formatting."""
    value = _resolve_path(profile, dot_path)
    if value is None:
        return None
    return _fmt.apply_format(value, dot_path, today)


def _score_match(token: str, norm: str) -> float:
    """Score how well a synonym token matches a normalised field label.

    Returns 1.0 for exact, len(token)/len(norm) for substring, 0.0 if absent.
    """
    if not norm:
        return 0.0
    if token == norm:
        return 1.0
    if token in norm:
        return len(token) / len(norm)
    return 0.0


def _determine_confidence(best_score: float, plausible_alt_count: int) -> str:
    """Map scoring facts to a confidence tier string."""
    if best_score < _WEAK_MATCH_THRESHOLD:
        return "low"
    is_exact = best_score == 1.0
    if plausible_alt_count == 0:
        return "high" if is_exact else "medium"
    if is_exact and plausible_alt_count == 1:
        return "medium"
    return "low"


def _make_result(
    pdf_field_name: str,
    pdf_field_alt: str,
    value: str | None,
    confidence: str,
    source: str,
    alternatives: list | None = None,
    notes: list | None = None,
) -> dict:
    return {
        "pdf_field_name": pdf_field_name,
        "pdf_field_alt": pdf_field_alt,
        "value": value,
        "confidence": confidence,
        "source": source,
        "alternatives": alternatives or [],
        "notes": notes or [],
    }


# ---------------------------------------------------------------------------
# Special-field pattern detectors
# ---------------------------------------------------------------------------

def _is_combined_city_state_zip(norm_name: str, norm_alt: str) -> bool:
    """True when the field appears to combine city, state, and zip."""
    for s in (norm_name, norm_alt):
        # Compact forms like "citystzip", "citystatezipn"
        stripped = s.replace(" ", "")
        if re.search(r"cityst(ate)?zip", stripped):
            return True
        # Explicit combined: contains both "city" and ("zip" or "state")
        if "city" in s and ("zip" in s or "state" in s):
            return True
    return False


def _is_mailing_if_different(norm_name: str, norm_alt: str) -> bool:
    """True when the field asks for mailing address only if it differs from home."""
    patterns = ["if different", "if other", "if not same"]
    for s in (norm_name, norm_alt):
        if any(p in s for p in patterns):
            return True
    return False


def _is_signature_date(norm_name: str, norm_alt: str) -> bool:
    """True when the field is a signature-adjacent date (not a DOB or named date)."""
    dob_keywords = {"birth", "dob", "born", "birthdate", "date of birth"}
    for s in (norm_name, norm_alt):
        if any(kw in s for kw in dob_keywords):
            return False
    # Match: "date", "date 2", "date_2" (already normalised — underscores → spaces)
    for s in (norm_name, norm_alt):
        if re.fullmatch(r"date ?[\d]*", s.strip()):
            return True
    return False


def _is_emergency_contact_field(norm_name: str, norm_alt: str) -> str | None:
    """Return 'name', 'phone', or 'relationship' if this is an EC sub-field, else None."""
    for s in (norm_name, norm_alt):
        if "emergency" not in s:
            continue
        if "phone" in s or "number" in s:
            return "phone"
        if "relationship" in s:
            return "relationship"
        # Default: name field
        return "name"
    return None


# ---------------------------------------------------------------------------
# Special-field resolvers
# ---------------------------------------------------------------------------

def _resolve_combined_csz(
    pdf_field_name: str, pdf_field_alt: str, profile: dict, today: date | None
) -> dict:
    city = _resolve_and_format(profile, "addresses.home.city", today) or ""
    state = _resolve_and_format(profile, "addresses.home.state_code", today) or ""
    zip_code = _resolve_and_format(profile, "addresses.home.postal_code", today) or ""

    if not any([city, state, zip_code]):
        return _make_result(
            pdf_field_name, pdf_field_alt, None, "none",
            "no match: combined city/state/zip — no address data in profile",
        )

    value = f"{city}, {state} {zip_code}".strip(", ")
    confidence = "high" if all([city, state, zip_code]) else "medium"
    return _make_result(
        pdf_field_name, pdf_field_alt, value, confidence,
        "combined city/state/zip → addresses.home.{city,state_code,postal_code}",
    )


def _resolve_mailing_if_different(
    pdf_field_name: str, pdf_field_alt: str, profile: dict
) -> dict:
    """Return 'skip' result when mailing == home address."""
    mailing = profile.get("addresses", {}).get("mailing", {})
    is_same = bool(mailing.get("same_as") or mailing.get("same_as_profile"))
    if is_same:
        return _make_result(
            pdf_field_name, pdf_field_alt, None, "none",
            "mailing address same as home — field left blank (if-different field)",
            notes=["Mailing = home: field intentionally left blank."],
        )
    # Mailing differs — fall through to regular synonym lookup
    return None  # type: ignore[return-value]


def _resolve_today_date(
    pdf_field_name: str, pdf_field_alt: str, today: date | None
) -> dict:
    value = _fmt.format_today(today)
    return _make_result(
        pdf_field_name, pdf_field_alt, value, "high",
        "signature date → today's date",
    )


def _resolve_emergency_contact(
    pdf_field_name: str, pdf_field_alt: str,
    profile: dict, index: dict,
    ec_subfield: str,  # 'name', 'phone', 'relationship'
    today: date | None,
) -> dict:
    ec = _ec.get_emergency_contact(profile, index, priority=1)
    if not ec:
        return _make_result(
            pdf_field_name, pdf_field_alt, None, "none",
            "no emergency contact defined in profile",
        )
    if ec_subfield == "name":
        value = ec["name"]
        source = f"emergency contact (priority 1) → {ec.get('profile_id') or ec.get('type')} name"
    elif ec_subfield == "phone":
        value = ec["phone"]
        source = f"emergency contact (priority 1) → {ec.get('profile_id') or ec.get('type')} phone"
    else:  # relationship
        value = ec["relationship_label"]
        source = f"emergency contact (priority 1) → relationship_label"

    if value is None:
        return _make_result(
            pdf_field_name, pdf_field_alt, None, "none",
            f"emergency contact found but {ec_subfield} is null",
        )
    return _make_result(
        pdf_field_name, pdf_field_alt, value, "high", source,
        notes=[f"EC: {ec.get('name')} ({ec.get('relationship_label')})"],
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_PCP_PREFIX = "external_entities.primary_care_physician."
_GENERIC_TO_PCP = {
    "phone":     _PCP_PREFIX + "phone",
    "telephone": _PCP_PREFIX + "phone",
    "fax":       _PCP_PREFIX + "fax",
    "name":      _PCP_PREFIX + "name",
    "address":   _PCP_PREFIX + "address.street_1",
}
_PCP_HINT_SCORE = 0.8
_PCP_SUPPRESS_PATHS = {"contact.primary_phone", "contact.work_phone"}


def map_pdf_field(
    pdf_field_name: str,
    pdf_field_alt: str,
    resolved_profile: dict,
    index: dict,
    today: date | None = None,
    section_hint: str | None = None,
) -> dict:
    """Map a PDF field to a profile value.

    Returns a result dict with keys:
        pdf_field_name, pdf_field_alt, value, confidence, source,
        alternatives, notes

    Never returns None — unmatched fields have confidence='none' and value=None.
    """
    norm_name = _normalize(pdf_field_name)
    norm_alt = _normalize(pdf_field_alt) if pdf_field_alt else ""

    # ------------------------------------------------------------------
    # 1. Special-field resolvers (run before synonym lookup)
    # ------------------------------------------------------------------

    # Emergency contact
    ec_subfield = _is_emergency_contact_field(norm_name, norm_alt)
    if ec_subfield:
        return _resolve_emergency_contact(
            pdf_field_name, pdf_field_alt, resolved_profile, index, ec_subfield, today
        )

    # Combined city/state/zip
    if _is_combined_city_state_zip(norm_name, norm_alt):
        return _resolve_combined_csz(pdf_field_name, pdf_field_alt, resolved_profile, today)

    # "Mailing address (if different)"
    if _is_mailing_if_different(norm_name, norm_alt):
        result = _resolve_mailing_if_different(pdf_field_name, pdf_field_alt, resolved_profile)
        if result is not None:
            return result
        # result is None → mailing differs, fall through to synonym lookup

    # Signature-adjacent date field (today's date injection)
    if _is_signature_date(norm_name, norm_alt):
        return _resolve_today_date(pdf_field_name, pdf_field_alt, today)

    # ------------------------------------------------------------------
    # 2. Synonym lookup
    # ------------------------------------------------------------------
    synonyms = _load_synonyms()
    best_by_path: dict[str, dict] = {}
    profile_id = resolved_profile.get("profile_id")

    for raw_label in (pdf_field_name, pdf_field_alt):
        if not raw_label:
            continue
        norm = _normalize(raw_label)
        if not norm:
            continue

        for token, dot_path in synonyms.items():
            score = _score_match(token, norm)
            # Discard scores below the weak threshold — they are noise, not matches.
            if score < _WEAK_MATCH_THRESHOLD:
                continue
            value = _resolve_and_format(resolved_profile, dot_path, today)
            if value is None:
                continue
            # Skip candidates blocked by context rules.
            if not _is_permitted_by_context(dot_path, profile_id, norm_name, norm_alt):
                continue

            existing = best_by_path.get(dot_path)
            if existing is None or score > existing["score"]:
                best_by_path[dot_path] = {
                    "token": token,
                    "dot_path": dot_path,
                    "value": value,
                    "score": round(score, 4),
                }

    # ------------------------------------------------------------------
    # 3. Section-hint: inject PCP candidates for generic field labels
    # ------------------------------------------------------------------
    if section_hint == "pcp":
        pcp_path = _GENERIC_TO_PCP.get(norm_name) or _GENERIC_TO_PCP.get(norm_alt)
        if pcp_path:
            pcp_val = _resolve_and_format(resolved_profile, pcp_path, today)
            if pcp_val is not None:
                existing = best_by_path.get(pcp_path)
                if existing is None or _PCP_HINT_SCORE > existing["score"]:
                    best_by_path[pcp_path] = {
                        "token": norm_name,
                        "dot_path": pcp_path,
                        "value": pcp_val,
                        "score": _PCP_HINT_SCORE,
                    }
                # Suppress patient contact fields when PCP candidate is strong enough
                pcp_max = max(
                    (c["score"] for c in best_by_path.values()
                     if c["dot_path"].startswith(_PCP_PREFIX)),
                    default=0.0,
                )
                if pcp_max >= 0.3:
                    for path in list(best_by_path.keys()):
                        if path in _PCP_SUPPRESS_PATHS:
                            del best_by_path[path]

    if not best_by_path:
        return _make_result(
            pdf_field_name, pdf_field_alt, None, "none",
            f"no match for field '{pdf_field_name}' / alt '{pdf_field_alt}'",
        )

    scored = sorted(best_by_path.values(), key=lambda c: c["score"], reverse=True)
    best = scored[0]
    rest = scored[1:]

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

    return _make_result(
        pdf_field_name, pdf_field_alt,
        best["value"], confidence,
        f"{best['token']} → {best['dot_path']}",
        alternatives, notes,
    )
