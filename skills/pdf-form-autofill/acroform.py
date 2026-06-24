"""Fill AcroForm PDFs using pypdf."""

from __future__ import annotations

import datetime
import re
from pathlib import Path

import pypdf

import field_mapper as _fm  # same directory, added to sys.path by CLI entry point

_PCP_SECTION_KEYWORDS = {"physician", "doctor", "pcp", "provider", "practice", "clinic"}


def _normalize_section(text: str) -> str:
    """Lowercase + strip non-alpha/digit, used only for section-hint detection."""
    return re.sub(r"[^a-z0-9 ]", " ", text.lower())


def _get_btn_values(obj: pypdf.generic.DictionaryObject) -> list[str]:
    """Return the valid on-values for a /Btn field from /AP or /Opt or /Kids."""
    values: list[str] = []

    def _ap_keys(d: object) -> list[str]:
        d_obj = d.get_object() if hasattr(d, "get_object") else d  # type: ignore[attr-defined]
        if not isinstance(d_obj, pypdf.generic.DictionaryObject):
            return []
        n = d_obj.get("/N")
        if n is None:
            return []
        n_obj = n.get_object() if hasattr(n, "get_object") else n
        if not isinstance(n_obj, pypdf.generic.DictionaryObject):
            return []
        return [k.lstrip("/") for k in n_obj.keys() if k != "/Off"]

    # /AP on the field itself (checkbox)
    ap = obj.get("/AP")
    if ap is not None:
        values = _ap_keys(ap)

    # /Opt (checkbox list or multi-select)
    if not values:
        opt = obj.get("/Opt")
        if opt is not None:
            opt_obj = opt.get_object() if hasattr(opt, "get_object") else opt
            if isinstance(opt_obj, (list, pypdf.generic.ArrayObject)):
                for item in opt_obj:
                    v = item.get_object() if hasattr(item, "get_object") else item
                    values.append(str(v))

    # /Kids — radio group; each kid widget carries its own /AP /N on-value
    if not values:
        kids = obj.get("/Kids")
        if kids is not None:
            kids_obj = kids.get_object() if hasattr(kids, "get_object") else kids
            for kid_ref in kids_obj:
                kid = kid_ref.get_object() if hasattr(kid_ref, "get_object") else kid_ref
                if isinstance(kid, pypdf.generic.DictionaryObject):
                    ap = kid.get("/AP")
                    if ap is not None:
                        for v in _ap_keys(ap):
                            if v not in values:
                                values.append(v)

    return values


def _get_acroform_fields(reader: pypdf.PdfReader) -> list[dict]:
    """Extract all AcroForm fields with name, alt text, type, current value, and btn_values."""
    fields = []
    root = reader.trailer.get("/Root", {})
    if "/AcroForm" not in root:
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
        field_type = str(field.get("/FT", ""))
        btn_values: list[str] = []
        if field_type == "/Btn" and isinstance(obj, pypdf.generic.DictionaryObject):
            btn_values = _get_btn_values(obj)
        fields.append({
            "name": name,
            "alt": alt_text,
            "field_type": field_type,
            "value": field.get("/V"),
            "btn_values": btn_values,
        })
    return fields


def fill(
    template_pdf: Path,
    profile: dict,
    index: dict,
    output_pdf: Path,
    dry_run: bool = True,
    skip_confidences: frozenset = frozenset(),
    field_overrides: dict | None = None,
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
          - 'fields': list of field result dicts (name, alt, mapped_value,
              confidence, source, alternatives, notes, skipped)
          - 'filled_count': int   — fields with a mapped value
          - 'skipped_count': int  — fields with no mapped value (confidence 'none')
          - 'low_count': int      — fields with confidence 'low'
          - 'output': str path    — only present when not dry_run
    """
    reader = pypdf.PdfReader(str(template_pdf))
    fields = _get_acroform_fields(reader)

    text_fill_data: dict[str, str] = {}   # /Tx, /Ch, etc. — via update_page_form_field_values
    btn_fill_data: dict[str, str] = {}    # /Btn — written directly as NameObject /V
    field_results: list[dict] = []

    current_section_hint: str | None = None
    non_pcp_streak = 0

    for f in fields:
        name = f["name"]
        alt = f["alt"]

        # Track PCP section context across consecutive fields
        norm_name = _normalize_section(name)
        if any(kw in norm_name for kw in _PCP_SECTION_KEYWORDS):
            current_section_hint = "pcp"
            non_pcp_streak = 0
        else:
            non_pcp_streak += 1
            if non_pcp_streak >= 3:
                current_section_hint = None

        if field_overrides and name in field_overrides:
            override_val = field_overrides[name]
            fm_result = {
                "value": override_val,
                "confidence": "high" if override_val is not None else "none",
                "source": "user via interview",
                "alternatives": [],
                "notes": [],
            }
        else:
            fm_result = _fm.map_pdf_field(
                name, alt, profile, index,
                today=datetime.date.today(),
                section_hint=current_section_hint,
            )

        if skip_confidences and fm_result.get("confidence") in skip_confidences:
            fm_result = dict(fm_result)
            fm_result["value"] = None

        value = fm_result["value"]
        skipped = value is None
        field_results.append({
            "name": name,
            "alt": alt,
            "mapped_value": value,
            "confidence": fm_result["confidence"],
            "source": fm_result["source"],
            "alternatives": fm_result["alternatives"],
            "notes": fm_result["notes"],
            "skipped": skipped,
        })
        if value is not None:
            if f.get("field_type") == "/Btn":
                btn_vals = f.get("btn_values") or []
                if btn_vals:
                    # Case-insensitive match to find the exact on-value casing
                    matched = next(
                        (v for v in btn_vals if v.lower() == value.lower()), None
                    )
                    if matched is not None:
                        btn_fill_data[name] = matched
                # /Btn without btn_values: skip (can't determine valid on-value)
            else:
                text_fill_data[name] = value

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

    # Write filled PDF — clone_from preserves the /AcroForm root dictionary
    writer = pypdf.PdfWriter(clone_from=str(template_pdf))

    # Text / choice fields: use the standard API across all pages
    if text_fill_data:
        for page in writer.pages:
            writer.update_page_form_field_values(page, text_fill_data)

    # /Btn fields: write /V directly as NameObject (avoids /AP requirement)
    if btn_fill_data:
        raw = writer.get_fields() or {}
        for fname, on_value in btn_fill_data.items():
            field_obj = raw.get(fname)
            if field_obj is None:
                continue
            fref = field_obj.get_object() if hasattr(field_obj, "get_object") else field_obj
            if isinstance(fref, pypdf.generic.DictionaryObject):
                fref[pypdf.generic.NameObject("/V")] = pypdf.generic.NameObject(
                    f"/{on_value}"
                )
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    with output_pdf.open("wb") as out:
        writer.write(out)

    return {
        "mode": "filled",
        "fields": field_results,
        "filled_count": filled_count,
        "skipped_count": skipped_count,
        "low_count": low_count,
        "output": str(output_pdf),
    }
