"""Gemini 1.5 Spatial Bounding Box extraction for PDF forms.

Sends a blank PDF page to Gemini 1.5 Flash and requests the exact bounding box
[ymin, xmin, ymax, xmax] of the visual underscore lines or checkboxes corresponding
to specific field labels.
"""

from __future__ import annotations

import json
import os
import io
from pathlib import Path

_DEFAULT_MODEL = "gemini-2.5-flash"

def get_spatial_coordinates(
    blank_pdf_path: Path,
    fields_to_locate: list[dict],
    model: str = _DEFAULT_MODEL,
) -> dict[str, dict]:
    """Call Gemini Vision to extract bounding boxes for target fields.

    Args:
        blank_pdf_path: Path to the template PDF (unfilled).
        fields_to_locate: List of field dictionaries containing 'label'.
        model: Gemini model ID.
    
    Returns:
        Mapping of {label: {"x": float, "bottom": float, "is_checkbox": bool}}
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set.")

    try:
        from google import genai
        from google.genai import types
        import PIL.Image
        import pdfplumber
    except ImportError:
        raise RuntimeError("google-genai, pillow, and pdfplumber are required.")

    # Convert pages to images
    pages_images = []
    page_dims = []
    with pdfplumber.open(str(blank_pdf_path)) as pdf:
        for p in pdf.pages:
            pages_images.append(p.to_image(resolution=150).original)
            page_dims.append({"w": float(p.width), "h": float(p.height)})
            
    client = genai.Client(api_key=api_key)
    
    # We will process each page's fields
    page_fields = {}
    for f in fields_to_locate:
        p = f.get("page", 1)
        if p not in page_fields:
            page_fields[p] = []
        page_fields[p].append(f)
        
    results = {}
    
    for page_num, fields in page_fields.items():
        if page_num > len(pages_images):
            continue
            
        img = pages_images[page_num - 1]
        dims = page_dims[page_num - 1]
        
        # Build prompt
        field_lines = []
        for f in fields:
            t = "checkbox" if f.get("is_checkbox") else "underscore line"
            field_lines.append(f"- \"{f['label']}\" (Type: {t})")
            
        prompt = (
            "You are a spatial bounding box extractor. I will give you a blank form image "
            "and a list of fields. For each field, you must locate the visual blank space "
            "(either an underscore line or a square checkbox) where the user is supposed "
            "to write their answer.\n\n"
            "Fields to locate:\n"
            + "\n".join(field_lines) + "\n\n"
            "Rules:\n"
            "1. You must return a JSON array of objects.\n"
            "2. Each object MUST have a 'label' exactly matching the list above.\n"
            "3. Each object MUST have a 'box' array: [ymin, xmin, ymax, xmax] scaled to 1000x1000.\n"
            "4. The box MUST tightly surround the underscore line itself, or the square checkbox itself, NOT the text label.\n"
            "5. Do not include markdown code block syntax (like ```json), just output the raw JSON array.\n"
        )
        
        try:
            resp = client.models.generate_content(
                model=model,
                contents=[img, prompt],
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    response_mime_type="application/json",
                )
            )
            
            raw_text = resp.text
            if not raw_text:
                continue

            try:
                boxes = json.loads(raw_text.strip())
            except json.JSONDecodeError as e:
                print(f"[Spatial Mapper] JSON error: {e}\nRaw: {raw_text}")
                continue
                
            for b in boxes:
                label = b.get("label")
                box = b.get("box")
                if not label or not box or len(box) != 4:
                    continue
                    
                ymin, xmin, ymax, xmax = box
                
                # Convert 1000x1000 to PDF points
                pdf_w = dims["w"]
                pdf_h = dims["h"]
                
                real_ymin = (ymin / 1000.0) * pdf_h
                real_xmin = (xmin / 1000.0) * pdf_w
                real_ymax = (ymax / 1000.0) * pdf_h
                real_xmax = (xmax / 1000.0) * pdf_w
                
                # For an underscore line, the y-baseline is the bottom of the bounding box (ymax).
                # But wait, PDF coordinates are from bottom-left (y=0 is bottom).
                # The LLM's [ymin, xmin, ymax, xmax] usually has y=0 at TOP.
                # So ymax in LLM is the bottom of the line on screen.
                # In PDF coords (origin bottom-left): real_bottom = pdf_h - real_ymax
                
                bottom = pdf_h - real_ymax
                x = real_xmin
                
                # If it's a checkbox, we want the center
                is_cb = False
                for f in fields:
                    if f["label"] == label:
                        is_cb = f.get("is_checkbox", False)
                        break
                        
                if is_cb:
                    center_y_screen = (ymin + ymax) / 2.0
                    center_x_screen = (xmin + xmax) / 2.0
                    
                    real_center_y = (center_y_screen / 1000.0) * pdf_h
                    bottom = pdf_h - real_center_y # center in PDF Y
                    
                    x = (center_x_screen / 1000.0) * pdf_w
                    
                results[label] = {
                    "x": x,
                    "bottom": bottom,
                    "is_checkbox": is_cb
                }
                print(f"[Spatial Mapper] Mapped '{label}' to x={x:.1f}, bottom={bottom:.1f}")
                
        except Exception as e:
            print(f"[Spatial Mapper] Error processing page {page_num}: {e}")
            
    return results
