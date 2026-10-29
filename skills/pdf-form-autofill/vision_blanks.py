"""Vision-based blank detection for scanned / image-only PDF forms.

Vector PDFs expose fill-in rules and checkbox borders as ``page.rects`` /
``page.lines`` / ``page.curves``. A scanned form has none of those -- the whole
page is a raster image, so ``blanks_extractor.get_blanks`` returns [] and every
downstream consumer (layout_analyzer, anchor_mapper, overlay) is starved.

This module recovers that geometry by rendering the page and asking Gemini
vision where the blanks are, reusing the same pypdfium2 + google-genai path
``vision_qa`` already uses. Output uses the exact dict shape ``get_blanks``
already emits -- ``{"x0", "x1", "top", "bottom", "type"}`` in top-origin PDF
points -- so it drops straight into the existing pipeline.

Results are cached per (file hash, page), because a vision call is slow and
billed and the geometry of a blank form never changes.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pypdfium2 as pdfium

MODEL = "gemini-2.5-flash"

# Render resolution handed to the model. This matters more than anything else
# in this module: at 150dpi Gemini mislocates checkboxes by 40-100pt, enough to
# miss a 12pt box entirely. At 300dpi the same model and prompt land within
# ~1.3pt. Do not lower this to save tokens.
DEFAULT_DPI = 300

CACHE_DIR = Path("/Users/tylercombs/.gemini/antigravity-ide/cache/blanks")

# Bump when the prompt or the coordinate handling changes, so old entries are
# ignored rather than silently replayed.
BLANKS_VERSION = 3

# Gemini emits boxes as [ymin, xmin, ymax, xmax] normalized to this range.
_NORM = 1000.0

# Geometry sanity limits, in PDF points. These mirror the thresholds
# blanks_extractor already applies to vector geometry.
MIN_LINE_WIDTH_PT = 12.0
# The model reports the writable BAND for a fill-in field -- roughly one line
# of text tall -- not the hairline rule underneath it. That band's bottom edge
# is the baseline downstream code anchors to, so accept it.
MAX_LINE_THICKNESS_PT = 18.0
MIN_BOX_SIDE_PT = 5.0
MAX_BOX_SIDE_PT = 24.0

# A rule spanning nearly the whole page is a table border or section divider,
# not a place to write.
MAX_LINE_WIDTH_FRAC = 0.80

# How far a blank may sit from the label the model associated it with, before
# we treat the detection as ungrounded.
VERTICAL_SLACK_PT = 6.0
HORIZONTAL_REACH_PT = 60.0

# Fraction of regions that must agree with the text layer for a detection to be
# accepted, and how many times to re-ask when it does not.
MIN_GROUNDING = 0.8
MAX_ATTEMPTS = 3

_PROMPT = """You are analysing a scanned paper form to find every place a person would WRITE or MARK.

Return two kinds of region, and nothing else:

1. "line" — a horizontal fill-in rule: the printed line a person writes ON or ABOVE.
   Report the writable span only. If a printed label sits on the left of the rule
   (for example "Student Name: ______"), START the box after the label text, where
   the empty writing space actually begins.

2. "checkbox" — a small empty square or rectangle intended to be ticked.
   Report the box border itself, not the option text beside it.

Rules:
- Report a region even when the form leaves an open area to write in rather than a printed rule,
  BUT only when there is a clear printed prompt for it. Mark those as "line".
- Do NOT report: the outer border of a table, long horizontal divider rules that separate
  sections, rows of asterisks or dashes used as decoration, or underlines that merely
  underline a heading for emphasis.
- Do NOT report a region that already has handwriting or printed data in it.
- Be exhaustive about checkboxes. Groups of options (for example a row of administration
  methods) usually have one box per option — report every one, including any whose label
  is hard to read.

For each region return "box_2d" as [ymin, xmin, ymax, xmax], normalized 0-1000,
and "type" as either "line" or "checkbox".
Also return "nearby_text": the printed label closest to that region, verbatim, or "" if none.
"""

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "regions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "box_2d": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "minItems": 4,
                        "maxItems": 4,
                    },
                    "type": {"type": "string", "enum": ["line", "checkbox"]},
                    "nearby_text": {"type": "string"},
                },
                "required": ["box_2d", "type"],
            },
        }
    },
    "required": ["regions"],
}


def _hash_file(path: Path) -> str:
    hasher = hashlib.md5()
    with open(path, "rb") as f:
        hasher.update(f.read())
    return hasher.hexdigest()


def _cache_path(pdf_path: Path, page_number: int) -> Path:
    return (
        CACHE_DIR
        / f"{_hash_file(pdf_path)}-p{page_number}-v{BLANKS_VERSION}.json"
    )


def _render(pdf_path: str, page_number: int, dpi: int):
    """Render a 1-based page. Returns (PIL image, width_pt, height_pt)."""
    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        page = pdf[page_number - 1]
        width_pt, height_pt = page.get_width(), page.get_height()
        pil = page.render(scale=dpi / 72.0).to_pil().convert("RGB")
    finally:
        pdf.close()
    return pil, width_pt, height_pt


def _to_points(box, width_pt: float, height_pt: float) -> dict | None:
    """Convert a Gemini [ymin, xmin, ymax, xmax] box to top-origin points."""
    try:
        ymin, xmin, ymax, xmax = (float(v) for v in box)
    except (TypeError, ValueError):
        return None

    x0 = min(xmin, xmax) / _NORM * width_pt
    x1 = max(xmin, xmax) / _NORM * width_pt
    top = min(ymin, ymax) / _NORM * height_pt
    bottom = max(ymin, ymax) / _NORM * height_pt

    # Clamp to the page rather than discarding a slightly overshooting box.
    x0, x1 = max(0.0, x0), min(width_pt, x1)
    top, bottom = max(0.0, top), min(height_pt, bottom)

    if x1 <= x0 or bottom < top:
        return None
    return {"x0": x0, "x1": x1, "top": top, "bottom": bottom}


def _plausible(region: dict, kind: str, width_pt: float) -> bool:
    """Reject boxes whose dimensions cannot be what the model claims."""
    w = region["x1"] - region["x0"]
    h = region["bottom"] - region["top"]

    if kind == "checkbox":
        return (
            MIN_BOX_SIDE_PT <= w <= MAX_BOX_SIDE_PT
            and MIN_BOX_SIDE_PT <= h <= MAX_BOX_SIDE_PT
        )

    return (
        w >= MIN_LINE_WIDTH_PT
        and w <= MAX_LINE_WIDTH_FRAC * width_pt
        and h <= MAX_LINE_THICKNESS_PT
    )


def _call_model(pil_image, api_key: str) -> list[dict]:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=MODEL,
        contents=[pil_image, _PROMPT],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=_RESPONSE_SCHEMA,
            temperature=0.0,
        ),
    )
    return json.loads(response.text).get("regions", [])



def _anchor_token(nearby_text: str) -> str:
    """The most distinctive word in a label, used to locate it in the text layer."""
    tokens = [t.strip(".,:;()[]") for t in (nearby_text or "").split()]
    tokens = [t for t in tokens if len(t) >= 3]
    return max(tokens, key=len) if tokens else ""


def _grounding_score(regions: list[dict], words: list[dict]) -> float:
    """Fraction of regions whose position agrees with the text layer.

    Gemini reliably reports WHICH label a blank belongs to, but its pixel
    coordinates are unstable -- at temperature 0 the same page can come back
    correctly placed or shifted by tens of points. pdfplumber's word boxes are
    exact, so they are the arbiter: a blank must sit on roughly the same line
    as the label the model said it was next to, and close to it horizontally.
    """
    from rapidfuzz import fuzz

    checked = agreed = 0
    for r in regions:
        token = _anchor_token(r.get("nearby_text", ""))
        if not token:
            continue

        matches = [
            w for w in words
            if fuzz.ratio(token.lower(), w["text"].strip(".,:;()[]").lower()) > 85
        ]
        if not matches:
            continue

        checked += 1
        cy = (r["top"] + r["bottom"]) / 2.0
        if any(
            w["top"] - VERTICAL_SLACK_PT <= cy <= w["bottom"] + VERTICAL_SLACK_PT
            and (r["x0"] - w["x1"]) < HORIZONTAL_REACH_PT
            and (w["x0"] - r["x1"]) < HORIZONTAL_REACH_PT
            for w in matches
        ):
            agreed += 1

    return agreed / checked if checked else 0.0


def _trim_labels(blanks: list[dict], words: list[dict]) -> list[dict]:
    """Cut printed text out of a fill-in band, leaving the writable part.

    Asked for the writable span, the model often returns the whole row --
    label included. Writing at that band's x0 stamps the value on top of the
    label. pdfplumber's word boxes are exact, so subtracting them recovers the
    part of the band that is actually empty. A band with nothing left is not a
    blank at all (body text the model mistook for a field) and is dropped.
    """
    trimmed: list[dict] = []
    for b in blanks:
        if b["type"] != "line":
            trimmed.append(b)
            continue

        cy = (b["top"] + b["bottom"]) / 2.0
        occluders = sorted(
            (w["x0"] - 1.0, w["x1"] + 2.0)
            for w in words
            if w["top"] - 1.0 <= cy <= w["bottom"] + 1.0
            and w["x1"] > b["x0"] and w["x0"] < b["x1"]
        )

        if not occluders:
            trimmed.append(b)
            continue

        spans, cursor = [], b["x0"]
        for lo, hi in occluders:
            if lo > cursor:
                spans.append((cursor, min(lo, b["x1"])))
            cursor = max(cursor, hi)
            if cursor >= b["x1"]:
                break
        if cursor < b["x1"]:
            spans.append((cursor, b["x1"]))

        widest = max(spans, key=lambda s: s[1] - s[0], default=None)
        if widest and (widest[1] - widest[0]) >= MIN_LINE_WIDTH_PT:
            trimmed.append({**b, "x0": widest[0], "x1": widest[1]})

    return trimmed


def detect_blanks(
    pdf_path: str,
    page_number: int = 1,
    dpi: int = DEFAULT_DPI,
    words: list[dict] | None = None,
    refresh: bool = False,
) -> list[dict]:
    """Detect fill-in rules and checkboxes on a scanned page using Gemini vision.

    Args:
        pdf_path: Path to the PDF.
        page_number: 1-based page index.
        dpi: Render resolution for the image sent to the model.
        words: pdfplumber ``page.extract_words()`` output. Used to verify the
            model's coordinates against the text layer; without it no
            grounding check is possible and coordinates are taken on trust.
        refresh: Ignore any cached detection for this page.

    Returns:
        Blanks in the same shape as ``blanks_extractor.get_vector_blanks``:
        dicts of ``x0``, ``x1``, ``top``, ``bottom``, ``type``, in top-origin
        PDF points. ``type`` is one of ``"line"`` or ``"checkbox"``.
    """
    source = Path(pdf_path)
    cache_file = _cache_path(source, page_number)
    refresh = refresh or os.environ.get("PDF_AUTOFILL_REFRESH_BLANKS") == "1"

    if not refresh and cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text())
            if cached.get("blanks_version") == BLANKS_VERSION:
                return cached.get("blanks", [])
        except (json.JSONDecodeError, OSError):
            pass

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is missing. Scanned PDFs need it to locate form blanks."
        )

    pil_image, width_pt, height_pt = _render(pdf_path, page_number, dpi)

    # Retrying only helps when there is a text layer to check the answer
    # against. Without one, a second opinion is no more trustworthy than the
    # first, so take one answer rather than paying for three.
    attempts = MAX_ATTEMPTS if words else 1

    best: list[dict] = []
    best_score = -1.0
    for attempt in range(1, attempts + 1):
        regions = _call_model(pil_image, api_key)

        parsed: list[dict] = []
        for r in regions:
            kind = r.get("type")
            if kind not in ("line", "checkbox"):
                continue
            geom = _to_points(r.get("box_2d"), width_pt, height_pt)
            if geom is None or not _plausible(geom, kind, width_pt):
                continue
            geom["type"] = kind
            geom["nearby_text"] = r.get("nearby_text", "")
            parsed.append(geom)

        score = _grounding_score(parsed, words or [])
        detail = f"grounding {score:.0%}" if words else "ungrounded (no text layer)"
        print(f"[Vision Blanks] attempt {attempt}: {len(parsed)} regions, {detail}")

        if score > best_score:
            best, best_score = parsed, score
        if score >= MIN_GROUNDING:
            break

    if words and best_score < MIN_GROUNDING:
        # Coordinates disagreed with the text layer on every attempt. Returning
        # them anyway would place marks confidently in the wrong spot, which is
        # worse than placing none: the caller falls back to label-relative
        # anchoring, which at least degrades visibly.
        print(
            f"[Vision Blanks] Warning: best grounding {best_score:.0%} is below "
            f"{MIN_GROUNDING:.0%}; discarding coordinates for page {page_number}."
        )
        best = []

    blanks = [
        {k: v for k, v in b.items() if k != "nearby_text"}
        for b in best
    ]
    if words:
        blanks = _trim_labels(blanks, words)
    blanks.sort(key=lambda b: (b["top"], b["x0"]))

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(
        json.dumps(
            {
                "blanks_version": BLANKS_VERSION,
                "source_pdf": source.name,
                "page": page_number,
                "grounding": round(best_score, 3),
                "blanks": blanks,
            },
            indent=2,
        )
    )
    return blanks
