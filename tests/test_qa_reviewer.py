"""Tests for qa_reviewer.py — prompt building, JSON parsing, API error handling."""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_field(name: str, value: str | None, skipped: bool = False) -> dict:
    return {
        "name": name,
        "mapped_value": value,
        "skipped": skipped,
        "confidence": "high" if value else "none",
    }


_SAMPLE_FIELDS = [
    _make_field("First Name", "Charlotte"),
    _make_field("Last Name", "Combs"),
    _make_field("Sibling First Name", "Charlotte"),   # intentional wrong-person data for QA
    _make_field("Skipped Field", None, skipped=True),
]

_SAMPLE_PROFILE = {
    "profile_id": "charlotte_combs",
    "identity": {"legal_name": "Charlotte Jean Combs"},
    "siblings": [
        {
            "first_name": "Fiona",
            "last_name": "Combs",
            "relationship": "biological_sibling",
            "grade_or_year": "5th",
            "school_name": "River Grove Elementary",
        }
    ],
    "emergency_contacts": [
        {
            "priority": 1,
            "type": "profile",
            "profile_id": "tyler_combs",
            "relationship_label": "Father",
        }
    ],
}


# ---------------------------------------------------------------------------
# _profile_summary
# ---------------------------------------------------------------------------

class TestProfileSummary:
    def test_returns_name(self):
        import qa_reviewer
        summary = qa_reviewer._profile_summary(_SAMPLE_PROFILE)
        assert "Charlotte Jean Combs" in summary

    def test_includes_sibling_info(self):
        import qa_reviewer
        summary = qa_reviewer._profile_summary(_SAMPLE_PROFILE)
        assert "Fiona" in summary
        assert "biological_sibling" in summary

    def test_includes_emergency_contact(self):
        import qa_reviewer
        summary = qa_reviewer._profile_summary(_SAMPLE_PROFILE)
        assert "tyler_combs" in summary
        assert "Father" in summary

    def test_minimal_profile_uses_profile_id(self):
        import qa_reviewer
        summary = qa_reviewer._profile_summary({"profile_id": "test_id"})
        assert "test_id" in summary

    def test_no_siblings_or_contacts(self):
        import qa_reviewer
        summary = qa_reviewer._profile_summary(
            {"identity": {"legal_name": "John Doe"}}
        )
        assert "John Doe" in summary
        assert "siblings" not in summary


# ---------------------------------------------------------------------------
# _build_prompt
# ---------------------------------------------------------------------------

class TestBuildPrompt:
    def test_contains_subject(self):
        import qa_reviewer
        prompt = qa_reviewer._build_prompt(_SAMPLE_FIELDS, "FORM TEXT", "Charlotte")
        assert "Charlotte" in prompt

    def test_contains_form_text(self):
        import qa_reviewer
        prompt = qa_reviewer._build_prompt(_SAMPLE_FIELDS, "HEADER SECTION", "subject")
        assert "HEADER SECTION" in prompt

    def test_filled_fields_numbered(self):
        import qa_reviewer
        prompt = qa_reviewer._build_prompt(_SAMPLE_FIELDS, "", "subject")
        assert "[001]" in prompt
        assert "First Name" in prompt

    def test_skipped_fields_excluded(self):
        import qa_reviewer
        prompt = qa_reviewer._build_prompt(_SAMPLE_FIELDS, "", "subject")
        assert "Skipped Field" not in prompt

    def test_none_value_fields_excluded(self):
        import qa_reviewer
        fields = [_make_field("Empty", None)]
        prompt = qa_reviewer._build_prompt(fields, "", "subject")
        assert "Empty" not in prompt

    def test_form_text_truncated(self):
        import qa_reviewer
        long_text = "x" * 5000
        prompt = qa_reviewer._build_prompt([], long_text, "subject")
        assert "truncated" in prompt

    def test_form_text_not_truncated_when_short(self):
        import qa_reviewer
        short_text = "short form text"
        prompt = qa_reviewer._build_prompt([], short_text, "subject")
        assert "truncated" not in prompt

    def test_json_schema_in_prompt(self):
        import qa_reviewer
        prompt = qa_reviewer._build_prompt([], "", "subject")
        assert '"issues"' in prompt
        assert "field_name" in prompt


# ---------------------------------------------------------------------------
# _parse_issues
# ---------------------------------------------------------------------------

class TestParseIssues:
    def test_valid_json_with_issues(self):
        import qa_reviewer
        raw = json.dumps({
            "issues": [
                {
                    "field_name": "90School",
                    "current_value": "Lakeridge Middle School",
                    "suggested_value": "River Grove Elementary",
                    "reason": "Field is in sibling section.",
                    "confidence": "high",
                }
            ]
        })
        result = qa_reviewer._parse_issues(raw)
        assert len(result) == 1
        assert result[0]["field_name"] == "90School"

    def test_empty_issues_list(self):
        import qa_reviewer
        raw = json.dumps({"issues": []})
        result = qa_reviewer._parse_issues(raw)
        assert result == []

    def test_json_with_preamble(self):
        import qa_reviewer
        raw = 'Here is the result:\n{"issues": [{"field_name": "X", "current_value": "a", "suggested_value": "b", "reason": "r", "confidence": "high"}]}'
        result = qa_reviewer._parse_issues(raw)
        assert len(result) == 1
        assert result[0]["field_name"] == "X"

    def test_completely_invalid_returns_empty(self):
        import qa_reviewer
        result = qa_reviewer._parse_issues("not json at all")
        assert result == []

    def test_json_missing_issues_key_returns_empty(self):
        import qa_reviewer
        result = qa_reviewer._parse_issues('{"something": "else"}')
        assert result == []


# ---------------------------------------------------------------------------
# review_fills — API key missing
# ---------------------------------------------------------------------------

class TestReviewFillsMissingKey:
    def test_raises_runtime_error_when_no_api_key(self, tmp_path, monkeypatch):
        import qa_reviewer
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        dummy_pdf = tmp_path / "form.pdf"
        dummy_pdf.write_bytes(b"%PDF-1.4 fake")
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            qa_reviewer.review_fills([], dummy_pdf, {})


# ---------------------------------------------------------------------------
# review_fills — anthropic not installed
# ---------------------------------------------------------------------------

class TestReviewFillsNoPackage:
    def test_raises_runtime_error_when_anthropic_missing(self, tmp_path, monkeypatch):
        import qa_reviewer
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake")
        dummy_pdf = tmp_path / "form.pdf"
        dummy_pdf.write_bytes(b"%PDF-1.4 fake")
        # Temporarily hide the anthropic package from the importer
        real_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else None
        import builtins
        original = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "anthropic":
                raise ImportError("No module named 'anthropic'")
            return original(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        with pytest.raises(RuntimeError, match="anthropic package not installed"):
            qa_reviewer.review_fills([], dummy_pdf, {})


# ---------------------------------------------------------------------------
# review_fills — mocked API call
# ---------------------------------------------------------------------------

class TestReviewFillsMockedApi:
    def _make_mock_client(self, response_text: str):
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text=response_text)]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_msg
        return mock_client

    def test_returns_issues_from_api(self, tmp_path, monkeypatch):
        import qa_reviewer
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake")
        dummy_pdf = tmp_path / "form.pdf"
        dummy_pdf.write_bytes(b"%PDF-1.4 fake")

        api_response = json.dumps({
            "issues": [
                {
                    "field_name": "90School",
                    "current_value": "Lakeridge Middle School",
                    "suggested_value": "River Grove Elementary",
                    "reason": "Field is inside SIBLING INFORMATION section.",
                    "confidence": "high",
                }
            ]
        })
        mock_client = self._make_mock_client(api_response)

        import anthropic as _anthropic_mod
        with patch.object(_anthropic_mod, "Anthropic", return_value=mock_client):
            result = qa_reviewer.review_fills(
                _SAMPLE_FIELDS, dummy_pdf, _SAMPLE_PROFILE
            )

        assert len(result) == 1
        assert result[0]["field_name"] == "90School"
        assert result[0]["suggested_value"] == "River Grove Elementary"

    def test_returns_empty_list_when_no_issues(self, tmp_path, monkeypatch):
        import qa_reviewer
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake")
        dummy_pdf = tmp_path / "form.pdf"
        dummy_pdf.write_bytes(b"%PDF-1.4 fake")

        api_response = json.dumps({"issues": []})
        mock_client = self._make_mock_client(api_response)

        import anthropic as _anthropic_mod
        with patch.object(_anthropic_mod, "Anthropic", return_value=mock_client):
            result = qa_reviewer.review_fills(
                _SAMPLE_FIELDS, dummy_pdf, _SAMPLE_PROFILE
            )

        assert result == []

    def test_passes_correct_model_to_api(self, tmp_path, monkeypatch):
        import qa_reviewer
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake")
        dummy_pdf = tmp_path / "form.pdf"
        dummy_pdf.write_bytes(b"%PDF-1.4 fake")

        mock_client = self._make_mock_client('{"issues": []}')
        import anthropic as _anthropic_mod
        with patch.object(_anthropic_mod, "Anthropic", return_value=mock_client):
            qa_reviewer.review_fills(
                [], dummy_pdf, {}, model="claude-sonnet-4-6"
            )

        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["model"] == "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# extract_form_text
# ---------------------------------------------------------------------------

class TestExtractFormText:
    def test_returns_string_for_nonexistent_pdf(self, tmp_path):
        import qa_reviewer
        result = qa_reviewer.extract_form_text(tmp_path / "no_such.pdf")
        assert isinstance(result, str)

    def test_returns_empty_string_on_error(self, tmp_path):
        import qa_reviewer
        bad_pdf = tmp_path / "bad.pdf"
        bad_pdf.write_bytes(b"not a pdf")
        result = qa_reviewer.extract_form_text(bad_pdf)
        assert isinstance(result, str)
