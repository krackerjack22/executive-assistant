"""Round-trip test: fill synthetic_form.pdf with Tyler's profile, verify populated fields."""

from __future__ import annotations

import pytest
from pathlib import Path

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


def test_synthetic_pdf_exists():
    assert SYNTHETIC_PDF.exists(), (
        f"Synthetic test PDF not found. Run: /usr/bin/python3 tests/make_test_pdf.py"
    )


def test_dry_run_returns_fields(tyler_profile, index):
    result = acroform.fill(
        template_pdf=SYNTHETIC_PDF,
        profile=tyler_profile,
        index=index,
        output_pdf=SYNTHETIC_PDF.parent / "dummy_output.pdf",
        dry_run=True,
    )
    assert result["mode"] == "dry_run"
    assert isinstance(result["fields"], list)
    assert len(result["fields"]) > 0


def test_tyler_name_filled(tyler_profile, index):
    result = acroform.fill(
        template_pdf=SYNTHETIC_PDF,
        profile=tyler_profile,
        index=index,
        output_pdf=SYNTHETIC_PDF.parent / "dummy_output.pdf",
        dry_run=True,
    )
    field_map = {f["name"]: f["mapped_value"] for f in result["fields"]}
    assert field_map.get("patient name") == "Tyler Combs"


def test_tyler_city_filled(tyler_profile, index):
    result = acroform.fill(
        template_pdf=SYNTHETIC_PDF,
        profile=tyler_profile,
        index=index,
        output_pdf=SYNTHETIC_PDF.parent / "dummy_output.pdf",
        dry_run=True,
    )
    field_map = {f["name"]: f["mapped_value"] for f in result["fields"]}
    assert field_map.get("city") == "Lake Oswego"


def test_tyler_insurance_filled(tyler_profile, index):
    result = acroform.fill(
        template_pdf=SYNTHETIC_PDF,
        profile=tyler_profile,
        index=index,
        output_pdf=SYNTHETIC_PDF.parent / "dummy_output.pdf",
        dry_run=True,
    )
    field_map = {f["name"]: f["mapped_value"] for f in result["fields"]}
    assert "Regence" in (field_map.get("insurance company") or "")


def test_commit_writes_file(tyler_profile, index, tmp_path):
    output = tmp_path / "tyler_filled.pdf"
    result = acroform.fill(
        template_pdf=SYNTHETIC_PDF,
        profile=tyler_profile,
        index=index,
        output_pdf=output,
        dry_run=False,
    )
    assert result["mode"] == "filled"
    assert output.exists()
    assert output.stat().st_size > 0


def test_fiona_uses_tyler_address(index, tmp_path):
    """Fiona's form fill should use Tyler's address (inherited)."""
    fiona = pl.load_profile("fiona_combs")
    result = acroform.fill(
        template_pdf=SYNTHETIC_PDF,
        profile=fiona,
        index=index,
        output_pdf=tmp_path / "fiona_filled.pdf",
        dry_run=True,
    )
    field_map = {f["name"]: f["mapped_value"] for f in result["fields"]}
    assert field_map.get("city") == "Lake Oswego"


def test_fiona_insurance_shows_tyler_carrier(index, tmp_path):
    """Fiona's form should show Tyler's insurance carrier (inherited)."""
    fiona = pl.load_profile("fiona_combs")
    result = acroform.fill(
        template_pdf=SYNTHETIC_PDF,
        profile=fiona,
        index=index,
        output_pdf=tmp_path / "fiona_filled.pdf",
        dry_run=True,
    )
    field_map = {f["name"]: f["mapped_value"] for f in result["fields"]}
    assert "Regence" in (field_map.get("insurance company") or "")
