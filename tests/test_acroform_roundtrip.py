"""Round-trip test: fill synthetic_form.pdf with Tyler's profile, verify populated fields."""

from __future__ import annotations

import pytest
from pathlib import Path

import acroform
from lib import profile_loader as pl

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
SYNTHETIC_PDF = FIXTURE_DIR / "synthetic_form.pdf"
AMBIGUOUS_PDF = FIXTURE_DIR / "ambiguous_form.pdf"


@pytest.fixture(scope="module")
def tyler_profile():
    return pl.load_profile("tyler_combs")


@pytest.fixture(scope="module")
def index():
    return pl.load_index()


def test_synthetic_pdf_exists():
    assert SYNTHETIC_PDF.exists(), (
        "Synthetic test PDF not found. Run: /usr/bin/python3 tests/make_test_pdf.py"
    )


def test_ambiguous_pdf_exists():
    assert AMBIGUOUS_PDF.exists(), (
        "Ambiguous test PDF not found. Run: /usr/bin/python3 tests/make_test_pdf.py"
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


def test_dry_run_result_has_low_count(tyler_profile, index):
    result = acroform.fill(
        template_pdf=SYNTHETIC_PDF,
        profile=tyler_profile,
        index=index,
        output_pdf=SYNTHETIC_PDF.parent / "dummy_output.pdf",
        dry_run=True,
    )
    assert "low_count" in result
    assert isinstance(result["low_count"], int)


def test_dry_run_result_has_skipped_count(tyler_profile, index):
    result = acroform.fill(
        template_pdf=SYNTHETIC_PDF,
        profile=tyler_profile,
        index=index,
        output_pdf=SYNTHETIC_PDF.parent / "dummy_output.pdf",
        dry_run=True,
    )
    assert "skipped_count" in result
    assert isinstance(result["skipped_count"], int)


def test_filled_result_has_low_count(tyler_profile, index, tmp_path):
    output = tmp_path / "tyler_filled.pdf"
    result = acroform.fill(
        template_pdf=SYNTHETIC_PDF,
        profile=tyler_profile,
        index=index,
        output_pdf=output,
        dry_run=False,
    )
    assert "low_count" in result
    assert isinstance(result["low_count"], int)


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


# ---------------------------------------------------------------------------
# Acceptance criteria: zero low_count for the 14-field synthetic form
# ---------------------------------------------------------------------------

def test_zero_low_count_synthetic(tyler_profile, index):
    """Tyler's profile → synthetic form: no field should be low confidence."""
    result = acroform.fill(
        template_pdf=SYNTHETIC_PDF,
        profile=tyler_profile,
        index=index,
        output_pdf=SYNTHETIC_PDF.parent / "dummy_output.pdf",
        dry_run=True,
    )
    low_fields = [
        f["name"] for f in result["fields"] if f.get("confidence") == "low"
    ]
    assert result["low_count"] == 0, f"low_count should be 0, got fields: {low_fields}"


def test_zero_none_count_synthetic(tyler_profile, index):
    """Tyler's profile → synthetic form: no field should be confidence=none."""
    result = acroform.fill(
        template_pdf=SYNTHETIC_PDF,
        profile=tyler_profile,
        index=index,
        output_pdf=SYNTHETIC_PDF.parent / "dummy_output.pdf",
        dry_run=True,
    )
    none_fields = [
        f["name"] for f in result["fields"] if f.get("confidence") == "none"
    ]
    assert len(none_fields) == 0, f"Fields with confidence=none: {none_fields}"


def test_all_synthetic_fields_have_source(tyler_profile, index):
    result = acroform.fill(
        template_pdf=SYNTHETIC_PDF,
        profile=tyler_profile,
        index=index,
        output_pdf=SYNTHETIC_PDF.parent / "dummy_output.pdf",
        dry_run=True,
    )
    for f in result["fields"]:
        assert isinstance(f.get("source"), str) and len(f["source"]) > 0, (
            f"Field '{f['name']}' has empty source"
        )


def test_field_result_includes_alternatives(tyler_profile, index):
    """Each field result dict must include alternatives (may be empty list)."""
    result = acroform.fill(
        template_pdf=SYNTHETIC_PDF,
        profile=tyler_profile,
        index=index,
        output_pdf=SYNTHETIC_PDF.parent / "dummy_output.pdf",
        dry_run=True,
    )
    for f in result["fields"]:
        assert "alternatives" in f and isinstance(f["alternatives"], list), (
            f"Field '{f['name']}' missing alternatives key"
        )


def test_field_result_includes_notes(tyler_profile, index):
    result = acroform.fill(
        template_pdf=SYNTHETIC_PDF,
        profile=tyler_profile,
        index=index,
        output_pdf=SYNTHETIC_PDF.parent / "dummy_output.pdf",
        dry_run=True,
    )
    for f in result["fields"]:
        assert "notes" in f and isinstance(f["notes"], list), (
            f"Field '{f['name']}' missing notes key"
        )


# ---------------------------------------------------------------------------
# Ambiguous form: low_count > 0
# ---------------------------------------------------------------------------

def test_ambiguous_form_has_low_count(tyler_profile, index):
    """ambiguous_form.pdf has 'phone email' → low confidence → low_count >= 1."""
    result = acroform.fill(
        template_pdf=AMBIGUOUS_PDF,
        profile=tyler_profile,
        index=index,
        output_pdf=AMBIGUOUS_PDF.parent / "dummy_ambiguous.pdf",
        dry_run=True,
    )
    assert result["low_count"] >= 1, (
        f"Expected at least 1 low-confidence field, got low_count={result['low_count']}"
    )


def test_ambiguous_form_phone_email_is_low(tyler_profile, index):
    """The 'phone email' field in ambiguous_form.pdf must be low confidence."""
    result = acroform.fill(
        template_pdf=AMBIGUOUS_PDF,
        profile=tyler_profile,
        index=index,
        output_pdf=AMBIGUOUS_PDF.parent / "dummy_ambiguous.pdf",
        dry_run=True,
    )
    phone_email = next(
        (f for f in result["fields"] if f["name"] == "phone email"), None
    )
    assert phone_email is not None, "Field 'phone email' not found in ambiguous form"
    assert phone_email["confidence"] == "low", (
        f"Expected low, got {phone_email['confidence']}"
    )


def test_ambiguous_form_patient_name_is_filled(tyler_profile, index):
    """Patient name in ambiguous form still maps correctly."""
    result = acroform.fill(
        template_pdf=AMBIGUOUS_PDF,
        profile=tyler_profile,
        index=index,
        output_pdf=AMBIGUOUS_PDF.parent / "dummy_ambiguous.pdf",
        dry_run=True,
    )
    name_field = next(
        (f for f in result["fields"] if f["name"] == "patient name"), None
    )
    assert name_field is not None
    assert name_field["mapped_value"] == "Tyler Combs"


# ---------------------------------------------------------------------------
# Commit write
# ---------------------------------------------------------------------------

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
