"""Tests for skills/form-autofill/overlay.py — spatial overlay for flattened PDFs."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SKILL_DIR = _PROJECT_ROOT / "skills" / "form-autofill"

for _p in (str(_PROJECT_ROOT), str(_SKILL_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import overlay

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
ACROFORM_PDF = FIXTURE_DIR / "synthetic_form.pdf"
FLATTENED_PDF = FIXTURE_DIR / "flattened_form.pdf"


@pytest.fixture(scope="module")
def tyler_profile():
    from lib import profile_loader as pl
    return pl.load_profile("tyler_combs")


@pytest.fixture(scope="module")
def index():
    from lib import profile_loader as pl
    return pl.load_index()


# ---------------------------------------------------------------------------
# Guard: AcroForm PDF must be rejected
# ---------------------------------------------------------------------------

def test_overlay_raises_on_acroform_pdf(tyler_profile, index, tmp_path):
    """overlay.fill() must raise ValueError when the PDF has an AcroForm."""
    with pytest.raises(ValueError, match="use acroform.fill()"):
        overlay.fill(
            template_pdf=ACROFORM_PDF,
            profile=tyler_profile,
            index=index,
            output_pdf=tmp_path / "out.pdf",
            dry_run=True,
        )


# ---------------------------------------------------------------------------
# Dry-run shape contract
# ---------------------------------------------------------------------------

def test_overlay_dry_run_returns_dict(tyler_profile, index, tmp_path):
    """Dry-run returns the standard result dict with all required keys."""
    result = overlay.fill(
        template_pdf=FLATTENED_PDF,
        profile=tyler_profile,
        index=index,
        output_pdf=tmp_path / "out.pdf",
        dry_run=True,
    )
    for key in ("mode", "fields", "filled_count", "skipped_count", "low_count"):
        assert key in result, f"Missing key: {key}"
    assert result["mode"] == "dry_run"
    assert isinstance(result["fields"], list)
    assert isinstance(result["filled_count"], int)
    assert isinstance(result["skipped_count"], int)
    assert isinstance(result["low_count"], int)


def test_overlay_dry_run_no_file_written(tyler_profile, index, tmp_path):
    """Dry-run must not write any file."""
    output = tmp_path / "should_not_exist.pdf"
    overlay.fill(
        template_pdf=FLATTENED_PDF,
        profile=tyler_profile,
        index=index,
        output_pdf=output,
        dry_run=True,
    )
    assert not output.exists(), "Dry run must not write any file"


def test_overlay_dry_run_detects_labels(tyler_profile, index, tmp_path):
    """Dry-run detects expected labels from the flattened fixture."""
    result = overlay.fill(
        template_pdf=FLATTENED_PDF,
        profile=tyler_profile,
        index=index,
        output_pdf=tmp_path / "out.pdf",
        dry_run=True,
    )
    names = [f["name"].lower() for f in result["fields"]]
    assert any("patient name" in n for n in names), f"Expected 'patient name' label. Got: {names}"
    assert any("phone" in n for n in names), f"Expected a phone label. Got: {names}"


def test_overlay_dry_run_fills_known_labels(tyler_profile, index, tmp_path):
    """High-confidence labels from the fixture have non-None mapped values."""
    result = overlay.fill(
        template_pdf=FLATTENED_PDF,
        profile=tyler_profile,
        index=index,
        output_pdf=tmp_path / "out.pdf",
        dry_run=True,
    )
    high_filled = [
        f for f in result["fields"]
        if f.get("confidence") == "high" and f.get("mapped_value")
    ]
    assert len(high_filled) >= 5, (
        f"Expected at least 5 high-confidence fills. Got: {len(high_filled)}"
    )


def test_overlay_counts_consistent(tyler_profile, index, tmp_path):
    """filled_count + skipped_count == len(fields)."""
    result = overlay.fill(
        template_pdf=FLATTENED_PDF,
        profile=tyler_profile,
        index=index,
        output_pdf=tmp_path / "out.pdf",
        dry_run=True,
    )
    total = len(result["fields"])
    assert result["filled_count"] + result["skipped_count"] == total


# ---------------------------------------------------------------------------
# Commit mode
# ---------------------------------------------------------------------------

def test_overlay_fill_writes_pdf(tyler_profile, index, tmp_path):
    """Commit mode writes an output PDF."""
    output = tmp_path / "filled.pdf"
    result = overlay.fill(
        template_pdf=FLATTENED_PDF,
        profile=tyler_profile,
        index=index,
        output_pdf=output,
        dry_run=False,
    )
    assert result["mode"] == "filled"
    assert "output" in result
    assert output.exists(), "Committed PDF was not written"
    assert output.stat().st_size > 0


def test_overlay_fill_result_has_output_key(tyler_profile, index, tmp_path):
    """Commit result includes 'output' key with the written path."""
    output = tmp_path / "filled.pdf"
    result = overlay.fill(
        template_pdf=FLATTENED_PDF,
        profile=tyler_profile,
        index=index,
        output_pdf=output,
        dry_run=False,
    )
    assert result.get("output") == str(output)


def test_overlay_fill_text_appears_in_output(tyler_profile, index, tmp_path):
    """Filled PDF contains overlaid profile values."""
    import pdfplumber
    output = tmp_path / "filled.pdf"
    overlay.fill(
        template_pdf=FLATTENED_PDF,
        profile=tyler_profile,
        index=index,
        output_pdf=output,
        dry_run=False,
    )
    with pdfplumber.open(str(output)) as pdf:
        text = pdf.pages[0].extract_text() or ""
    assert "Tyler Combs" in text, f"Expected 'Tyler Combs' in filled PDF text. Got: {text[:300]}"


# ---------------------------------------------------------------------------
# OCR / Blank PDF Detection
# ---------------------------------------------------------------------------

def test_overlay_detects_blank_pdf(tyler_profile, index, tmp_path, monkeypatch):
    """A completely blank PDF (no words, no images) raises a ValueError."""
    import pdfplumber
    class MockPage:
        images = []
        def extract_words(self):
            return []
    class MockPdf:
        pages = [MockPage()]
    
    class MockOpen:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return MockPdf()
        def __exit__(self, *args): pass

    monkeypatch.setattr(pdfplumber, "open", MockOpen)
    
    with pytest.raises(ValueError, match="It is completely blank"):
        overlay.fill(
            template_pdf=FLATTENED_PDF,
            profile=tyler_profile,
            index=index,
            output_pdf=tmp_path / "out.pdf",
            dry_run=True,
        )


def test_overlay_detects_image_only_pdf(tyler_profile, index, tmp_path, monkeypatch):
    """An image-only PDF attempts to run OCR workflow and raises if not interactive."""
    import pdfplumber
    class MockPage:
        images = [{"dummy": "image"}]
        def extract_words(self):
            return []
    class MockPdf:
        pages = [MockPage()]

    class MockOpen:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return MockPdf()
        def __exit__(self, *args): pass

    monkeypatch.setattr(pdfplumber, "open", MockOpen)
    
    # In tests, sys.stdin.isatty() is usually False, so it hits the ValueError
    with pytest.raises(ValueError, match="interactive terminal to perform automated OCR"):
        overlay.fill(
            template_pdf=FLATTENED_PDF,
            profile=tyler_profile,
            index=index,
            output_pdf=tmp_path / "out.pdf",
            dry_run=True,
        )
