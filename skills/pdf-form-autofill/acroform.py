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

    # Map fully-qualified field names to their page number and /Rect
    field_locations = {}
    raw_fields = reader.get_fields() or {}
    
    widget_to_page = {}
    for page_num, page in enumerate(reader.pages):
        annots = page.get("/Annots")
        if not annots: continue
        annots_obj = annots.get_object() if hasattr(annots, "get_object") else annots
        if isinstance(annots_obj, list):
            for annot_ref in annots_obj:
                widget_to_page[id(annot_ref.get_object())] = page_num

    for name, field in raw_fields.items():
        obj = field.get_object() if hasattr(field, "get_object") else field
        rect = obj.get("/Rect")
        page_num = widget_to_page.get(id(obj))
        
        if not rect and obj.get("/Kids"):
            for kid_ref in obj["/Kids"]:
                kid = kid_ref.get_object() if hasattr(kid_ref, "get_object") else kid_ref
                rect = kid.get("/Rect")
                page_num = widget_to_page.get(id(kid))
                if rect and page_num is not None:
                    break
        
        if rect and page_num is not None:
            field_locations[name] = {
                "page_num": page_num,
                "rect": (float(rect[0]), float(rect[1]), float(rect[2]), float(rect[3]))
            }

    adjacent_texts = {}
    if field_locations:
        import pdfplumber
        with pdfplumber.open(template_pdf) as pdf:
            pdf_pages = [p.extract_words() for p in pdf.pages]
            for name, loc in field_locations.items():
                page_num = loc["page_num"]
                if page_num >= len(pdf_pages): continue
                words = pdf_pages[page_num]
                ll_x, ll_y, ur_x, ur_y = loc["rect"]
                
                page = pdf.pages[page_num]
                p_x0, p_top = ll_x, page.height - ur_y
                p_x1, p_bottom = ur_x, page.height - ll_y
                
                adj_words = []
                for w in words:
                    w_x0, w_top, w_x1, w_bottom = w["x0"], w["top"], w["x1"], w["bottom"]
                    if (p_x0 - 200 <= w_x1 <= p_x0) and (p_top - 15 <= w_bottom and w_top <= p_bottom + 15):
                        adj_words.append(w)
                    elif (p_bottom <= w_top <= p_bottom + 60) and (p_x0 - 30 <= w_x1 and w_x0 <= p_x1 + 30):
                        adj_words.append(w)
                
                adj_words.sort(key=lambda w: (round(w["top"] / 5), w["x0"]))
                adjacent_texts[name] = " ".join(w["text"] for w in adj_words)

    text_fill_data: dict[str, str] = {}   # /Tx, /Ch, etc. — via update_page_form_field_values
    btn_fill_data: dict[str, str] = {}    # /Btn — written directly as NameObject /V
    sig_fill_data: dict[str, str] = {}    # Signatures to be drawn via reportlab
    field_results: list[dict] = []

    current_section_hint: str | None = None
    non_pcp_streak = 0
    fill_state = {"used_signatures": set()}
    today = datetime.date.today()

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

        adj_text = adjacent_texts.get(name, "")

        # If the AcroForm already has a value, skip filling it to prevent overwriting existing data
        if f.get("value"):
            continue

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
                name,
                alt,
                profile,
                index,
                today=today,
                section_hint=current_section_hint,
                adjacent_text=adj_text,
                fill_state=fill_state,
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
            "profile_null": fm_result.get("profile_null", False),
            "profile_null_path": fm_result.get("profile_null_path"),
        })
        if value is not None:
            if f.get("field_type") == "/Btn":
                btn_vals = f.get("btn_values") or []
                if btn_vals:
                    # Case-insensitive match to find the exact on-value casing
                    matched = next(
                        (v for v in btn_vals if v.lower() == str(value).lower()), None
                    )
                    if matched is not None:
                        btn_fill_data[name] = matched
                # /Btn without btn_values: skip (can't determine valid on-value)
            else:
                val_str = str(value)
                if val_str.startswith("[SIGNATURE_IMAGE") or val_str.startswith("[INITIALS_IMAGE"):
                    sig_fill_data[name] = val_str
                else:
                    text_fill_data[name] = value

    filled_count = sum(1 for r in field_results if not r["skipped"])
    skipped_count = sum(1 for r in field_results if r["skipped"])
    low_count = sum(1 for r in field_results if r.get("confidence") == "low")
    profile_null_fields = [
        {"name": r["name"], "profile_null_path": r["profile_null_path"]}
        for r in field_results if r.get("profile_null")
    ]

    if dry_run:
        return {
            "mode": "dry_run",
            "fields": field_results,
            "filled_count": filled_count,
            "skipped_count": skipped_count,
            "low_count": low_count,
            "profile_null_count": len(profile_null_fields),
            "profile_null_fields": profile_null_fields,
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

    if sig_fill_data:
        import io
        from reportlab.pdfgen import canvas
        from reportlab.lib.utils import ImageReader
        
        page_canvases = {}
        for fname, val_str in sig_fill_data.items():
            loc = field_locations.get(fname)
            if not loc: continue
            
            img_path = val_str.split("]:")[1]
            custom_scale = 1.0
            if ":" in val_str.split("]:")[0]:
                try:
                    custom_scale = float(val_str.split("]:")[0].split(":")[1])
                except ValueError:
                    pass
            
            page_num = loc["page_num"]
            if page_num not in page_canvases:
                page_canvases[page_num] = []
            page_canvases[page_num].append((loc["rect"], img_path, custom_scale))
            
        for page_num, sigs in page_canvases.items():
            packet = io.BytesIO()
            page = writer.pages[page_num]
            c = canvas.Canvas(packet, pagesize=(float(page.mediabox.width), float(page.mediabox.height)))
            
            for (ll_x, ll_y, ur_x, ur_y), img_path, custom_scale in sigs:
                if not Path(img_path).exists():
                    print(f"Signature image not found: {img_path}")
                    continue
                
                w = ur_x - ll_x
                h = ur_y - ll_y
                try:
                    img = ImageReader(img_path)
                    img_w, img_h = img.getSize()
                    scale = min(w / img_w, h / img_h) * custom_scale
                    scaled_w = img_w * scale
                    scaled_h = img_h * scale
                    
                    draw_x = ll_x + (w - scaled_w) / 2
                    draw_y = ll_y + (h - scaled_h) / 2
                    
                    c.drawImage(img_path, draw_x, draw_y, width=scaled_w, height=scaled_h, mask='auto')
                except Exception as e:
                    print(f"Failed to draw signature {img_path}: {e}")
                    
            c.save()
            packet.seek(0)
            overlay_pdf = pypdf.PdfReader(packet)
            writer.pages[page_num].merge_page(overlay_pdf.pages[0])

    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    with output_pdf.open("wb") as out:
        writer.write(out)

    return {
        "mode": "filled",
        "fields": field_results,
        "filled_count": filled_count,
        "skipped_count": skipped_count,
        "low_count": low_count,
        "profile_null_count": len(profile_null_fields),
        "profile_null_fields": profile_null_fields,
        "output": str(output_pdf),
    }
