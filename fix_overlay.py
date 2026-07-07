import re

with open("skills/pdf-form-autofill/overlay.py", "r") as f:
    content = f.read()

# 1. Update _group_into_lines to split on 40px gaps
new_group_into_lines = """def _group_into_lines(words: list[dict]) -> list[list[dict]]:
    \"\"\"Group words into lines based on vertical proximity and horizontal gaps.\"\"\"
    if not words:
        return []
    sorted_words = sorted(words, key=lambda w: (w["y0"], w["x0"]))
    lines = []
    current = [sorted_words[0]]
    for word in sorted_words[1:]:
        if abs(word["y0"] - current[0]["y0"]) <= _LINE_CLUSTER_TOL:
            # Check horizontal gap
            if current and word["x0"] - current[-1]["x1"] > 40.0:
                lines.append(sorted(current, key=lambda w: w["x0"]))
                current = [word]
            else:
                current.append(word)
        else:
            lines.append(sorted(current, key=lambda w: w["x0"]))
            current = [word]
    lines.append(sorted(current, key=lambda w: w["x0"]))
    return lines"""

content = re.sub(r'def _group_into_lines.*?return lines', new_group_into_lines, content, flags=re.DOTALL)

# 2. Update _find_underscore_line_above
new_find_underscore = """def _find_underscore_line_above(target_word: dict, all_words: list[dict], pdf_page=None) -> dict | None:
    \"\"\"Find a drawn underscore line ('____') or PDF line/rect directly above the target word.\"\"\"
    target_x_mid = (target_word["x0"] + target_word["x1"]) / 2
    candidates = []
    
    # 1. Check for text-based underscores
    for w in all_words:
        if "_" in w["text"]:
            if w["x0"] <= target_x_mid <= w["x1"]:
                if w.get("y1", w.get("bottom", 0)) < target_word.get("y0", target_word.get("top", 0)) and (target_word.get("y0", target_word.get("top", 0)) - w.get("y1", w.get("bottom", 0))) < 40:
                    candidates.append(w)
                    
    # 2. Check for PDF vector lines (if pdf_page is provided)
    if pdf_page:
        # Check explicit lines
        for l in getattr(pdf_page, "lines", []):
            if l["x0"] <= target_x_mid <= l["x1"]:
                if l["bottom"] < target_word.get("y0", target_word.get("top", 0)) and (target_word.get("y0", target_word.get("top", 0)) - l["bottom"]) < 40:
                    candidates.append({"x0": l["x0"], "x1": l["x1"], "y0": l["top"], "y1": l["bottom"]})
        
        # Check skinny rects acting as lines
        for r in getattr(pdf_page, "rects", []):
            if r["bottom"] - r["top"] < 5:  # It's a line
                if r["x0"] <= target_x_mid <= r["x1"]:
                    if r["bottom"] < target_word.get("y0", target_word.get("top", 0)) and (target_word.get("y0", target_word.get("top", 0)) - r["bottom"]) < 40:
                        candidates.append({"x0": r["x0"], "x1": r["x1"], "y0": r["top"], "y1": r["bottom"]})

    if candidates:
        # Return the closest one vertically
        candidates.sort(key=lambda w: target_word.get("y0", target_word.get("top", 0)) - w.get("y1", w.get("bottom", 0)))
        return candidates[0]
    return None"""

content = re.sub(r'def _find_underscore_line_above.*?return None', new_find_underscore, content, flags=re.DOTALL)

# 3. Update _detect_label
new_detect_label = """def _detect_label(line: list[dict], page_w: float, page_words: list[dict], pdf_page=None) -> list[dict]:
    \"\"\"Return a list of label metadata dicts if the line contains colon-terminated labels or a signature indicator.\"\"\"
    labels = []
    
    # 1. Find all colon indices
    colon_indices = [i for i, word in enumerate(line) if word["text"].endswith(":")]
    
    if colon_indices:
        # Process each colon as a separate label
        start_idx = 0
        for idx, colon_idx in enumerate(colon_indices):
            colon_word = line[colon_idx]
            fill_x = colon_word["x1"] + _FILL_GAP
            
            # Determine where the fill area for this label ends
            next_start = colon_indices[idx+1] if idx + 1 < len(colon_indices) else len(line)
            words_after = line[colon_idx + 1:next_start]
            
            # Label is from start_idx to colon_idx
            label_words = line[start_idx : colon_idx + 1]
            label_raw = " ".join(w["text"] for w in label_words)
            label_text = label_raw.rstrip(":").strip()
            
            has_text = False
            import re
            for w in words_after:
                cleaned = re.sub(r'[_.\-\s]', '', w["text"])
                if cleaned:
                    has_text = True
                    break
                    
            label_y1 = colon_word["y1"]
            ul_width = None
            target_word = colon_word
            has_underscore = False
            if "signature" in label_text.lower() or "initial" in label_text.lower() or "name" in label_text.lower():
                ul_line = _find_underscore_line_above(colon_word, page_words, pdf_page=pdf_page)
                if ul_line:
                    label_y1 = ul_line.get("y1", ul_line.get("bottom", 0))
                    ul_width = ul_line.get("x1", 0) - ul_line.get("x0", 0)
                    has_underscore = True
                    label_raw = " ".join(w["text"] for w in line[start_idx : colon_idx + 1])
            
            # Compute full vertical context for the rule engine
            target_y0 = target_word["y0"]
            v_words = [w for w in page_words if abs(w["y0"] - target_y0) <= _LINE_CLUSTER_TOL]
            v_words.sort(key=lambda w: w["x0"])
            full_line_text = " ".join(w["text"] for w in v_words)

            if page_w - fill_x >= _MIN_BLANK_WIDTH:
                labels.append({
                    "label_text": label_text,
                    "label_raw": label_raw,
                    "line_raw": full_line_text,
                    "fill_x": fill_x,
                    "label_y1": label_y1,
                    "has_text": has_text,
                    "ul_width": ul_width,
                    "has_underscore": has_underscore,
                })
            start_idx = next_start
        
        return labels

    # Signature fallback (no colon)
    line_text = " ".join(w["text"] for w in line).lower()
    is_sig = any(kw in line_text for kw in ["signature", "initial", "sign", "tyler combs", "tyler c. combs", "clearcut capital", "ripple returns", "unicorn unlimited", "combslink", "ttyylleerr ccoommbbss", "ttyylleerr cc.. ccoommbbss", "printed name", "print name", "name (print", "print clearly", "print)"])
    if is_sig:
        if len(line) <= 8:
            label_raw = " ".join(w["text"] for w in line)
            target_word = line[0]
            label_y1 = target_word["y1"]
            ul_line = _find_underscore_line_above(target_word, page_words, pdf_page=pdf_page)
            ul_width = None
            has_underscore = False
            if ul_line:
                label_y1 = ul_line.get("y1", ul_line.get("bottom", 0))
                ul_width = ul_line.get("x1", 0) - ul_line.get("x0", 0)
                has_underscore = True
                
            # Compute full vertical context for the rule engine
            target_y0 = target_word["y0"]
            v_words = [w for w in page_words if abs(w["y0"] - target_y0) <= _LINE_CLUSTER_TOL]
            v_words.sort(key=lambda w: w["x0"])
            full_line_text = " ".join(w["text"] for w in v_words)

            labels.append({
                "label_text": label_raw.strip(),
                "label_raw": label_raw,
                "line_raw": full_line_text,
                "fill_x": target_word["x0"],
                "label_y1": label_y1,
                "ul_width": ul_width,
                "has_underscore": has_underscore,
            })

    return labels"""

content = re.sub(r'def _detect_label.*?return None', new_detect_label, content, flags=re.DOTALL)

with open("skills/pdf-form-autofill/overlay.py", "w") as f:
    f.write(content)
