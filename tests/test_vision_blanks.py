"""Tests for vision-based blank detection on scanned / image-only PDFs.

Covers the gap that made scanned forms unfillable: pdfplumber reports no vector
geometry, so blanks_extractor found nothing and every downstream stage
(layout_analyzer, anchor_mapper, overlay) had nothing to anchor to.

No test here calls Gemini. The model call is stubbed so the geometry handling,
the grounding check and the label trimming are all exercised deterministically.
"""

from __future__ import annotations

import json
from pathlib import Path

import pdfplumber
import pytest

import blanks_extractor
import schema_extractor
import vision_blanks
from make_scanned_pdf import (
    CHECKBOX_FIELDS,
    RULE_FIELDS,
    expected_checkboxes_top_origin,
    expected_rules_top_origin,
    make_scanned_form,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
FLATTENED_PDF = FIXTURE_DIR / "flattened_form.pdf"

PAGE_W, PAGE_H = 612.0, 792.0


@pytest.fixture(scope="module")
def scanned_pdf() -> Path:
    path = FIXTURE_DIR / "scanned_form.pdf"
    if not path.exists():
        FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
        make_scanned_form(path)
    return path


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    """Never read or write the real blanks cache during tests."""
    monkeypatch.setattr(vision_blanks, "CACHE_DIR", tmp_path / "blanks")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-used")


def _box(x0, x1, top, bottom):
    """Build a Gemini-style [ymin, xmin, ymax, xmax] box from PDF points."""
    return [
        round(top / PAGE_H * 1000),
        round(x0 / PAGE_W * 1000),
        round(bottom / PAGE_H * 1000),
        round(x1 / PAGE_W * 1000),
    ]


def _truthful_regions():
    regions = []
    for (x0, x1, top), (label, *_ ) in zip(expected_rules_top_origin(), RULE_FIELDS):
        regions.append({
            "box_2d": _box(x0, x1, top - 5, top + 5),
            "type": "line",
            "nearby_text": label,
        })
    for (x0, x1, top, bottom), (label, *_) in zip(
        expected_checkboxes_top_origin(), CHECKBOX_FIELDS
    ):
        regions.append({
            "box_2d": _box(x0, x1, top, bottom),
            "type": "checkbox",
            "nearby_text": label,
        })
    return regions


# ---------------------------------------------------------------------------
# Precondition: the fixture really is a scan
# ---------------------------------------------------------------------------

def test_fixture_has_no_vector_geometry(scanned_pdf):
    """Guards the premise. If this fails the fixture stopped being a scan."""
    with pdfplumber.open(scanned_pdf) as pdf:
        page = pdf.pages[0]
        assert page.rects == []
        assert page.lines == []
        assert page.curves == []
        assert page.images, "fixture should be a raster image"


def test_vector_extraction_finds_nothing_on_a_scan(scanned_pdf):
    """The original failure mode, pinned so a regression is visible."""
    with pdfplumber.open(scanned_pdf) as pdf:
        assert blanks_extractor.get_vector_blanks(pdf.pages[0]) == []


# ---------------------------------------------------------------------------
# Coordinate conversion
# ---------------------------------------------------------------------------

def test_box_converts_to_top_origin_points():
    geom = vision_blanks._to_points([250, 100, 300, 500], PAGE_W, PAGE_H)
    assert geom["x0"] == pytest.approx(61.2)
    assert geom["x1"] == pytest.approx(306.0)
    assert geom["top"] == pytest.approx(198.0)
    assert geom["bottom"] == pytest.approx(237.6)


def test_box_is_clamped_to_the_page():
    geom = vision_blanks._to_points([-20, -50, 1100, 1200], PAGE_W, PAGE_H)
    assert geom["x0"] == 0.0
    assert geom["x1"] == PAGE_W
    assert geom["top"] == 0.0
    assert geom["bottom"] == PAGE_H


def test_inverted_box_is_normalised():
    geom = vision_blanks._to_points([300, 500, 250, 100], PAGE_W, PAGE_H)
    assert geom["x0"] < geom["x1"]
    assert geom["top"] < geom["bottom"]


def test_malformed_box_is_rejected():
    assert vision_blanks._to_points([1, 2, 3], PAGE_W, PAGE_H) is None
    assert vision_blanks._to_points(None, PAGE_W, PAGE_H) is None
    assert vision_blanks._to_points(["a", "b", "c", "d"], PAGE_W, PAGE_H) is None


# ---------------------------------------------------------------------------
# Plausibility filter
# ---------------------------------------------------------------------------

def test_full_width_rule_is_rejected_as_a_divider():
    band = {"x0": 10.0, "x1": 600.0, "top": 100.0, "bottom": 108.0}
    assert not vision_blanks._plausible(band, "line", PAGE_W)


def test_writable_band_is_accepted_as_a_line():
    """The model returns a band ~one line tall, not a hairline rule."""
    band = {"x0": 150.0, "x1": 400.0, "top": 100.0, "bottom": 110.5}
    assert vision_blanks._plausible(band, "line", PAGE_W)


def test_oversized_checkbox_is_rejected():
    big = {"x0": 100.0, "x1": 160.0, "top": 100.0, "bottom": 160.0}
    assert not vision_blanks._plausible(big, "checkbox", PAGE_W)


# ---------------------------------------------------------------------------
# Grounding against the text layer
# ---------------------------------------------------------------------------

_WORDS = [
    {"text": "Mouth", "x0": 91.0, "x1": 120.0, "top": 262.0, "bottom": 272.0},
    {"text": "Skin", "x0": 91.0, "x1": 115.0, "top": 276.0, "bottom": 286.0},
]


def test_well_placed_regions_ground():
    regions = [
        {"x0": 74.0, "x1": 86.0, "top": 262.0, "bottom": 274.0, "nearby_text": "Mouth"},
        {"x0": 74.0, "x1": 86.0, "top": 276.0, "bottom": 288.0, "nearby_text": "Skin"},
    ]
    assert vision_blanks._grounding_score(regions, _WORDS) == 1.0


def test_shifted_regions_fail_grounding():
    """The real failure: correct boxes, wrong absolute position."""
    regions = [
        {"x0": 142.0, "x1": 154.0, "top": 246.0, "bottom": 258.0, "nearby_text": "Mouth"},
        {"x0": 142.0, "x1": 154.0, "top": 260.0, "bottom": 272.0, "nearby_text": "Skin"},
    ]
    assert vision_blanks._grounding_score(regions, _WORDS) < vision_blanks.MIN_GROUNDING


def test_grounding_is_zero_without_a_text_layer():
    assert vision_blanks._grounding_score([{"nearby_text": "Mouth"}], []) == 0.0


def test_anchor_token_picks_the_longest_word():
    assert vision_blanks._anchor_token("Time of day to be given at school:") == "school"
    assert vision_blanks._anchor_token("") == ""
    assert vision_blanks._anchor_token("a b c") == ""


# ---------------------------------------------------------------------------
# Label trimming
# ---------------------------------------------------------------------------

def test_label_is_trimmed_out_of_a_band():
    """A band covering "Student Name: ____" must start after the label."""
    words = [
        {"text": "Student", "x0": 72.0, "x1": 110.0, "top": 96.0, "bottom": 106.0},
        {"text": "Name:", "x0": 112.0, "x1": 148.0, "top": 96.0, "bottom": 106.0},
    ]
    band = [{"x0": 70.0, "x1": 400.0, "top": 96.0, "bottom": 106.0, "type": "line"}]
    out = vision_blanks._trim_labels(band, words)
    assert len(out) == 1
    assert out[0]["x0"] == pytest.approx(150.0)
    assert out[0]["x1"] == pytest.approx(400.0)


def test_band_covered_entirely_by_text_is_dropped():
    """Body text the model mistook for a field."""
    words = [{"text": "sentence", "x0": 70.0, "x1": 400.0, "top": 96.0, "bottom": 106.0}]
    band = [{"x0": 72.0, "x1": 398.0, "top": 96.0, "bottom": 106.0, "type": "line"}]
    assert vision_blanks._trim_labels(band, words) == []


def test_checkboxes_are_never_trimmed():
    words = [{"text": "Yes", "x0": 100.0, "x1": 130.0, "top": 96.0, "bottom": 106.0}]
    box = [{"x0": 86.0, "x1": 98.0, "top": 95.0, "bottom": 107.0, "type": "checkbox"}]
    assert vision_blanks._trim_labels(box, words) == box


# ---------------------------------------------------------------------------
# detect_blanks, with the model stubbed
# ---------------------------------------------------------------------------

def test_detect_returns_the_vector_contract(scanned_pdf, monkeypatch):
    monkeypatch.setattr(vision_blanks, "_call_model", lambda *a: _truthful_regions())
    blanks = vision_blanks.detect_blanks(str(scanned_pdf), 1, refresh=True)

    assert blanks
    for b in blanks:
        assert set(b) >= {"x0", "x1", "top", "bottom", "type"}
        assert b["type"] in {"line", "checkbox"}
        assert b["x1"] > b["x0"]
        assert b["bottom"] >= b["top"]
        assert 0 <= b["x0"] < PAGE_W and 0 <= b["top"] <= PAGE_H


def test_detect_finds_every_checkbox(scanned_pdf, monkeypatch):
    monkeypatch.setattr(vision_blanks, "_call_model", lambda *a: _truthful_regions())
    blanks = vision_blanks.detect_blanks(str(scanned_pdf), 1, refresh=True)
    assert len([b for b in blanks if b["type"] == "checkbox"]) == len(CHECKBOX_FIELDS)


def test_detect_retries_until_grounded(scanned_pdf, monkeypatch):
    """A shifted first answer must be re-requested, not accepted."""
    words = [
        {"text": label, "x0": x + side + 5, "x1": x + side + 40,
         "top": PAGE_H - (y + side), "bottom": PAGE_H - y}
        for label, x, y, side in CHECKBOX_FIELDS
    ]
    shifted = [
        {**r, "box_2d": [r["box_2d"][0] - 60, r["box_2d"][1] + 90,
                         r["box_2d"][2] - 60, r["box_2d"][3] + 90]}
        for r in _truthful_regions()
    ]
    answers = [shifted, _truthful_regions()]
    calls = {"n": 0}

    def fake(*a):
        calls["n"] += 1
        return answers[min(calls["n"] - 1, len(answers) - 1)]

    monkeypatch.setattr(vision_blanks, "_call_model", fake)
    blanks = vision_blanks.detect_blanks(str(scanned_pdf), 1, words=words, refresh=True)

    assert calls["n"] == 2, "should have re-requested after the shifted answer"
    assert blanks


def test_ungrounded_detection_is_discarded(scanned_pdf, monkeypatch):
    """Confidently wrong coordinates are worse than none."""
    words = [
        {"text": label, "x0": x + side + 5, "x1": x + side + 40,
         "top": PAGE_H - (y + side), "bottom": PAGE_H - y}
        for label, x, y, side in CHECKBOX_FIELDS
    ]
    shifted = [
        {**r, "box_2d": [r["box_2d"][0] - 60, r["box_2d"][1] + 90,
                         r["box_2d"][2] - 60, r["box_2d"][3] + 90]}
        for r in _truthful_regions()
    ]
    monkeypatch.setattr(vision_blanks, "_call_model", lambda *a: shifted)
    assert vision_blanks.detect_blanks(str(scanned_pdf), 1, words=words, refresh=True) == []


def test_detection_is_cached(scanned_pdf, monkeypatch):
    calls = {"n": 0}

    def fake(*a):
        calls["n"] += 1
        return _truthful_regions()

    monkeypatch.setattr(vision_blanks, "_call_model", fake)
    first = vision_blanks.detect_blanks(str(scanned_pdf), 1, refresh=True)
    second = vision_blanks.detect_blanks(str(scanned_pdf), 1)
    assert calls["n"] == 1, "second call should have hit the cache"
    assert first == second


def test_missing_api_key_is_a_clear_error(scanned_pdf, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        vision_blanks.detect_blanks(str(scanned_pdf), 1, refresh=True)


# ---------------------------------------------------------------------------
# Automatic fallback wiring
# ---------------------------------------------------------------------------

def test_get_blanks_falls_back_to_vision(scanned_pdf, monkeypatch):
    """The whole point: get_blanks() now returns geometry for a scan."""
    monkeypatch.setattr(vision_blanks, "_call_model", lambda *a: _truthful_regions())
    with pdfplumber.open(scanned_pdf) as pdf:
        blanks = blanks_extractor.get_blanks(pdf.pages[0])

    assert blanks
    assert all(b.get("source") == "vision" for b in blanks)


def test_get_blanks_can_opt_out_of_vision(scanned_pdf):
    with pdfplumber.open(scanned_pdf) as pdf:
        assert blanks_extractor.get_blanks(pdf.pages[0], allow_vision=False) == []


def test_blanks_stay_sorted(scanned_pdf, monkeypatch):
    monkeypatch.setattr(vision_blanks, "_call_model", lambda *a: _truthful_regions())
    with pdfplumber.open(scanned_pdf) as pdf:
        blanks = blanks_extractor.get_blanks(pdf.pages[0])
    assert blanks == sorted(blanks, key=lambda b: (b["top"], b["x0"]))


@pytest.mark.skipif(not FLATTENED_PDF.exists(), reason="vector fixture absent")
def test_vector_pdf_never_calls_the_model(monkeypatch):
    """Regression guard: a vector PDF must never pay for a vision call."""
    def _boom(*args, **kwargs):
        raise AssertionError("vision fallback ran on a vector PDF")

    monkeypatch.setattr(vision_blanks, "detect_blanks", _boom)

    with pdfplumber.open(FLATTENED_PDF) as pdf:
        for page in pdf.pages:
            blanks_extractor.get_blanks(page)


# ---------------------------------------------------------------------------
# Schema cache staleness
# ---------------------------------------------------------------------------

def test_cache_key_is_versioned(scanned_pdf):
    assert schema_extractor.cache_path_for(scanned_pdf).name.endswith(
        f"-v{schema_extractor.SCHEMA_VERSION}.json"
    )


def test_legacy_bare_list_cache_is_ignored(tmp_path):
    """Pre-versioning entries were bare arrays written by the blind pipeline."""
    stale = tmp_path / "legacy.json"
    stale.write_text(json.dumps([{"label": "Name:", "is_checkbox": False, "page": 1}]))
    assert schema_extractor._read_cache(stale) is None


def test_superseded_version_is_ignored(tmp_path):
    old = tmp_path / "old.json"
    old.write_text(json.dumps({
        "schema_version": schema_extractor.SCHEMA_VERSION - 1,
        "schema": [{"label": "Name:", "is_checkbox": False, "page": 1}],
    }))
    assert schema_extractor._read_cache(old) is None


def test_empty_cached_schema_is_ignored(tmp_path):
    """An empty schema is a failed run, not a result worth replaying."""
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps({
        "schema_version": schema_extractor.SCHEMA_VERSION, "schema": [],
    }))
    assert schema_extractor._read_cache(empty) is None


def test_current_cache_is_returned(tmp_path):
    good = tmp_path / "good.json"
    fields = [{"label": "Name:", "is_checkbox": False, "page": 1}]
    good.write_text(json.dumps({
        "schema_version": schema_extractor.SCHEMA_VERSION, "schema": fields,
    }))
    assert schema_extractor._read_cache(good) == fields


def test_corrupt_cache_is_ignored(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert schema_extractor._read_cache(bad) is None


# ---------------------------------------------------------------------------
# find_best_blank: relation choice and width filtering
# ---------------------------------------------------------------------------

def test_same_line_blank_beats_a_marginally_closer_one_above():
    """A value must not walk onto the previous row's label.

    In a bulleted list each item has a blank to its right, and the blank
    belonging to the item ABOVE sits just a point or two nearer. Ranking by
    raw distance picked that one and stamped the value on the wrong row.
    """
    import anchor_mapper

    match = {"x0": 76.6, "x1": 238.0, "top": 589.6, "bottom": 599.9}
    above = {"x0": 102.8, "x1": 293.1, "top": 577.4, "bottom": 587.7, "type": "line"}
    right = {"x0": 240.8, "x1": 293.1, "top": 590.0, "bottom": 601.9, "type": "line"}

    blank, rel = anchor_mapper.find_best_blank(match, [above, right], False)
    assert blank is right, f"picked the blank {rel} instead of the one on its line"


def test_a_clearly_closer_blank_above_still_wins():
    """The 'above' relation exists for captioned lines; it must survive."""
    import anchor_mapper

    match = {"x0": 100.0, "x1": 200.0, "top": 300.0, "bottom": 310.0}
    above = {"x0": 100.0, "x1": 260.0, "top": 297.0, "bottom": 299.0, "type": "line"}
    far_right = {"x0": 240.0, "x1": 400.0, "top": 300.0, "bottom": 311.0, "type": "line"}

    blank, rel = anchor_mapper.find_best_blank(match, [above, far_right], False)
    assert blank is above and rel == "above"


def test_short_rule_is_a_valid_text_anchor():
    """A narrow rule -- Grade, State, Zip -- is a real field, not noise."""
    import anchor_mapper

    match = {"x0": 487.9, "x1": 520.0, "top": 67.3, "bottom": 77.0}
    short_rule = {"x0": 522.7, "x1": 538.9, "top": 79.9, "bottom": 80.6, "type": "line"}
    other_line = {"x0": 401.8, "x1": 540.4, "top": 105.5, "bottom": 106.2, "type": "line"}

    blank, rel = anchor_mapper.find_best_blank(match, [short_rule, other_line], False)
    assert blank is short_rule, f"picked the wrong blank via {rel}"


def test_checkbox_blanks_are_not_offered_to_text_fields():
    import anchor_mapper

    match = {"x0": 100.0, "x1": 140.0, "top": 200.0, "bottom": 210.0}
    checkbox = {"x0": 145.0, "x1": 157.0, "top": 199.0, "bottom": 211.0, "type": "checkbox"}

    assert anchor_mapper.find_best_blank(match, [checkbox], False)[0] is None


def test_segmented_cells_are_not_offered_to_text_fields():
    import anchor_mapper

    match = {"x0": 100.0, "x1": 140.0, "top": 200.0, "bottom": 210.0}
    cell = {"x0": 145.0, "x1": 165.0, "top": 195.0, "bottom": 220.0, "type": "segmented_cell"}

    assert anchor_mapper.find_best_blank(match, [cell], False)[0] is None
