"""Render addresses in various formats and detect subject-vs-third-party fields."""

from __future__ import annotations

ADDRESS_FORMATS = [
    "street_only",           # "5910 Rockwood Ct"
    "city_st_zip_comma",     # "Lake Oswego, OR 97035"
    "city_st_zip_nocomma",   # "Lake Oswego OR 97035"
    "single_line",           # "5910 Rockwood Ct, Lake Oswego, OR 97035"
    "parts_separated",       # dict: {street, city, state, zip}
]


def render(address: dict, fmt: str) -> "str | dict":
    """Render an address dict in the requested format.

    Args:
        address: dict with keys street_1, city, state_code, postal_code, etc.
        fmt: one of ADDRESS_FORMATS.

    Returns:
        str for all formats except 'parts_separated', which returns a dict.
    """
    if fmt not in ADDRESS_FORMATS:
        raise ValueError(f"Unknown format '{fmt}'. Choose from {ADDRESS_FORMATS}.")

    street = (address.get("street_1") or "").strip()
    street2 = (address.get("street_2") or "").strip()
    city = (address.get("city") or "").strip()
    state = (address.get("state_code") or "").strip()
    zip_code = (address.get("postal_code") or "").strip()

    full_street = f"{street} {street2}".strip() if street2 else street

    if fmt == "street_only":
        return full_street

    if fmt == "city_st_zip_comma":
        return f"{city}, {state} {zip_code}"

    if fmt == "city_st_zip_nocomma":
        return f"{city} {state} {zip_code}"

    if fmt == "single_line":
        parts = [p for p in [full_street, city, f"{state} {zip_code}".strip()] if p]
        return ", ".join(parts)

    if fmt == "parts_separated":
        return {
            "street": full_street,
            "city": city,
            "state": state,
            "zip": zip_code,
        }


def is_subject_address(field_label: str, index: dict) -> bool:
    """Return True if the field label refers to the profile holder's address.

    Consults index.address_role_keywords. Case-insensitive substring match.
    Returns False for third-party entity addresses (physician, school, etc.).
    """
    label_lower = field_label.lower()
    ark = index.get("address_role_keywords", {})

    # Explicit "do not substitute" keywords take priority
    for kw in ark.get("do_not_substitute_profile_address", []):
        if kw.lower() in label_lower:
            return False

    # Explicit "use external entity" keywords
    for kw in ark.get("use_external_entity_address", {}):
        if kw.lower() in label_lower:
            return False

    # "Use profile home address" keywords
    for kw in ark.get("use_profile_home_address", []):
        if kw.lower() in label_lower:
            return True

    return False
