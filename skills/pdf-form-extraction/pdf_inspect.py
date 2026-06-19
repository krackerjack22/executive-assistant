"""pypdf + pdfplumber helpers for PDF field inspection."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def get_acroform_fields(pdf_path: Path) -> list[dict]:
    """Extract all AcroForm fields from a PDF using pypdf.

    Returns a list of dicts with keys: name, alt, field_type, value, page_index.
    Returns empty list if no AcroForm is present.
    """
    import pypdf
    import pypdf.generic

    reader = pypdf.PdfReader(str(pdf_path))
    raw_fields = reader.get_fields()
    if not raw_fields:
        return []

    results = []
    for name, field in raw_fields.items():
        obj = field.get_object() if hasattr(field, "get_object") else field
        alt_text = ""
        if isinstance(obj, pypdf.generic.DictionaryObject):
            tu = obj.get("/TU")
            if tu:
                alt_text = str(tu)
        results.append({
            "name": name,
            "alt": alt_text,
            "field_type": str(field.get("/FT", "")),
            "value": field.get("/V"),
        })
    return results


def has_acroform(pdf_path: Path) -> bool:
    """Return True if the PDF contains an AcroForm."""
    import pypdf
    reader = pypdf.PdfReader(str(pdf_path))
    root = reader.trailer.get("/Root", {})
    return "/AcroForm" in root


def get_spatial_map(pdf_path: Path) -> list[dict]:
    """Extract a spatial word map from all pages using pdfplumber.

    Returns a list of dicts: {page, x0, y0, x1, y1, text}.
    Useful for non-AcroForm PDFs and for verifying field positions.
    """
    import pdfplumber

    words = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_num, page in enumerate(pdf.pages):
            for word in (page.extract_words() or []):
                words.append({
                    "page": page_num,
                    "x0": round(word["x0"], 2),
                    "y0": round(word["top"], 2),
                    "x1": round(word["x1"], 2),
                    "y1": round(word["bottom"], 2),
                    "text": word["text"],
                })
    return words


def get_page_count(pdf_path: Path) -> int:
    """Return the number of pages."""
    import pypdf
    return len(pypdf.PdfReader(str(pdf_path)).pages)
