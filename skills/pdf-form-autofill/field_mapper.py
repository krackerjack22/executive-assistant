"""Map PDF field names/alt text to resolved profile values via synonym lookup."""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

import formatters as _fmt
import emergency_contact as _ec

_SYNONYMS_PATH = Path(__file__).parent / "data" / "synonyms.json"
_synonyms_cache: dict | None = None


def clear_synonyms_cache() -> None:
    """Invalidate the in-process synonyms cache (used after learning saves)."""
    global _synonyms_cache
    _synonyms_cache = None

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
    """Return False when a context rule blocks this dot_path for the given field label.

    Rules with no profile_id (null) are universal — they apply to all profiles.
    block_if_keywords_present takes priority: if any blocking keyword appears in
    the field label, the rule immediately denies regardless of permit keywords.
    """
    for rule in _load_context_rules():
        rule_profile = rule.get("profile_id")
        # Universal rules (null profile_id) apply to everyone; others must match.
        if rule_profile is not None and rule_profile != profile_id:
            continue
        if rule.get("dot_path") != dot_path:
            continue
        combined = f"{norm_name} {norm_alt}"
        # Block keywords: any match → immediate deny.
        block_kws = rule.get("block_if_keywords_present", [])
        if block_kws and any(kw.lower() in combined for kw in block_kws):
            return False
        # Permit keywords: at least one must be present.
        permit_kws = rule.get("keywords_that_permit_use", [])
        if permit_kws:
            if any(kw.lower() in combined for kw in permit_kws):
                return True
            return False
        return True
    return True


def _load_synonyms() -> dict:
    global _synonyms_cache
    if _synonyms_cache is None:
        with _SYNONYMS_PATH.open() as f:
            raw = json.load(f)
        flat: dict[str, str] = {}
        learned_section: dict | None = None

        # First pass: all curated sections (non-underscore, non-learned)
        for key, val in raw.items():
            if key.startswith("_"):
                continue
            if key == "learned":
                learned_section = val
                continue
            if isinstance(val, dict):
                for token, path in val.items():
                    flat[token.lower()] = path

        # Second pass: learned section overrides curated (processed last)
        if learned_section:
            for token, entry in learned_section.items():
                if not isinstance(entry, dict):
                    continue
                dot_path = entry.get("dot_path")
                if not dot_path:
                    continue
                tok_lower = token.lower()
                if tok_lower in flat:
                    print(
                        f"[synonyms] WARNING: learned token '{token}' shadows "
                        f"curated entry '{flat[tok_lower]}'",
                        file=sys.stderr,
                    )
                flat[tok_lower] = dot_path

        _synonyms_cache = flat
    return _synonyms_cache


def _normalize(text: str) -> str:
    """Lowercase, strip non-alpha/digit/space, collapse whitespace."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _resolve_path(profile: dict, dot_path: str) -> str | None:
    """Walk a dot-notation path through a profile dict. Handles list indices.

    Returns str or None.  Numeric path segments (e.g. 'siblings.0.first_name')
    are treated as list indices.
    """
    parts = dot_path.split(".")
    cur: object = profile
    for part in parts:
        if cur is None:
            return None
        if isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
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

    Guards applied:
    - Minimum-length: tokens < 3 chars require exact match (too ambiguous as substrings).
    - Word-boundary: single-word tokens must not be preceded or followed by a letter
      (prevents "name" matching "Vietnamese", "city" matching "electricity", etc.).
    """
    if not norm:
        return 0.0
    if token == norm:
        return 1.0
    # Minimum-length guard: very short tokens only win on exact match (already checked).
    if len(token) < 3:
        return 0.0
    # Single-word tokens: must not be preceded or followed by another letter.
    # Digits/spaces/start/end are all fine (e.g. "zip" in "13zip" → ok).
    if " " not in token:
        if not re.search(r"(?<![a-z])" + re.escape(token) + r"(?![a-z])", norm):
            return 0.0
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
    **extra,
) -> dict:
    result = {
        "pdf_field_name": pdf_field_name,
        "pdf_field_alt": pdf_field_alt,
        "value": value,
        "confidence": confidence,
        "source": source,
        "alternatives": alternatives or [],
        "notes": notes or [],
    }
    result.update(extra)
    return result


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
# Sibling special resolver
# ---------------------------------------------------------------------------

def _is_sibling_field(norm_name: str, norm_alt: str) -> str | None:
    """Return profile subfield key if this looks like a sibling data field, else None."""
    for s in (norm_name, norm_alt):
        if "sibling" not in s:
            continue
        if "last" in s:
            return "last_name"
        if "first" in s:
            return "first_name"
        if "school" in s:
            return "school_name"
        if "grade" in s:
            return "grade_or_year"
        return "first_name"
    return None


def _resolve_sibling(
    pdf_field_name: str,
    pdf_field_alt: str,
    subfield: str,
    profile: dict,
    today: date | None,
) -> dict:
    """Return the first sibling's data for the requested subfield."""
    siblings = profile.get("siblings", [])
    for i, sib in enumerate(siblings):
        val = sib.get(subfield)
        if val is not None:
            return _make_result(
                pdf_field_name, pdf_field_alt, str(val), "medium",
                f"siblings[{i}].{subfield}",
            )
    if siblings:
        return _make_result(
            pdf_field_name, pdf_field_alt, None, "none",
            f"no value for siblings[*].{subfield} in profile",
        )
    return _make_result(
        pdf_field_name, pdf_field_alt, None, "none",
        "no siblings array in profile",
    )


# ---------------------------------------------------------------------------
# Race / ethnicity checkbox special resolver
# ---------------------------------------------------------------------------

_RACE_CHECKBOX_LABELS: frozenset = frozenset({
    "asian",
    "black",
    "white",
    "native american or alaska native",
    "native hawaiian or other pacific islander",
    "african american",
    "other african",
    "other black",
    "burundian",
    "eritrean",
    "ethiopian",
    "somali",
    "alaska native",
    "burns paiute tribe",
    "confederated tribes of siletz indians",
    "confederated tribes of the grand ronde community of oregon",
    "confederated tribes of the umatilla indian reservation",
    "confederated tribes of the coos lower umpqua and",
    "klamath tribes",
    "caribbean islands",
})

_ETHNICITY_CHECKBOX_LABELS: frozenset = frozenset({
    "hispanic or latino",
    "is your child of hispanic or latino origin",
})


def _is_race_ethnicity_field(norm_name: str, norm_alt: str) -> bool:
    """True when the field is a race or ethnicity checkbox/question."""
    for raw in (norm_name, norm_alt):
        s = re.sub(r"^\d+\s*", "", raw).strip()
        if s in _RACE_CHECKBOX_LABELS:
            return True
        if s in _ETHNICITY_CHECKBOX_LABELS:
            return True
        if any(t in s for t in _ETHNICITY_CHECKBOX_LABELS):
            return True
    return False


def _resolve_race_ethnicity(
    pdf_field_name: str,
    pdf_field_alt: str,
    norm_name: str,
    norm_alt: str,
    profile: dict,
) -> dict:
    """Fill race/ethnicity checkboxes from demographics.race / demographics.ethnicity_hispanic_or_latino."""
    demographics = profile.get("demographics") or {}
    if not demographics:
        return _make_result(
            pdf_field_name, pdf_field_alt, None, "none",
            "demographics not in profile — add demographics.race / demographics.ethnicity_hispanic_or_latino",
        )
    race = (demographics.get("race") or "").lower()
    eth_hispanic = demographics.get("ethnicity_hispanic_or_latino")

    for raw in (norm_name, norm_alt):
        s = re.sub(r"^\d+\s*", "", raw).strip()

        # Ethnicity question
        if s in _ETHNICITY_CHECKBOX_LABELS or any(t in s for t in _ETHNICITY_CHECKBOX_LABELS):
            if eth_hispanic is None:
                return _make_result(
                    pdf_field_name, pdf_field_alt, None, "none",
                    "demographics.ethnicity_hispanic_or_latino not set",
                )
            value = "Yes" if eth_hispanic else "No"
            return _make_result(
                pdf_field_name, pdf_field_alt, value, "high",
                f"demographics.ethnicity_hispanic_or_latino → {value}",
            )

        # Race checkbox
        if s in _RACE_CHECKBOX_LABELS:
            if not race:
                return _make_result(
                    pdf_field_name, pdf_field_alt, None, "none",
                    "demographics.race not set",
                )
            is_match = (s in race) or (race in s)
            value = "Yes" if is_match else "Off"
            return _make_result(
                pdf_field_name, pdf_field_alt, value, "high",
                f"demographics.race ({race!r}) → {value} for '{s}'",
            )

    return _make_result(
        pdf_field_name, pdf_field_alt, None, "none",
        "race/ethnicity data insufficient to determine checkbox value",
    )


# ---------------------------------------------------------------------------
# Language field special resolver
# ---------------------------------------------------------------------------

_LANGUAGE_PREF_KEYS: frozenset = frozenset({"prefer", "preferred", "receive", "communication"})
_LANGUAGE_FIRST_KEYS: frozenset = frozenset({"first", "learned"})
_LANGUAGE_HOME_KEYS: frozenset = frozenset({"home", "primarily", "frequently", "most", "speak"})


def _is_language_field(norm_name: str, norm_alt: str) -> str | None:
    """Return the demographics dot-path to resolve if this is a language field, else None."""
    for s in (norm_name, norm_alt):
        if "language" not in s:
            continue
        if any(k in s for k in _LANGUAGE_PREF_KEYS):
            return "demographics.preferred_school_communication_language"
        if any(k in s for k in _LANGUAGE_FIRST_KEYS):
            return "demographics.first_language_learned"
        if any(k in s for k in _LANGUAGE_HOME_KEYS):
            return "demographics.home_language"
        return "demographics.primary_language"
    return None


def _resolve_language_field(
    pdf_field_name: str,
    pdf_field_alt: str,
    dot_path: str,
    profile: dict,
) -> dict:
    value = _resolve_and_format(profile, dot_path, None)
    if value is None:
        return _make_result(
            pdf_field_name, pdf_field_alt, None, "none",
            f"{dot_path} not set in profile",
        )
    return _make_result(
        pdf_field_name, pdf_field_alt, value, "high",
        f"language field → {dot_path}",
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

    # Race / ethnicity checkboxes
    if _is_race_ethnicity_field(norm_name, norm_alt):
        return _resolve_race_ethnicity(
            pdf_field_name, pdf_field_alt, norm_name, norm_alt, resolved_profile
        )

    # Language fields (labels containing "language" with contextual keywords)
    lang_path = _is_language_field(norm_name, norm_alt)
    if lang_path:
        return _resolve_language_field(pdf_field_name, pdf_field_alt, lang_path, resolved_profile)

    # Sibling fields
    sibling_subfield = _is_sibling_field(norm_name, norm_alt)
    if sibling_subfield:
        return _resolve_sibling(
            pdf_field_name, pdf_field_alt, sibling_subfield, resolved_profile, today
        )

    # ------------------------------------------------------------------
    # 2. Synonym lookup
    # ------------------------------------------------------------------
    synonyms = _load_synonyms()
    best_by_path: dict[str, dict] = {}
    profile_id = resolved_profile.get("profile_id")
    vault_failed: list[dict] = []
    # Tracks synonyms that matched but whose profile value is null.
    # Key: dot_path, value: best-scoring candidate for that path.
    profile_null: dict[str, dict] = {}

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

            # Vault-reference paths: lazy dereference via bw CLI
            if dot_path.startswith("vault_references."):
                raw_pointer = _resolve_path(resolved_profile, dot_path)
                if raw_pointer is None:
                    continue
                from lib import vault as _vault
                try:
                    item_name, field_name = _vault.resolve_pointer(raw_pointer)
                    secret = _vault.get(item_name, field_name)
                    if secret is None:
                        continue
                    value = secret
                except _vault.VaultLocked as exc:
                    vault_failed.append({
                        "dot_path": dot_path,
                        "item": str(raw_pointer),
                        "error": "locked",
                        "score": round(score, 4),
                        "detail": str(exc),
                    })
                    continue
                except _vault.VaultBinaryMissing as exc:
                    vault_failed.append({
                        "dot_path": dot_path,
                        "item": str(raw_pointer),
                        "error": "no_binary",
                        "score": round(score, 4),
                        "detail": str(exc),
                    })
                    continue
                except _vault.VaultItemNotFound as exc:
                    vault_failed.append({
                        "dot_path": dot_path,
                        "item": str(raw_pointer),
                        "error": "not_found",
                        "score": round(score, 4),
                        "detail": str(exc),
                    })
                    continue
                except _vault.VaultError as exc:
                    vault_failed.append({
                        "dot_path": dot_path,
                        "item": str(raw_pointer),
                        "error": "error",
                        "score": round(score, 4),
                        "detail": str(exc),
                    })
                    continue
            else:
                value = _resolve_and_format(resolved_profile, dot_path, today)
                if value is None:
                    # Synonym matched but profile has no value — track it so the
                    # caller can surface it as a targeted "please add this" prompt.
                    if _is_permitted_by_context(dot_path, profile_id, norm_name, norm_alt):
                        existing_null = profile_null.get(dot_path)
                        if existing_null is None or score > existing_null["score"]:
                            profile_null[dot_path] = {
                                "token": token,
                                "dot_path": dot_path,
                                "score": round(score, 4),
                            }
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
    # 2b. Vault-failure fallback: if no non-vault candidates matched but vault
    #     fields were attempted, return a vault-specific confidence='none' result.
    # ------------------------------------------------------------------
    if not best_by_path and vault_failed:
        best_vf = max(vault_failed, key=lambda x: x["score"])
        error_type = best_vf["error"]
        dot_path_vf = best_vf["dot_path"]
        item_vf = best_vf["item"]
        if error_type == "locked":
            source_vf = f"{dot_path_vf} → bw item '{item_vf}' (locked)"
            notes_vf = [
                "Vault locked: run 'bw unlock' and set BW_SESSION to dereference."
            ]
        elif error_type == "no_binary":
            source_vf = f"{dot_path_vf} → bw item '{item_vf}' (bw not installed)"
            notes_vf = ["Bitwarden CLI not found. Install with: brew install bitwarden-cli"]
        elif error_type == "not_found":
            source_vf = f"{dot_path_vf} → bw item '{item_vf}' not found"
            notes_vf = [f"Bitwarden item '{item_vf}' not found. Check your vault."]
        else:
            source_vf = f"{dot_path_vf} → bw item '{item_vf}' (error)"
            notes_vf = [f"Vault lookup failed: {best_vf.get('detail', '')}"]
        return _make_result(
            pdf_field_name, pdf_field_alt, None, "none", source_vf, notes=notes_vf
        )

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
        # Profile-null: synonym matched but the profile has no value for that path.
        # Return a distinct result so callers can prompt the user for the missing data
        # rather than silently skipping or treating it as an unknown field.
        if profile_null:
            best_null = max(profile_null.values(), key=lambda c: c["score"])
            return _make_result(
                pdf_field_name, pdf_field_alt, None, "none",
                f"profile null: {best_null['token']} → {best_null['dot_path']}",
                notes=[
                    f"Field maps to '{best_null['dot_path']}' but profile has no value — "
                    "add it to the profile or supply it during interview."
                ],
                profile_null=True,
                profile_null_path=best_null["dot_path"],
            )
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
