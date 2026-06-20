"""Spatial overlay fill for flattened (non-AcroForm) PDFs."""

from __future__ import annotations

import datetime
import io
from collections import defaultdict
from pathlib import Path

import pypdf
import pdfplumber

_FILL_GAP = 8.0              # pts between label end and value start
_MIN_BLANK_WIDTH = 72.0      # pts (1 inch) minimum blank area required
_FONT_SIZE = 11
_LINE_CLUSTER_TOL = 4.0      # pts — words within this y-range → same line


def _group_into_lines(words: list[dict]) -> list[list[dict]]:
    """Cluster words into text lines by top-edge proximity."""
    if not words:
        return []
    sorted_words = sorted(words, key=lambda w: (w["y0"], w["x0"]))
    lines: list[list[dict]] = []
    current: list[dict] = [sorted_words[0]]
    for word in sorted_words[1:]:
        if abs(word["y0"] - current[0]["y0"]) <= _LINE_CLUSTER_TOL:
            current.append(word)
        else:
            lines.append(sorted(current, key=lambda w: w["x0"]))
            current = [word]
    lines.append(sorted(current, key=lambda w: w["x0"]))
    return lines


def _detect_label(line: list[dict], page_w: float) -> dict | None:
    """Return label metadata if the line contains a colon-terminated label.

    Looks for the rightmost word ending with ':'. Everything on the line up to
    and including that word becomes the label; the blank area to its right
    becomes the fill zone. Returns None if no colon found or no room to fill.
    """
    colon_idx = None
    for i, word in enumerate(line):
        if word["text"].endswith(":"):
            colon_idx = i

    if colon_idx is None:
        return None

    colon_word = line[colon_idx]
    fill_x = colon_word["x1"] + _FILL_GAP

    if page_w - fill_x < _MIN_BLANK_WIDTH:
        return None

    label_words = line[: colon_idx + 1]
    label_raw = " ".join(w["text"] for w in label_words)
    label_text = label_raw.rstrip(":").strip()

    return {
        "label_text": label_text,
        "label_raw": label_raw,
        "fill_x": fill_x,
        "label_y1": colon_word["y1"],
    }


def _write_overlay(
    template_pdf: Path,
    output_pdf: Path,
    instructions: list[dict],
    page_heights: dict[int, float],
    page_widths: dict[int, float],
) -> None:
    """Stamp text overlays onto template PDF pages and write output."""
    from reportlab.pdfgen import canvas as _rl_canvas

    by_page: dict[int, list[dict]] = defaultdict(list)
    for inst in instructions:
        by_page[inst["page"]].append(inst)

    writer = pypdf.PdfWriter(clone_from=str(template_pdf))

    for page_num, page_insts in by_page.items():
        page_h = page_heights[page_num]
        page_w = page_widths[page_num]

        buf = io.BytesIO()
        c = _rl_canvas.Canvas(buf, pagesize=(page_w, page_h))
        c.setFont("Helvetica", _FONT_SIZE)
        for inst in page_insts:
            c.drawString(float(inst["x"]), float(inst["y"]), str(inst["text"]))
        c.save()
        buf.seek(0)

        overlay_reader = pypdf.PdfReader(buf)
        writer.pages[page_num].merge_page(overlay_reader.pages[0])

    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    with output_pdf.open("wb") as f:
        writer.write(f)


def fill(
    template_pdf: Path,
    profile: dict,
    index: dict,
    output_pdf: Path,
    dry_run: bool = True,
) -> dict:
    """Fill a flattened (non-AcroForm) PDF by overlaying typed text at label positions.

    Uses pdfplumber's spatial word map to detect colon-terminated labels, maps
    each to a profile value via field_mapper, then (in commit mode) overlays the
    text using a reportlab canvas merged with pypdf.

    Raises:
        ValueError: if the PDF contains an AcroForm (use acroform.fill() instead).

    Returns:
        dict with the same shape as acroform.fill():
          mode, fields, filled_count, skipped_count, low_count, [output]
    """
    reader = pypdf.PdfReader(str(template_pdf))
    root = reader.trailer.get("/Root", {})
    if "/AcroForm" in root:
        raise ValueError(
            "use acroform.fill() for AcroForm PDFs"
        )

    page_heights = {i: float(p.mediabox.height) for i, p in enumerate(reader.pages)}
    page_widths = {i: float(p.mediabox.width) for i, p in enumerate(reader.pages)}

    words_by_page: dict[int, list[dict]] = defaultdict(list)
    with pdfplumber.open(str(template_pdf)) as pdf:
        for page_num, page in enumerate(pdf.pages):
            for word in page.extract_words() or []:
                words_by_page[page_num].append(
                    {
                        "text": word["text"],
                        "x0": word["x0"],
                        "x1": word["x1"],
                        "y0": word["top"],
                        "y1": word["bottom"],
                    }
                )

    import field_mapper as _fm

    field_results: list[dict] = []
    fill_instructions: list[dict] = []
    today = datetime.date.today()

    for page_num in sorted(words_by_page):
        words = words_by_page[page_num]
        page_h = page_heights[page_num]
        page_w = page_widths[page_num]

        for line in _group_into_lines(words):
            label_info = _detect_label(line, page_w)
            if label_info is None:
                continue

            label_text = label_info["label_text"]
            fill_x = label_info["fill_x"]
            # pdfplumber uses top-origin; PDF canvas uses bottom-origin
            fill_y = page_h - label_info["label_y1"]

            fm_result = _fm.map_pdf_field(
                label_text,
                label_info["label_raw"],
                profile,
                index,
                today=today,
            )
            value = fm_result["value"]
            skipped = value is None

            field_results.append(
                {
                    "name": label_text,
                    "alt": label_info["label_raw"],
                    "mapped_value": value,
                    "confidence": fm_result["confidence"],
                    "source": fm_result["source"],
                    "alternatives": fm_result["alternatives"],
                    "notes": fm_result["notes"],
                    "skipped": skipped,
                }
            )

            if not skipped:
                fill_instructions.append(
                    {
                        "page": page_num,
                        "x": fill_x,
                        "y": fill_y,
                        "text": value,
                        "font_size": _FONT_SIZE,
                    }
                )

    filled_count = sum(1 for r in field_results if not r["skipped"])
    skipped_count = sum(1 for r in field_results if r["skipped"])
    low_count = sum(1 for r in field_results if r.get("confidence") == "low")

    if dry_run:
        return {
            "mode": "dry_run",
            "fields": field_results,
            "filled_count": filled_count,
            "skipped_count": skipped_count,
            "low_count": low_count,
        }

    _write_overlay(template_pdf, output_pdf, fill_instructions, page_heights, page_widths)

    return {
        "mode": "filled",
        "fields": field_results,
        "filled_count": filled_count,
        "skipped_count": skipped_count,
        "low_count": low_count,
        "output": str(output_pdf),
    }
