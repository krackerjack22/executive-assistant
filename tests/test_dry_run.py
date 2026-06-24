"""Test dry-run behavior, commit refusal, --commit-unsafe bypass, and --resolve stub."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import acroform
from lib import profile_loader as pl

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
SYNTHETIC_PDF = FIXTURE_DIR / "synthetic_form.pdf"
AMBIGUOUS_PDF = FIXTURE_DIR / "ambiguous_form.pdf"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
AUTOFILL_CLI = PROJECT_ROOT / "skills" / "pdf-form-autofill" / "autofill.py"


@pytest.fixture(scope="module")
def tyler_profile():
    return pl.load_profile("tyler_combs")


@pytest.fixture(scope="module")
def index():
    return pl.load_index()


# ---------------------------------------------------------------------------
# Dry-run core behaviour
# ---------------------------------------------------------------------------

def test_dry_run_no_file_written(tyler_profile, index, tmp_path):
    output = tmp_path / "should_not_exist.pdf"
    result = acroform.fill(
        template_pdf=SYNTHETIC_PDF,
        profile=tyler_profile,
        index=index,
        output_pdf=output,
        dry_run=True,
    )
    assert result["mode"] == "dry_run"
    assert not output.exists(), "Dry run must not write any file"


def test_dry_run_all_fields_have_source(tyler_profile, index, tmp_path):
    """Every field in the dry-run result has a non-empty source explanation."""
    result = acroform.fill(
        template_pdf=SYNTHETIC_PDF,
        profile=tyler_profile,
        index=index,
        output_pdf=tmp_path / "dummy.pdf",
        dry_run=True,
    )
    for f in result["fields"]:
        assert isinstance(f["source"], str) and len(f["source"]) > 0, (
            f"Field '{f['name']}' has empty source explanation"
        )


def test_dry_run_counts(tyler_profile, index, tmp_path):
    """filled_count + skipped_count == total fields."""
    result = acroform.fill(
        template_pdf=SYNTHETIC_PDF,
        profile=tyler_profile,
        index=index,
        output_pdf=tmp_path / "dummy.pdf",
        dry_run=True,
    )
    total = len(result["fields"])
    assert result["filled_count"] + result["skipped_count"] == total


def test_dry_run_result_has_low_count_key(tyler_profile, index, tmp_path):
    result = acroform.fill(
        template_pdf=SYNTHETIC_PDF,
        profile=tyler_profile,
        index=index,
        output_pdf=tmp_path / "dummy.pdf",
        dry_run=True,
    )
    assert "low_count" in result


# ---------------------------------------------------------------------------
# CLI: default dry-run
# ---------------------------------------------------------------------------

def test_dry_run_cli_no_file(tmp_path):
    """CLI dry-run (default) must not write any file."""
    output = tmp_path / "cli_out.pdf"
    result = subprocess.run(
        [
            sys.executable,
            str(AUTOFILL_CLI),
            "--template", str(SYNTHETIC_PDF),
            "--profile", "tyler_combs",
            "--output", str(output),
            "--json-output",
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert not output.exists(), "Dry-run CLI must not write output file"


def test_dry_run_cli_json_has_low_count(tmp_path):
    """CLI dry-run JSON output includes low_count key."""
    output = tmp_path / "cli_out.pdf"
    proc = subprocess.run(
        [
            sys.executable,
            str(AUTOFILL_CLI),
            "--template", str(SYNTHETIC_PDF),
            "--profile", "tyler_combs",
            "--output", str(output),
            "--json-output",
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert "low_count" in data


# ---------------------------------------------------------------------------
# CLI: --commit success (synthetic form has no low-confidence fields)
# ---------------------------------------------------------------------------

def test_commit_cli_writes_file(tmp_path):
    """CLI --commit writes the output file when no low-confidence fields exist."""
    output = tmp_path / "cli_committed.pdf"
    result = subprocess.run(
        [
            sys.executable,
            str(AUTOFILL_CLI),
            "--template", str(SYNTHETIC_PDF),
            "--profile", "tyler_combs",
            "--output", str(output),
            "--commit",
            "--json-output",
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert output.exists(), "Committed output PDF should exist"


def test_commit_cli_json_has_mode_filled(tmp_path):
    """--commit JSON output has mode=filled."""
    output = tmp_path / "cli_committed.pdf"
    proc = subprocess.run(
        [
            sys.executable,
            str(AUTOFILL_CLI),
            "--template", str(SYNTHETIC_PDF),
            "--profile", "tyler_combs",
            "--output", str(output),
            "--commit",
            "--json-output",
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["mode"] == "filled"


# ---------------------------------------------------------------------------
# CLI: --commit REFUSED when low-confidence fields present
# ---------------------------------------------------------------------------

def test_commit_refused_on_low_confidence(tmp_path):
    """--commit exits 1 when ambiguous_form.pdf has a low-confidence field."""
    output = tmp_path / "refused.pdf"
    proc = subprocess.run(
        [
            sys.executable,
            str(AUTOFILL_CLI),
            "--template", str(AMBIGUOUS_PDF),
            "--profile", "tyler_combs",
            "--output", str(output),
            "--commit",
            "--json-output",
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1, (
        f"Expected exit 1 (commit refused), got {proc.returncode}. "
        f"stdout: {proc.stdout[:500]}"
    )
    assert not output.exists(), "File must not be written when commit is refused"


def test_commit_refusal_message_mentions_unsafe(tmp_path):
    """Refusal message hints at --commit-unsafe."""
    output = tmp_path / "refused.pdf"
    proc = subprocess.run(
        [
            sys.executable,
            str(AUTOFILL_CLI),
            "--template", str(AMBIGUOUS_PDF),
            "--profile", "tyler_combs",
            "--output", str(output),
            "--commit",
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1
    assert "commit-unsafe" in proc.stderr, (
        f"Refusal message should mention --commit-unsafe. stderr: {proc.stderr}"
    )


# ---------------------------------------------------------------------------
# CLI: --commit-unsafe bypasses low-confidence refusal
# ---------------------------------------------------------------------------

def test_commit_unsafe_writes_file_despite_low(tmp_path):
    """--commit-unsafe writes the file even when low-confidence fields are present."""
    output = tmp_path / "unsafe_committed.pdf"
    proc = subprocess.run(
        [
            sys.executable,
            str(AUTOFILL_CLI),
            "--template", str(AMBIGUOUS_PDF),
            "--profile", "tyler_combs",
            "--output", str(output),
            "--commit-unsafe",
            "--json-output",
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"stderr: {proc.stderr}"
    assert output.exists(), "--commit-unsafe must write the output file"
    assert output.stat().st_size > 0


def test_commit_unsafe_json_mode_is_filled(tmp_path):
    """--commit-unsafe JSON output shows mode=filled."""
    output = tmp_path / "unsafe_committed.pdf"
    proc = subprocess.run(
        [
            sys.executable,
            str(AUTOFILL_CLI),
            "--template", str(AMBIGUOUS_PDF),
            "--profile", "tyler_combs",
            "--output", str(output),
            "--commit-unsafe",
            "--json-output",
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["mode"] == "filled"


def test_commit_unsafe_json_still_shows_low_count(tmp_path):
    """--commit-unsafe result still reports accurate low_count (doesn't hide it)."""
    output = tmp_path / "unsafe_committed.pdf"
    proc = subprocess.run(
        [
            sys.executable,
            str(AUTOFILL_CLI),
            "--template", str(AMBIGUOUS_PDF),
            "--profile", "tyler_combs",
            "--output", str(output),
            "--commit-unsafe",
            "--json-output",
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["low_count"] >= 1, (
        "low_count should still be reported accurately after --commit-unsafe"
    )


# ---------------------------------------------------------------------------
# CLI: --resolve (real interactive flow)
# ---------------------------------------------------------------------------
# Note: tests for the interactive stdin prompt loop require a real terminal
# and cannot be automated in pytest. Those paths must be verified manually.

def test_resolve_with_no_low_fields_commits_directly(tmp_path):
    """--resolve on a form with zero low-confidence fields commits directly, exit 0."""
    output = tmp_path / "resolved.pdf"
    proc = subprocess.run(
        [
            sys.executable,
            str(AUTOFILL_CLI),
            "--template", str(SYNTHETIC_PDF),
            "--profile", "tyler_combs",
            "--output", str(output),
            "--resolve",
            "--json-output",
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"Expected exit 0, got {proc.returncode}. stderr: {proc.stderr}"
    assert output.exists(), "--resolve with no low fields should write the output file"
    combined = proc.stdout + proc.stderr
    assert "committing directly" in combined.lower() or "filled" in combined.lower()


def test_resolve_without_template_errors():
    """--resolve without --template exits non-zero with a usage error."""
    proc = subprocess.run(
        [
            sys.executable,
            str(AUTOFILL_CLI),
            "--resolve",
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0, (
        "--resolve without --template must exit with an error"
    )


# ---------------------------------------------------------------------------
# CLI: --missing-mode skip
# ---------------------------------------------------------------------------

def test_missing_mode_skip_exits_zero(tmp_path):
    """--missing-mode skip exits 0 with the synthetic form."""
    output = tmp_path / "skip_out.pdf"
    proc = subprocess.run(
        [
            sys.executable,
            str(AUTOFILL_CLI),
            "--template", str(SYNTHETIC_PDF),
            "--profile", "tyler_combs",
            "--output", str(output),
            "--missing-mode", "skip",
            "--json-output",
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"Expected exit 0. stderr: {proc.stderr}"


def test_missing_mode_skip_still_fills_confident_fields(tmp_path):
    """--missing-mode skip fills high-confidence fields; output JSON shows mode=filled."""
    output = tmp_path / "skip_out.pdf"
    proc = subprocess.run(
        [
            sys.executable,
            str(AUTOFILL_CLI),
            "--template", str(SYNTHETIC_PDF),
            "--profile", "tyler_combs",
            "--output", str(output),
            "--missing-mode", "skip",
            "--json-output",
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["mode"] == "filled"
    high_filled = [
        f for f in data["fields"]
        if f.get("confidence") == "high" and f.get("mapped_value")
    ]
    assert len(high_filled) > 0, "At least one high-confidence field should be filled"


# ---------------------------------------------------------------------------
# Note: --missing-mode interview requires an interactive terminal.
# It cannot be fully tested in pytest. Test manually by running:
#   python3 skills/form-autofill/autofill.py --template <pdf> --missing-mode interview
# The non-tty guard exits 1 cleanly when stdin is not a terminal.
# ---------------------------------------------------------------------------

def test_missing_mode_interview_exits_on_non_tty(tmp_path):
    """--missing-mode interview exits 1 with a clear message when stdin is not a tty."""
    output = tmp_path / "interview_out.pdf"
    proc = subprocess.run(
        [
            sys.executable,
            str(AUTOFILL_CLI),
            "--template", str(SYNTHETIC_PDF),
            "--profile", "tyler_combs",
            "--output", str(output),
            "--missing-mode", "interview",
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        input="",
    )
    assert proc.returncode == 1, (
        f"Expected exit 1 for non-tty interview mode, got {proc.returncode}"
    )
    assert "interactive terminal" in proc.stderr.lower() or "tty" in proc.stderr.lower()
