"""Tests for lib/vault.py — Bitwarden CLI integration."""

from __future__ import annotations

import json
import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from lib import vault


@pytest.fixture(autouse=True)
def _clear_vault_cache():
    """Reset the per-process cache before each test."""
    vault.clear_cache()
    yield
    vault.clear_cache()


# ---------------------------------------------------------------------------
# is_available
# ---------------------------------------------------------------------------

def test_is_available_returns_two_key_dict():
    result = vault.is_available()
    assert isinstance(result, dict)
    assert "bw_binary" in result
    assert "session_token" in result
    assert isinstance(result["bw_binary"], bool)
    assert isinstance(result["session_token"], bool)


# ---------------------------------------------------------------------------
# resolve_pointer
# ---------------------------------------------------------------------------

def test_resolve_pointer_accepts_string():
    item, field = vault.resolve_pointer("tyler-ssn")
    assert item == "tyler-ssn"
    assert field == "notes"


def test_resolve_pointer_accepts_dict():
    item, field = vault.resolve_pointer({"bw_item": "tyler-dl-or", "bw_field": "number"})
    assert item == "tyler-dl-or"
    assert field == "number"


def test_resolve_pointer_dict_defaults_field_to_notes():
    item, field = vault.resolve_pointer({"bw_item": "some-item"})
    assert field == "notes"


def test_resolve_pointer_rejects_list():
    with pytest.raises(ValueError, match="str or dict"):
        vault.resolve_pointer([1, 2])


def test_resolve_pointer_rejects_none():
    with pytest.raises(ValueError):
        vault.resolve_pointer(None)


def test_resolve_pointer_rejects_dict_without_bw_item():
    with pytest.raises(ValueError, match="bw_item"):
        vault.resolve_pointer({"bw_field": "notes"})


# ---------------------------------------------------------------------------
# get / _cached_bw_call — error paths (mocked)
# ---------------------------------------------------------------------------

def test_get_raises_vault_binary_missing_when_bw_absent(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: None)
    with pytest.raises(vault.VaultBinaryMissing):
        vault.get("some-item")


def test_get_raises_vault_locked_when_session_unset(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/bw" if name == "bw" else None)
    monkeypatch.delenv("BW_SESSION", raising=False)
    with pytest.raises(vault.VaultLocked, match="BW_SESSION"):
        vault.get("some-item")


def test_get_raises_vault_locked_on_locked_vault_response(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/bw" if name == "bw" else None)
    monkeypatch.setenv("BW_SESSION", "fake-session-token")

    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "Vault is locked."
    mock_result.stdout = ""

    with patch("subprocess.run", return_value=mock_result):
        with pytest.raises(vault.VaultLocked):
            vault.get("some-item")


def test_get_raises_vault_item_not_found(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/bw" if name == "bw" else None)
    monkeypatch.setenv("BW_SESSION", "fake-session-token")

    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "Not found."
    mock_result.stdout = ""

    with patch("subprocess.run", return_value=mock_result):
        with pytest.raises(vault.VaultItemNotFound):
            vault.get("missing-item")


def test_get_raises_vault_error_on_unparseable_json(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/bw" if name == "bw" else None)
    monkeypatch.setenv("BW_SESSION", "fake-session-token")

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "NOT VALID JSON {{{"
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result):
        with pytest.raises(vault.VaultError, match="unparseable"):
            vault.get("some-item")


def test_subprocess_timeout_raises_vault_locked(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/bw" if name == "bw" else None)
    monkeypatch.setenv("BW_SESSION", "fake-session-token")

    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="bw", timeout=5)):
        with pytest.raises(vault.VaultLocked, match="timed out"):
            vault.get("some-item")


# ---------------------------------------------------------------------------
# Cache behaviour
# ---------------------------------------------------------------------------

def test_cached_bw_call_invokes_subprocess_once(monkeypatch):
    """Two get() calls with same item name → only one subprocess invocation."""
    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/bw" if name == "bw" else None)
    monkeypatch.setenv("BW_SESSION", "fake-session-token")

    item_json = json.dumps({"id": "abc", "name": "tyler-ssn", "notes": "123-45-6789"})
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = item_json
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        v1 = vault.get("tyler-ssn", "notes")
        v2 = vault.get("tyler-ssn", "notes")

    assert v1 == "123-45-6789"
    assert v2 == "123-45-6789"
    assert mock_run.call_count == 1, f"Expected 1 subprocess call, got {mock_run.call_count}"


def test_clear_cache_allows_fresh_subprocess_call(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/bw" if name == "bw" else None)
    monkeypatch.setenv("BW_SESSION", "fake-session-token")

    item_json = json.dumps({"id": "abc", "name": "item", "notes": "value"})
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = item_json
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        vault.get("item")
        vault.clear_cache()
        vault.get("item")

    assert mock_run.call_count == 2


# ---------------------------------------------------------------------------
# Field extraction
# ---------------------------------------------------------------------------

def test_get_extracts_notes_field(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/bw" if name == "bw" else None)
    monkeypatch.setenv("BW_SESSION", "fake-session-token")

    item_json = json.dumps({"notes": "secret-value", "fields": []})
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = item_json
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result):
        assert vault.get("item", "notes") == "secret-value"


def test_get_extracts_custom_field(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/bw" if name == "bw" else None)
    monkeypatch.setenv("BW_SESSION", "fake-session-token")

    item_json = json.dumps({
        "notes": None,
        "fields": [{"name": "number", "value": "DL-12345"}],
    })
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = item_json
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result):
        assert vault.get("item", "number") == "DL-12345"


def test_get_returns_none_for_empty_field(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/bw" if name == "bw" else None)
    monkeypatch.setenv("BW_SESSION", "fake-session-token")

    item_json = json.dumps({"notes": None, "fields": []})
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = item_json
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result):
        assert vault.get("item", "notes") is None


# ---------------------------------------------------------------------------
# unlock_interactive
# ---------------------------------------------------------------------------

def test_unlock_interactive_sets_env_and_saves_file(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/bw" if name == "bw" else None)
    monkeypatch.delenv("BW_SESSION", raising=False)
    vault.clear_cache()

    session_file = tmp_path / ".bw_session"
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "fake-session-token-xyz"

    with patch("subprocess.run", return_value=mock_result):
        token = vault.unlock_interactive(session_file=str(session_file))

    assert token == "fake-session-token-xyz"
    assert os.environ.get("BW_SESSION") == "fake-session-token-xyz"
    assert session_file.read_text() == "fake-session-token-xyz"


def test_unlock_interactive_raises_when_bw_missing(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda name: None)
    with pytest.raises(vault.VaultBinaryMissing):
        vault.unlock_interactive(session_file=str(tmp_path / ".bw_session"))


def test_unlock_interactive_raises_on_empty_token(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/bw" if name == "bw" else None)
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = ""  # empty token = unlock failed

    with patch("subprocess.run", return_value=mock_result):
        with pytest.raises(vault.VaultError, match="bw unlock failed"):
            vault.unlock_interactive(session_file=str(tmp_path / ".bw_session"))


def test_unlock_interactive_raises_on_nonzero_returncode(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/bw" if name == "bw" else None)
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""

    with patch("subprocess.run", return_value=mock_result):
        with pytest.raises(vault.VaultError):
            vault.unlock_interactive(session_file=str(tmp_path / ".bw_session"))


def test_unlock_interactive_clears_cache(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/bw" if name == "bw" else None)
    vault._bw_cache["some-item"] = {"notes": "cached"}

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "new-token"

    with patch("subprocess.run", return_value=mock_result):
        vault.unlock_interactive(session_file=str(tmp_path / ".bw_session"))

    assert "some-item" not in vault._bw_cache
