import pdfplumber

# A page with fewer than this many vector blanks is treated as having no usable
# vector geometry. Scanned pages usually yield exactly 0; a handful of stray
# hits (a logo outline, a stamp) should not suppress the raster pass.
_VECTOR_BLANK_FLOOR = 2


def dedupe_chars(s: str) -> str:
    res = []
    for c in s:
        if not res or res[-1] != c: res.append(c)
    return "".join(res)


def get_vector_blanks(page):
    """Blanks recoverable from the PDF's own vector graphics and text layer."""
    blanks = []
    
    # 1. page.rects (Lines, Checkboxes, Segmented Cells)
    for r in page.rects:
        w = r['x1'] - r['x0']
        h = r['bottom'] - r['top']
        
        if h < 5 and w > 10:
            blanks.append({"x0": r['x0'], "x1": r['x1'], "top": r['top'], "bottom": r['bottom'], "type": "line"})
        elif 5 <= h <= 15 and 5 <= w <= 15 and abs(w - h) < 4:
            blanks.append({"x0": r['x0'], "x1": r['x1'], "top": r['top'], "bottom": r['bottom'], "type": "checkbox"})
        elif 10 < h < 40 and 5 < w < 30:
            blanks.append({"x0": r['x0'], "x1": r['x1'], "top": r['top'], "bottom": r['bottom'], "type": "segmented_cell"})
            
    # 2. page.lines (Explicit vector lines)
    for l in page.lines:
        w = abs(l['x1'] - l['x0'])
        h = abs(l['bottom'] - l['top'])
        if h < 5 and w > 10:
            blanks.append({"x0": min(l['x0'], l['x1']), "x1": max(l['x0'], l['x1']), "top": l['top'], "bottom": l['bottom'], "type": "line"})
            
    # 3. page.curves (Curved vector lines acting as straight lines)
    for c in page.curves:
        pts = c.get('pts', [])
        if len(pts) >= 2:
            y_coords = [p[1] for p in pts]
            if max(y_coords) - min(y_coords) < 5:
                x_coords = [p[0] for p in pts]
                w = max(x_coords) - min(x_coords)
                if w > 10:
                    blanks.append({"x0": min(x_coords), "x1": max(x_coords), "top": min(y_coords), "bottom": max(y_coords), "type": "line"})
                    
    # 4. Underscores (OCR chars)
    underscores = sorted([c for c in page.chars if c['text'] == '_'], key=lambda c: (c['top'], c['x0']))
    if underscores:
        current_group = [underscores[0]]
        for u in underscores[1:]:
            last = current_group[-1]
            if abs(u['top'] - last['top']) < 5 and u['x0'] - last['x1'] < 5:
                current_group.append(u)
            else:
                w = current_group[-1]['x1'] - current_group[0]['x0']
                if w > 10:
                    blanks.append({"x0": current_group[0]['x0'], "x1": current_group[-1]['x1'], "top": min(c['top'] for c in current_group), "bottom": max(c['bottom'] for c in current_group), "type": "underscore"})
                current_group = [u]
        w = current_group[-1]['x1'] - current_group[0]['x0']
        if w > 10:
            blanks.append({"x0": current_group[0]['x0'], "x1": current_group[-1]['x1'], "top": min(c['top'] for c in current_group), "bottom": max(c['bottom'] for c in current_group), "type": "underscore"})

    return blanks


def _page_source_path(page):
    """Best-effort filesystem path backing a pdfplumber page, or None."""
    return getattr(getattr(page.pdf, "stream", None), "name", None)


def get_blanks(page, allow_vision: bool = True):
    """Detect fill-in rules and checkboxes on a page.

    Prefers the PDF's own vector geometry. When a page carries no usable vector
    blanks -- the signature of a scanned or flattened-to-image form -- falls
    back to locating the same geometry with Gemini vision. Both paths emit
    identical dicts, so callers need not care which ran.
    """
    blanks = get_vector_blanks(page)

    if allow_vision and len(blanks) < _VECTOR_BLANK_FLOOR:
        source = _page_source_path(page)
        if source:
            try:
                import vision_blanks

                blanks = vision_blanks.detect_blanks(
                    source,
                    page.page_number,
                    words=page.extract_words(),
                )
                for b in blanks:
                    b["source"] = "vision"
            except Exception as exc:  # pragma: no cover - diagnostics only
                print(f"[Blanks Extractor] Vision fallback failed: {exc}")

    # Sort blanks by top, then left to right
    blanks.sort(key=lambda b: (b['top'], b['x0']))
    return blanks
