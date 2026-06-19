"""Env-var resolution and path canonicalization for executive-assistant."""

from __future__ import annotations

import json
import os
from pathlib import Path


_ENV_VAR_PROFILES = "EXEC_ASSISTANT_PROFILES_DIR"
_ENV_VAR_CONFIG = "EXEC_ASSISTANT_CONFIG_PATH"
_DEFAULT_PROFILES_DIR = Path.home() / "Assets_Library" / "Executive-Assistant" / "profiles"
_DEFAULT_CONFIG_PATH = Path.home() / ".config" / "executive-assistant" / "config.json"


def profiles_dir() -> Path:
    """Return resolved absolute Path to profiles directory.

    Resolution order: EXEC_ASSISTANT_PROFILES_DIR env var → ~/Assets_Library/... default.
    Raises FileNotFoundError with an actionable message if neither exists.
    """
    raw = os.environ.get(_ENV_VAR_PROFILES, "").strip()
    if raw:
        p = Path(raw).expanduser().resolve()
        source = "env_var"
    else:
        p = _DEFAULT_PROFILES_DIR.expanduser().resolve()
        source = "default"

    if not p.exists():
        raise FileNotFoundError(
            f"Profiles directory not found at '{p}' (source: {source}). "
            f"Create it or set {_ENV_VAR_PROFILES} to the correct path."
        )
    return p


def profiles_dir_source() -> str:
    """Return 'env_var' or 'default' depending on which resolution path is used."""
    raw = os.environ.get(_ENV_VAR_PROFILES, "").strip()
    return "env_var" if raw else "default"


def config() -> dict:
    """Load optional config.json. Returns {} if file missing or unreadable. Never raises."""
    raw = os.environ.get(_ENV_VAR_CONFIG, "").strip()
    if raw:
        cfg_path = Path(raw).expanduser().resolve()
    else:
        cfg_path = _DEFAULT_CONFIG_PATH.expanduser().resolve()

    try:
        with cfg_path.open() as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
