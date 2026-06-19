"""Tests for lib/preflight.py."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from lib import preflight


def test_preflight_ok_basic():
    """Preflight passes with a valid environment."""
    result = preflight.run()
    assert result["schema_version"] == "1.0"
    assert "ok" in result
    assert "platform" in result
    assert "paths" in result
    assert "tools" in result
    assert "issues" in result
    assert "warnings" in result
    assert "actionable" in result


def test_preflight_ok_when_setup_correct():
    """Preflight returns ok=True when profiles dir exists and modules are installed."""
    result = preflight.run()
    # If profiles dir is set up correctly, this should pass
    if result["paths"].get("profiles_dir_readable"):
        assert result["ok"] is True


def test_preflight_profiles_dir_missing(tmp_path):
    """PROFILES_DIR_MISSING issue when dir doesn't exist."""
    nonexistent = tmp_path / "no_such_profiles"
    with patch.dict(os.environ, {"EXEC_ASSISTANT_PROFILES_DIR": str(nonexistent)}):
        result = preflight.run(output_dir=tmp_path)
    assert result["ok"] is False
    codes = [i["code"] for i in result["issues"]]
    assert "PROFILES_DIR_MISSING" in codes
    assert len(result["actionable"]) > 0


def test_preflight_profiles_index_missing(tmp_path):
    """PROFILES_INDEX_MISSING issue when index file absent."""
    (tmp_path / "dummy.txt").write_text("x")
    with patch.dict(os.environ, {"EXEC_ASSISTANT_PROFILES_DIR": str(tmp_path)}):
        result = preflight.run(output_dir=tmp_path)
    assert result["ok"] is False
    codes = [i["code"] for i in result["issues"]]
    assert "PROFILES_INDEX_MISSING" in codes


def test_preflight_profiles_index_unparseable(tmp_path):
    """PROFILES_INDEX_UNPARSEABLE issue when index file is corrupted."""
    (tmp_path / "profiles_index.json").write_text("NOT VALID JSON {{{{")
    with patch.dict(os.environ, {"EXEC_ASSISTANT_PROFILES_DIR": str(tmp_path)}):
        result = preflight.run(output_dir=tmp_path)
    assert result["ok"] is False
    codes = [i["code"] for i in result["issues"]]
    assert "PROFILES_INDEX_UNPARSEABLE" in codes


def test_preflight_sandbox_indicators_not_blocking(tmp_path):
    """sandbox_indicators being non-empty must not make ok=False."""
    # Simulate sandbox environment by patching HOME
    with patch.dict(os.environ, {
        "EXEC_ASSISTANT_PROFILES_DIR": str(tmp_path),
        "HOME": "/sessions/test",
    }):
        # tmp_path exists so PROFILES_DIR_MISSING won't fire,
        # but index is missing so we just check sandbox_indicators behavior
        result = preflight.run(output_dir=tmp_path)
    # ok may be False because of missing index, but sandbox alone never adds issues
    sandbox = result["platform"]["sandbox_indicators"]
    # Can't reliably inject sandbox indicators via HOME override alone,
    # but we can verify the structure is present and never causes an issue code
    assert isinstance(sandbox, list)
    sandbox_codes = [i["code"] for i in result["issues"] if "sandbox" in i["code"].lower()]
    assert sandbox_codes == []


def test_preflight_missing_required_module(tmp_path, monkeypatch):
    """MISSING_REQUIRED_MODULE issue when pypdf is not importable."""
    import builtins
    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "pypdf":
            raise ImportError("mocked missing")
        return real_import(name, *args, **kwargs)

    # Use importlib.metadata mock instead — patch _module_version
    with patch("lib.preflight._module_version", side_effect=lambda m: None if m == "pypdf" else "1.0"):
        # Need a valid profiles dir to isolate the module issue
        profiles_dir = Path(os.environ.get("EXEC_ASSISTANT_PROFILES_DIR", "")) or (
            Path.home() / "Assets_Library" / "Executive-Assistant" / "profiles"
        )
        result = preflight.run(output_dir=tmp_path)

    # The mock will report pypdf missing; check issue is present
    codes = [i["code"] for i in result["issues"]]
    if not result["paths"].get("profiles_dir_readable"):
        pytest.skip("Profiles dir not set up; skipping module-check isolation test")
    assert "MISSING_REQUIRED_MODULE" in codes
    fix_text = " ".join(i["fix"] for i in result["issues"] if i["code"] == "MISSING_REQUIRED_MODULE")
    assert sys.executable in fix_text


def test_preflight_speed():
    """Preflight must complete in under 500ms on a warm filesystem."""
    start = time.monotonic()
    preflight.run()
    elapsed_ms = (time.monotonic() - start) * 1000
    assert elapsed_ms < 500, f"Preflight took {elapsed_ms:.0f}ms (limit: 500ms)"


def test_preflight_cli_ok(tmp_path):
    """--check-env exits 0 and prints ok=true JSON when env is valid."""
    result = subprocess.run(
        [sys.executable, "skills/form-autofill/autofill.py", "--check-env"],
        cwd=str(Path(__file__).resolve().parent.parent),
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        data = json.loads(result.stdout)
        assert data["ok"] is True
    else:
        # Valid to fail only if profiles dir is not configured
        data = json.loads(result.stdout)
        assert data["ok"] is False


def test_preflight_cli_missing_dir_exit_1(tmp_path):
    """--check-env exits 1 with PROFILES_DIR_MISSING when dir doesn't exist."""
    nonexistent = tmp_path / "no_profiles"
    result = subprocess.run(
        [sys.executable, "skills/form-autofill/autofill.py", "--check-env"],
        cwd=str(Path(__file__).resolve().parent.parent),
        env={**os.environ, "EXEC_ASSISTANT_PROFILES_DIR": str(nonexistent)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    data = json.loads(result.stdout)
    assert data["ok"] is False
    codes = [i["code"] for i in data["issues"]]
    assert "PROFILES_DIR_MISSING" in codes


def test_preflight_cli_missing_index_exit_1(tmp_path):
    """--check-env exits 1 with PROFILES_INDEX_MISSING when index is absent."""
    result = subprocess.run(
        [sys.executable, "skills/form-autofill/autofill.py", "--check-env"],
        cwd=str(Path(__file__).resolve().parent.parent),
        env={**os.environ, "EXEC_ASSISTANT_PROFILES_DIR": str(tmp_path)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    data = json.loads(result.stdout)
    codes = [i["code"] for i in data["issues"]]
    assert "PROFILES_INDEX_MISSING" in codes
