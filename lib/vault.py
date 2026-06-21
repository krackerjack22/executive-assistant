"""Bitwarden CLI integration for vault-backed profile fields."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Optional

_SUBPROCESS_TIMEOUT_SEC = 5
_bw_cache: dict[str, dict] = {}


class VaultError(Exception):
    pass


class VaultLocked(VaultError):
    pass


class VaultBinaryMissing(VaultError):
    pass


class VaultItemNotFound(VaultError):
    pass


def is_available() -> dict:
    """Returns {'bw_binary': bool, 'session_token': bool}."""
    return {
        "bw_binary": shutil.which("bw") is not None,
        "session_token": bool(os.environ.get("BW_SESSION")),
    }


def resolve_pointer(pointer: object) -> tuple[str, str]:
    """Normalize a vault_references entry to (item_name, field_name).

    Accepts a string (defaults field to 'notes') or a dict
    {bw_item: str, bw_field: str}. Raises ValueError on malformed input.
    """
    if isinstance(pointer, str):
        return pointer, "notes"
    if isinstance(pointer, dict):
        item = pointer.get("bw_item")
        field = pointer.get("bw_field", "notes")
        if not item:
            raise ValueError(
                f"vault pointer dict missing 'bw_item': {pointer!r}"
            )
        return str(item), str(field)
    raise ValueError(
        f"vault pointer must be str or dict, got {type(pointer).__name__}: {pointer!r}"
    )


def get(item_name: str, field: str = "notes") -> Optional[str]:
    """Return the resolved vault value.

    Raises:
        VaultBinaryMissing: bw binary not found.
        VaultLocked: BW_SESSION not set or vault is locked/expired.
        VaultItemNotFound: item does not exist in the vault.
        VaultError: other bw errors (bad JSON, timeout, etc.).
    """
    item_data = _cached_bw_call(item_name)
    return _extract_field(item_data, field)


def _extract_field(item_data: dict, field: str) -> Optional[str]:
    """Extract a named field value from a parsed BW item dict."""
    if field == "notes":
        return item_data.get("notes") or None

    # Check named custom fields
    for f in item_data.get("fields") or []:
        if (f.get("name") or "").lower() == field.lower():
            val = f.get("value")
            return str(val) if val is not None else None

    # Login sub-fields
    login = item_data.get("login") or {}
    if field == "username":
        return login.get("username") or None
    if field == "password":
        return login.get("password") or None

    return None


def _cached_bw_call(item_name: str) -> dict:
    """Subprocess call to bw, cached per item_name within this process."""
    if item_name in _bw_cache:
        return _bw_cache[item_name]

    bw_path = shutil.which("bw")
    if not bw_path:
        raise VaultBinaryMissing(
            "Bitwarden CLI not found. Install with: brew install bitwarden-cli"
        )

    session = os.environ.get("BW_SESSION")
    if not session:
        raise VaultLocked(
            "BW_SESSION not set. Run 'bw unlock' and export BW_SESSION."
        )

    cmd = [bw_path, "get", "item", item_name, "--session", session]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired:
        raise VaultLocked(
            f"bw subprocess timed out after {_SUBPROCESS_TIMEOUT_SEC}s. Try again."
        )

    if proc.returncode != 0:
        stderr = (proc.stderr or "").lower()
        if any(kw in stderr for kw in ("not logged in", "vault is locked", "invalid session")):
            raise VaultLocked(
                f"Vault is locked or session expired: {proc.stderr.strip()}"
            )
        if any(kw in stderr for kw in ("not found", "no items", "no item")):
            raise VaultItemNotFound(
                f"Item '{item_name}' not found in vault."
            )
        raise VaultError(
            f"bw returned exit code {proc.returncode}: {(proc.stderr or '').strip()}"
        )

    try:
        item_data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise VaultError(f"bw response unparseable: {exc}") from exc

    _bw_cache[item_name] = item_data
    return item_data


def clear_cache() -> None:
    """Invalidate the per-process item cache. Used in tests."""
    _bw_cache.clear()
