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


def _run_ocr_workflow(template_pdf: Path, pdf) -> dict[int, list[dict]]:
    import sys
    import json
    import base64
    import tempfile
    import urllib.request
    from pathlib import Path
    import os

    if not sys.stdin.isatty():
        raise ValueError(
            "This PDF appears to be a scanned image with no embedded text. "
            "Please run this tool in an interactive terminal to perform automated OCR, "
            "or manually OCR the file in Mac Preview / Adobe Acrobat and re-run."
        )

    print("\nThis PDF appears to be a scanned image with no embedded text.")
    print("How would you like to proceed?")
    print("  [M]anual OCR (open in Acrobat/Preview, save, and re-run)")
    print("  [A]utomated OCR via Native Agent Vision / Gemini API")
    print("Choice [M/A]: ", end="", flush=True)
    choice = input().strip().upper()

    if choice != "A":
        print("\nPlease manually OCR the PDF, save it, and run the tool again.")
        sys.exit(0)

    # Export images
    tmp_dir = Path(tempfile.mkdtemp(prefix="executive-assistant-ocr-"))
    image_paths = []
    print(f"\nExporting {len(pdf.pages)} pages to images for OCR...")
    for i, page in enumerate(pdf.pages):
        img_obj = page.to_image(resolution=150)
        img_path = tmp_dir / f"page_{i}.png"
        img_obj.original.save(str(img_path))
        image_paths.append(img_path)

    print("\n[AGENT INSTRUCTION]")
    print("Please use your vision capabilities to analyze the following images:")
    for path in image_paths:
        print(f"  - {path}")
    print("Provide a JSON array containing one sub-array per page.")
    print("Each sub-array must contain every word and its bounding box on that page.")
    print("Format: [[{\"text\": \"Word\", \"x0\": float, \"top\": float, \"x1\": float, \"bottom\": float}], ...]")
    print("IMPORTANT: Coordinate values must be relative to the original PDF page size in points (top-left origin).")
    for i, p in enumerate(pdf.pages):
        print(f"  Page {i}: {float(p.width)} x {float(p.height)}")
    print("\nPaste the JSON below and type END_JSON on a new line.")
    print("If you cannot reliably output PDF-point coordinates, type 'fallback' and press Enter to use the Gemini API:")

    lines = []
    while True:
        try:
            line = input()
            if line.strip() == "fallback":
                lines = ["fallback"]
                break
            if line.strip() == "END_JSON":
                break
            lines.append(line)
        except EOFError:
            break

    response_text = "\n".join(lines).strip()
    words_by_page = defaultdict(list)

    if response_text == "fallback":
        # Gemini API fallback
        print("\nFalling back to Gemini Vision API...")
        
        # Load .env manually if missing from os.environ
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            env_path = template_pdf.parent.parent.parent / ".env"
            # Attempt to find the project root .env
            current = Path.cwd()
            while current != current.parent:
                if (current / ".env").exists():
                    env_path = current / ".env"
                    break
                current = current.parent
                
            if env_path.exists():
                with open(env_path) as f:
                    for eline in f:
                        eline = eline.strip()
                        if eline.startswith("GEMINI_API_KEY="):
                            api_key = eline.split("=", 1)[1].strip('"\'')
                            break

        if not api_key:
            print(
                "\nError: GEMINI_API_KEY is missing. "
                "Please add it to the .env file within the repository root to use the OCR fallback."
            )
            sys.exit(1)

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"

        for page_num, (img_path, pdf_page) in enumerate(zip(image_paths, pdf.pages)):
            print(f"  Processing page {page_num + 1} / {len(image_paths)}...")
            with open(img_path, "rb") as f:
                b64_img = base64.b64encode(f.read()).decode("utf-8")

            prompt = f"""
Return a JSON array of all words on this document page.
Each object must have:
- "text": the word text
- "x0": the left coordinate (in points)
- "x1": the right coordinate (in points)
- "top": the top coordinate (in points)
- "bottom": the bottom coordinate (in points)

The page dimensions in points are: width = {float(pdf_page.width)}, height = {float(pdf_page.height)}.
Ensure the coordinates match these bounds accurately (top-left origin).
"""
            data = {
                "contents": [{
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": "image/png", "data": b64_img}}
                    ]
                }],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "responseSchema": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "text": {"type": "STRING"},
                                "x0": {"type": "NUMBER"},
                                "x1": {"type": "NUMBER"},
                                "top": {"type": "NUMBER"},
                                "bottom": {"type": "NUMBER"}
                            },
                            "required": ["text", "x0", "x1", "top", "bottom"]
                        }
                    }
                }
            }

            req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req) as response:
                    res_body = json.loads(response.read().decode("utf-8"))
                    text_out = res_body["candidates"][0]["content"]["parts"][0]["text"]
                    words = json.loads(text_out)
                    for w in words:
                        words_by_page[page_num].append({
                            "text": str(w.get("text", "")),
                            "x0": float(w.get("x0", 0)),
                            "x1": float(w.get("x1", 0)),
                            "y0": float(w.get("top", 0)),
                            "y1": float(w.get("bottom", 0)),
                        })
            except Exception as e:
                print(f"\nError calling Gemini API on page {page_num}: {e}")
                sys.exit(1)
                
        print("OCR complete.")
        return words_by_page
    else:
        # Agent provided JSON
        try:
            # Extract JSON from potential markdown blocks
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
                
            parsed = json.loads(response_text)
            if not isinstance(parsed, list):
                raise ValueError("Expected a top-level JSON array.")
                
            for page_num, page_words in enumerate(parsed):
                for w in page_words:
                    words_by_page[page_num].append({
                        "text": str(w.get("text", "")),
                        "x0": float(w.get("x0", 0)),
                        "x1": float(w.get("x1", 0)),
                        "y0": float(w.get("top", 0)),
                        "y1": float(w.get("bottom", 0)),
                    })
            print("Successfully parsed agent OCR data.")
            return words_by_page
        except Exception as e:
            print(f"\nFailed to parse JSON from agent: {e}")
            print("Aborting. Please try again or use manual OCR.")
            sys.exit(1)


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
    has_images = False
    
    with pdfplumber.open(str(template_pdf)) as pdf:
        for page_num, page in enumerate(pdf.pages):
            if page.images:
                has_images = True
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

        has_words = any(bool(words) for words in words_by_page.values())
        if not has_words:
            if has_images:
                words_by_page = _run_ocr_workflow(template_pdf, pdf)
            else:
                raise ValueError(
                    "This PDF contains no text and no images. It is completely blank "
                    "or empty and cannot be processed."
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
