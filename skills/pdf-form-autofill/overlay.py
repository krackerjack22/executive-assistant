"""Spatial overlay fill for flattened (non-AcroForm) PDFs using structural heuristics."""

from __future__ import annotations

import datetime
import io
from collections import defaultdict
from pathlib import Path

import pypdf
import pdfplumber

_FONT_SIZE = 11

def _write_overlay(
    template_pdf: Path,
    output_pdf: Path,
    instructions: list[dict],
    page_heights: dict[int, float],
    page_widths: dict[int, float],
) -> dict[str, dict]:
    """Stamp text overlays onto template PDF pages and write output. Returns dict of rendered bounding boxes."""
    from reportlab.pdfgen import canvas as _rl_canvas
    from reportlab.lib.utils import ImageReader

    rendered_boxes = {}

    by_page: dict[int, list[dict]] = defaultdict(list)
    for inst in instructions:
        by_page[inst["page"]].append(inst)

    writer = pypdf.PdfWriter(clone_from=str(template_pdf))

    for page_num, page_insts in by_page.items():
        page_h = page_heights[page_num]
        page_w = page_widths[page_num]
        
        # pypdf page indexing is 0-based.
        pdf_page_idx = page_num - 1

        buf = io.BytesIO()
        c = _rl_canvas.Canvas(buf, pagesize=(page_w, page_h))
        c.setFillColorRGB(0, 0, 0.5) # Navy Blue
        
        for inst in page_insts:
            val = str(inst["text"])
            if not val or "x" not in inst:
                continue
                
            x = float(inst["x"])
            y = float(inst["y"])
            
            # Checkbox handling
            if inst.get("is_checkbox"):
                c.setFont("Helvetica", 14)
                sw = c.stringWidth(val, "Helvetica", 14)
                c.drawString(x - (sw/2), y - 4, val)
                rendered_boxes[inst.get("label", "")] = {
                    "page": inst["page"], "x0": x - (sw/2), "y0": page_h - y + 4 - 14, "x1": x + (sw/2), "y1": page_h - y + 4
                }
                continue
                
            if val.startswith("[SIGNATURE_IMAGE") or val.startswith("[INITIALS_IMAGE"):
                img_path = val.split("]:", 1)[1].strip()
                if not Path(img_path).exists():
                    print(f"Signature image not found: {img_path}")
                    continue
                try:
                    img = ImageReader(img_path)
                    img_w, img_h = img.getSize()
                    
                    custom_scale = 1.0
                    if ":" in val.split("]:")[0]:
                        try:
                            custom_scale = float(val.split("]:")[0].split(":")[1])
                        except ValueError:
                            pass
                            
                    default_w = 100.0 if val.startswith("[SIGNATURE") else 40.0
                        
                    scale = (default_w / img_w) * custom_scale
                    scaled_w = img_w * scale
                    scaled_h = img_h * scale
                    
                    draw_y = y - (scaled_h * 0.20)
                    if val.startswith("[INITIALS"):
                        draw_y = y - (scaled_h * 0.04)
                    
                    c.drawImage(img_path, x, draw_y, width=scaled_w, height=scaled_h, mask='auto')
                    rendered_boxes[inst.get("label", "")] = {
                        "page": inst["page"], "x0": x, "y0": page_h - draw_y - scaled_h, "x1": x + scaled_w, "y1": page_h - draw_y
                    }
                except Exception as e:
                    print(f"Error drawing image: {e}")
            else:
                c.setFont("Helvetica", _FONT_SIZE)
                c.drawString(x, y + 2, val)
                sw = c.stringWidth(val, "Helvetica", _FONT_SIZE)
                rendered_boxes[inst.get("label", "")] = {
                    "page": inst["page"], "x0": x, "y0": page_h - y - 2 - _FONT_SIZE, "x1": x + sw, "y1": page_h - y - 2
                }
                
        c.save()
        buf.seek(0)

        overlay_reader = pypdf.PdfReader(buf)
        writer.pages[pdf_page_idx].merge_page(overlay_reader.pages[0])

    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    with output_pdf.open("wb") as f:
        writer.write(f)

    return rendered_boxes


def fill(
    template_pdf: Path,
    profile: dict,
    index: dict,
    output_pdf: Path,
    dry_run: bool = True,
    skip_confidences: frozenset = frozenset(),
    field_overrides: dict | None = None,
) -> dict:
    reader = pypdf.PdfReader(str(template_pdf))
    root = reader.trailer.get("/Root", {})
    if "/AcroForm" in root:
        raise ValueError("use acroform.fill() for AcroForm PDFs")

    page_heights = {i+1: float(p.mediabox.height) for i, p in enumerate(reader.pages)}
    page_widths = {i+1: float(p.mediabox.width) for i, p in enumerate(reader.pages)}

    import field_mapper as _fm
    import schema_extractor
    import anchor_mapper

    # 1. Get the JSON schema of fields from the layout-aware LLM extractor
    schema = schema_extractor.get_or_create_schema(template_pdf)
    
    field_results: list[dict] = []
    today = datetime.date.today()
    fill_state = {"used_signatures": set()}
    
    anchor_payload = []

    # 2. Map each logical field to the user's profile database
    for item in schema:
        label = item.get("label")
        if not label: continue
        
        if field_overrides and label in field_overrides:
            override = field_overrides[label]
            if isinstance(override, dict):
                override_val = override.get("value")
                # Attach nudges to the item so anchor logic can use it later
                item["_x_nudge"] = override.get("x_offset", 0)
                item["_y_nudge"] = override.get("y_offset", 0)
            else:
                override_val = override
                
            fm_result = {
                "value": override_val,
                "confidence": "high" if override_val is not None else "none",
                "source": "user via interview or QA",
                "alternatives": [],
                "notes": [],
            }
        else:
            fm_result = _fm.map_pdf_field(
                label,
                label,
                profile,
                index,
                today=today,
                fill_state=fill_state,
            )
            
        if skip_confidences and fm_result.get("confidence") in skip_confidences:
            fm_result = dict(fm_result)
            fm_result["value"] = None

        value = fm_result["value"]
        
        if item.get("is_checkbox"):
            if str(value).lower() in ("true", "yes", "1", "x", "on"):
                value = "X"
            elif str(value).lower() in ("false", "no", "0", "off", "none", ""):
                value = None
            elif value is not None:
                # Fallback: if there's *any* other value, assume it means checked
                value = "X"
                
        skipped = value is None

        field_results.append({
            "name": label,
            "alt": label,
            "mapped_value": value,
            "confidence": fm_result["confidence"],
            "source": fm_result["source"],
            "alternatives": fm_result["alternatives"],
            "notes": fm_result["notes"],
            "skipped": skipped,
        })
        
        if not skipped:
            anchor_payload.append({
                "label": label,
                "text": value,
                "page": item.get("page", 1),
                "is_checkbox": item.get("is_checkbox", False),
                "_x_nudge": item.get("_x_nudge", 0),
                "_y_nudge": item.get("_y_nudge", 0),
            })

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

    # 3. Geometrically anchor the text using our new heuristic engine
    coords = anchor_mapper.get_anchor_coordinates(template_pdf, anchor_payload)
    
    fill_instructions = []
    for item in anchor_payload:
        label = item["label"]
        if label in coords:
            c = coords[label]
            page_h = page_heights[item["page"]]
            fill_instructions.append({
                "label": label,
                "page": item["page"],
                "x": c["x"] + item.get("_x_nudge", 0),
                "y": (page_h - c["bottom"]) + item.get("_y_nudge", 0),
                "text": item["text"],
                "is_checkbox": item.get("is_checkbox")
            })
        else:
            print(f"[Overlay] Warning: Failed to find geometric anchor for '{label}'. Skipping.")

    # 4. Stamp text onto the PDF
    rendered_boxes = _write_overlay(template_pdf, output_pdf, fill_instructions, page_heights, page_widths)
    
    # Attach bounding boxes to field_results
    for res in field_results:
        label = res["name"]
        if label in rendered_boxes:
            res["rendered_bbox"] = rendered_boxes[label]

    return {
        "mode": "filled",
        "fields": field_results,
        "filled_count": filled_count,
        "skipped_count": skipped_count,
        "low_count": low_count,
        "output": str(output_pdf),
    }
