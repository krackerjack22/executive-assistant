"""Load and resolve profile JSON files with inheritance expansion."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Optional

from lib import env as _env


def _profiles_path() -> Path:
    return _env.profiles_dir()


def load_index() -> dict:
    """Load profiles_index.json."""
    p = _profiles_path() / "profiles_index.json"
    with p.open() as f:
        return json.load(f)


def list_profiles() -> list[dict]:
    """Return minimal {profile_id, legal_name, status} per registered profile."""
    index = load_index()
    result = []
    for pid, meta in index.get("profiles", {}).items():
        result.append({
            "profile_id": pid,
            "legal_name": meta.get("legal_name"),
            "status": meta.get("status"),
        })
    return result


def _load_raw(profile_id: str) -> dict:
    index = load_index()
    if profile_id not in index.get("profiles", {}):
        raise FileNotFoundError(f"Profile '{profile_id}' not in registry.")
    fname = index["profiles"][profile_id]["file"]
    p = _profiles_path() / fname
    with p.open() as f:
        return json.load(f)


def _resolve_address_same_as(addr_block: dict, profile_addresses: dict, seen: set | None = None) -> dict:
    """Resolve a single-level same_as pointer within the same profile."""
    if seen is None:
        seen = set()
    same_as = addr_block.get("same_as")
    if not same_as or same_as in seen:
        return addr_block
    seen.add(same_as)
    target = profile_addresses.get(same_as, {})
    return _resolve_address_same_as(target, profile_addresses, seen)


def _resolve_addresses(profile: dict, all_raws: dict[str, dict]) -> dict:
    """Expand same_as and same_as_profile in addresses block."""
    addresses = profile.get("addresses", {})
    resolved = {}
    for role, block in addresses.items():
        if role.startswith("_"):
            resolved[role] = block
            continue
        if not isinstance(block, dict):
            resolved[role] = block
            continue
        if "same_as" in block:
            resolved[role] = _resolve_address_same_as(block, addresses)
        elif "same_as_profile" in block:
            src_id = block["same_as_profile"]
            src_profile = all_raws.get(src_id, {})
            src_home = src_profile.get("addresses", {}).get("home", {})
            resolved[role] = _resolve_address_same_as(src_home, src_profile.get("addresses", {}))
        else:
            resolved[role] = block
    return resolved


def _resolve_insurance(profile: dict, all_raws: dict[str, dict]) -> dict:
    """Expand inherit_from_subscriber in insurance.primary."""
    insurance = copy.deepcopy(profile.get("insurance", {}))
    primary = insurance.get("primary")
    if not isinstance(primary, dict):
        return insurance

    if primary.get("inherit_from_subscriber"):
        sub_id = primary.get("subscriber_profile_id")
        if sub_id and sub_id != profile.get("profile_id"):
            sub_raw = all_raws.get(sub_id, {})
            sub_ins = sub_raw.get("insurance", {}).get("primary", {})
            # Copy all fields from subscriber that are not present locally
            merged = copy.deepcopy(sub_ins)
            # Preserve local overrides (subscriber_relationship_to_patient etc.)
            for k, v in primary.items():
                if not k.startswith("_"):
                    merged[k] = v
            insurance["primary"] = merged

    return insurance


def _load_all_raws(index: dict) -> dict[str, dict]:
    """Load all profile raw dicts keyed by profile_id."""
    raws = {}
    pdir = _profiles_path()
    for pid, meta in index.get("profiles", {}).items():
        fname = meta["file"]
        try:
            with (pdir / fname).open() as f:
                raws[pid] = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass
    return raws


def load_profile(profile_id: str) -> dict:
    """Load and fully resolve a profile.

    Resolves same_as / same_as_profile address pointers and inherit_from_subscriber
    insurance inheritance. Returns a flat, self-contained dict ready for field_mapper.
    Raises FileNotFoundError if profile_id not in registry.
    """
    index = load_index()
    all_raws = _load_all_raws(index)

    if profile_id not in all_raws:
        raise FileNotFoundError(f"Profile '{profile_id}' not found.")

    profile = copy.deepcopy(all_raws[profile_id])

    # Resolve addresses
    profile["addresses"] = _resolve_addresses(profile, all_raws)

    # Resolve insurance
    profile["insurance"] = _resolve_insurance(profile, all_raws)

    # Attach the index for resolvers that need it
    profile["_index"] = index

    return profile
