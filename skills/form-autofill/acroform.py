"""Fill AcroForm PDFs using pypdf."""

from __future__ import annotations

import copy
from pathlib import Path

import pypdf
import pypdf.generic

from lib import address_resolver as _ar
import field_mapper as _fm  # same directory, added to sys.path by CLI entry point


def _get_acroform_fields(reader: pypdf.PdfReader) -> list[dict]:
    """Extract all AcroForm fields with name, alt text, type, and current value."""
    fields = []
    acroform = reader.trailer.get("/Root", {}).get("/AcroForm")
    if acroform is None:
        return fields

    raw_fields = reader.get_fields()
    if not raw_fields:
        return fields

    for name, field in raw_fields.items():
        obj = field.get_object() if hasattr(field, "get_object") else field
        alt_text = ""
        if isinstance(obj, pypdf.generic.DictionaryObject):
            tu = obj.get("/TU")
            if tu:
                alt_text = str(tu)
        fields.append({
            "name": name,
            "alt": alt_text,
            "field_type": str(field.get("/FT", "")),
            "value": field.get("/V"),
        })
    return fields


def fill(
    template_pdf: Path,
    profile: dict,
    index: dict,
    output_pdf: Path,
    dry_run: bool = True,
) -> dict:
    """Fill an AcroForm PDF from a resolved profile.

    Args:
        template_pdf: path to blank AcroForm PDF.
        profile: fully resolved profile dict.
        index: profiles_index dict.
        output_pdf: where to write the filled PDF (ignored in dry_run).
        dry_run: if True, return preview dict only; do not write.

    Returns:
        dict with keys:
          - 'mode': 'dry_run' | 'filled'
          - 'fields': list of {name, alt, mapped_value, source, skipped}
          - 'filled_count': int
          - 'skipped_count': int
          - 'output': str path (only when not dry_run)
    """
    reader = pypdf.PdfReader(str(template_pdf))
    fields = _get_acroform_fields(reader)

    fill_data: dict[str, str] = {}
    field_results: list[dict] = []

    for f in fields:
        name = f["name"]
        alt = f["alt"]
        value, source = _fm.map_pdf_field(name, alt, profile, index)
        skipped = value is None
        field_results.append({
            "name": name,
            "alt": alt,
            "mapped_value": value,
            "source": source,
            "skipped": skipped,
        })
        if value is not None:
            fill_data[name] = value

    filled_count = sum(1 for r in field_results if not r["skipped"])
    skipped_count = sum(1 for r in field_results if r["skipped"])

    if dry_run:
        return {
            "mode": "dry_run",
            "fields": field_results,
            "filled_count": filled_count,
            "skipped_count": skipped_count,
        }

    # Write filled PDF — clone_from preserves the /AcroForm root dictionary
    writer = pypdf.PdfWriter(clone_from=str(template_pdf))
    writer.update_page_form_field_values(writer.pages[0], fill_data)
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    with output_pdf.open("wb") as out:
        writer.write(out)

    return {
        "mode": "filled",
        "fields": field_results,
        "filled_count": filled_count,
        "skipped_count": skipped_count,
        "output": str(output_pdf),
    }
