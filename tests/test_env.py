"""Tests for lib/env.py — env-var resolution, default fallback, missing-dir error."""

import os
import pytest
from pathlib import Path
from unittest.mock import patch

from lib import env


def test_default_profiles_dir_exists():
    """Default path should resolve to an existing directory (symlink or real)."""
    # Only pass if the user has the profiles dir set up
    p = env.profiles_dir()
    assert p.exists(), f"Profiles dir not found: {p}"


def test_env_var_override(tmp_path):
    """EXEC_ASSISTANT_PROFILES_DIR env var should override the default."""
    with patch.dict(os.environ, {"EXEC_ASSISTANT_PROFILES_DIR": str(tmp_path)}):
        p = env.profiles_dir()
        assert p == tmp_path.resolve()


def test_missing_dir_raises(tmp_path):
    """FileNotFoundError with actionable message when dir doesn't exist."""
    nonexistent = tmp_path / "does_not_exist"
    with patch.dict(os.environ, {"EXEC_ASSISTANT_PROFILES_DIR": str(nonexistent)}):
        with pytest.raises(FileNotFoundError) as exc_info:
            env.profiles_dir()
    assert "EXEC_ASSISTANT_PROFILES_DIR" in str(exc_info.value)


def test_profiles_dir_source_env_var(tmp_path):
    """profiles_dir_source returns 'env_var' when env var is set."""
    with patch.dict(os.environ, {"EXEC_ASSISTANT_PROFILES_DIR": str(tmp_path)}):
        assert env.profiles_dir_source() == "env_var"


def test_profiles_dir_source_default():
    """profiles_dir_source returns 'default' when env var is not set."""
    env_copy = {k: v for k, v in os.environ.items() if k != "EXEC_ASSISTANT_PROFILES_DIR"}
    with patch.dict(os.environ, env_copy, clear=True):
        assert env.profiles_dir_source() == "default"


def test_config_returns_dict_when_missing():
    """config() returns {} when config file is absent. Never raises."""
    with patch.dict(os.environ, {"EXEC_ASSISTANT_CONFIG_PATH": "/tmp/__nonexistent_config__.json"}):
        result = env.config()
        assert result == {}


def test_cli_exits_nonzero_on_missing_dir(tmp_path, capsys):
    """CLI (via preflight) exits non-zero with actionable message when profiles dir missing."""
    import subprocess, sys
    nonexistent = tmp_path / "no_such_dir"
    result = subprocess.run(
        [sys.executable, "skills/pdf-form-autofill/autofill.py", "--check-env"],
        cwd=str(Path(__file__).resolve().parent.parent),
        env={**os.environ, "EXEC_ASSISTANT_PROFILES_DIR": str(nonexistent)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "PROFILES_DIR_MISSING" in result.stdout
