"""Test dry-run: output contains every fillable field with source, no file written."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

import acroform
from lib import profile_loader as pl

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
SYNTHETIC_PDF = FIXTURE_DIR / "synthetic_form.pdf"


@pytest.fixture(scope="module")
def tyler_profile():
    return pl.load_profile("tyler_combs")


@pytest.fixture(scope="module")
def index():
    return pl.load_index()


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


def test_dry_run_cli_no_file(tmp_path):
    """CLI dry-run (default) must not write any file."""
    project_root = Path(__file__).resolve().parent.parent
    output = tmp_path / "cli_out.pdf"
    result = subprocess.run(
        [
            sys.executable,
            "skills/form-autofill/autofill.py",
            "--template", str(SYNTHETIC_PDF),
            "--profile", "tyler_combs",
            "--output", str(output),
            "--json-output",
        ],
        cwd=str(project_root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert not output.exists(), "Dry-run CLI must not write output file"


def test_commit_cli_writes_file(tmp_path):
    """CLI --commit writes the output file."""
    project_root = Path(__file__).resolve().parent.parent
    output = tmp_path / "cli_committed.pdf"
    result = subprocess.run(
        [
            sys.executable,
            "skills/form-autofill/autofill.py",
            "--template", str(SYNTHETIC_PDF),
            "--profile", "tyler_combs",
            "--output", str(output),
            "--commit",
            "--json-output",
        ],
        cwd=str(project_root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert output.exists(), "Committed output PDF should exist"
