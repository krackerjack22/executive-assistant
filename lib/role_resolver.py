"""Walk the relationship graph to resolve form-role keywords to profiles or external persons."""

from __future__ import annotations

from lib import profile_loader as _pl


def resolve(
    active_profile: dict,
    role_keyword: str,
    all_profiles: dict,
    role_map: dict,
    strict: bool = True,
) -> dict | None:
    """Resolve a role keyword for the given active_profile.

    Args:
        active_profile: fully resolved profile dict (from profile_loader.load_profile).
        role_keyword: e.g. "father", "mother", "subscriber".
        all_profiles: mapping of profile_id → raw profile dict.
        role_map: index["role_resolution_map"].
        strict: if True (default), skip relationships tagged "unverified".

    Returns:
        Profile dict or external_persons entry dict, or None if no match found.
    """
    entry = role_map.get(role_keyword)
    if entry is None:
        return None

    # Special case: resolves_to_field (e.g. subscriber_profile_id)
    if "resolves_to_field" in entry:
        field_path = entry["resolves_to_field"]
        parts = field_path.split(".")
        val = active_profile
        for part in parts:
            if not isinstance(val, dict):
                return None
            val = val.get(part)
        if val is None:
            return None
        # val is a profile_id
        if val == active_profile.get("profile_id"):
            return active_profile
        return all_profiles.get(val)

    # Standard lookup_chain
    lookup_chain = entry.get("lookup_chain", [])
    for step in lookup_chain:
        result = _resolve_step(active_profile, step, all_profiles, strict)
        if result is not None:
            return result

    return None


def _resolve_step(
    active_profile: dict,
    step: dict,
    all_profiles: dict,
    strict: bool,
) -> dict | None:
    """Resolve a single lookup_chain step. Returns first match or None."""

    # external_persons_tag lookup
    if "external_persons_tag" in step:
        tag = step["external_persons_tag"]
        return _lookup_external_person(active_profile, tag)

    # target_role lookup (walks relationship graph)
    if "target_role" in step:
        target_role = step["target_role"]
        gender_filter = (step.get("filter") or {}).get("gender")
        target_tag = step.get("target_tag")

        for rel in active_profile.get("relationships", []):
            if strict and "unverified" in rel.get("tags", []):
                continue
            # "reciprocal" = what the target IS to the active profile (e.g. parent_of)
            # "role"       = what the active profile IS to the target (e.g. child_of)
            if rel.get("reciprocal") != target_role:
                continue
            to_id = rel.get("to")
            if to_id not in all_profiles:
                continue
            candidate = all_profiles[to_id]
            # Gender filter
            if gender_filter:
                cand_gender = (candidate.get("identity") or {}).get("gender", "")
                if cand_gender != gender_filter:
                    continue
            # target_tag filter (e.g. "primary_emergency_contact_for_*")
            if target_tag:
                rel_tags = rel.get("tags", [])
                pattern = target_tag.rstrip("*")
                if not any(t.startswith(pattern) for t in rel_tags):
                    continue
            return candidate

    return None


def _lookup_external_person(profile: dict, tag: str) -> dict | None:
    """Find the first external_persons entry whose tags list contains the given tag."""
    for _slug, ep in (profile.get("external_persons") or {}).items():
        if _slug.startswith("_"):
            continue
        if isinstance(ep, dict) and tag in (ep.get("tags") or []):
            return ep
    return None
