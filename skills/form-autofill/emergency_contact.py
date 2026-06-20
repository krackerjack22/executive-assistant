"""Resolve emergency contact data from a profile's emergency_contacts list."""

from __future__ import annotations

from formatters import format_phone


def get_emergency_contact(
    profile: dict,
    index: dict,
    priority: int = 1,
) -> dict | None:
    """Return emergency contact info for the given priority (1=primary, 2=secondary).

    Returns a dict with keys: name, phone, relationship_label, type, profile_id.
    Returns None if no entry exists at that priority or the data cannot be resolved.
    """
    ec_list = profile.get("emergency_contacts")
    if not ec_list:
        return None

    ec = next((e for e in ec_list if e.get("priority") == priority), None)
    if ec is None:
        return None

    ec_type = ec.get("type")

    if ec_type == "profile":
        ec_profile_id = ec.get("profile_id")
        if not ec_profile_id:
            return None
        # Lazy import to avoid circular dependency
        from lib import profile_loader as _pl
        try:
            ec_profile = _pl.load_profile(ec_profile_id)
        except Exception:
            return None
        name = ec_profile.get("identity", {}).get("legal_name")
        raw_phone = ec_profile.get("contact", {}).get("primary_phone")
        phone = format_phone(raw_phone) if raw_phone else None
        return {
            "name": name,
            "phone": phone,
            "relationship_label": ec.get("relationship_label"),
            "type": "profile",
            "profile_id": ec_profile_id,
        }

    if ec_type == "external_person":
        key = ec.get("external_person_key")
        ep = (profile.get("external_persons") or {}).get(key)
        if not ep:
            return None
        name = ep.get("legal_name")
        raw_phone = (ep.get("contact") or {}).get("primary_phone")
        phone = format_phone(raw_phone) if raw_phone else None
        return {
            "name": name,
            "phone": phone,
            "relationship_label": ec.get("relationship_label"),
            "type": "external_person",
            "profile_id": None,
        }

    return None
