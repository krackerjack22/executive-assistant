"""Deterministic anchor extraction for PDF forms.

Uses pdfplumber and rapidfuzz to find the exact mathematical bounding box
of OCR text labels in a PDF, allowing us to anchor answers perfectly without
relying on unreliable LLM pixel-math.
"""

from __future__ import annotations

import pdfplumber
from rapidfuzz import fuzz
from blanks_extractor import get_blanks, dedupe_chars
from pathlib import Path



def normalize_text(s: str) -> str:
    """Normalize apostrophes and spacing for better matching."""
    s = s.replace("’", "'").replace("‘", "'")
    return s.strip().lower()

def find_best_blank(match, blanks, is_cb):
    if is_cb:
        candidates = [b for b in blanks if abs(b['top'] - match['top']) < 15 and (b['x1'] - b['x0']) < 25]
        if candidates:
            return sorted(candidates, key=lambda b: min(abs(b['x1'] - match['x0']), abs(b['x0'] - match['x1'])))[0], 'checkbox'
        return None, None
    else:
        candidates = []
        for b in blanks:
            if b['x1'] - b['x0'] < 30: continue
            
            vert_dist = match['top'] - b['bottom']
            if -15 <= vert_dist <= 20 and max(b['x0'], match['x0']) < min(b['x1'], match['x1']):
                candidates.append((b, abs(vert_dist), 'above'))
            elif b['x0'] >= match['x1'] - 10 and abs(b['bottom'] - match['bottom']) < 15:
                candidates.append((b, b['x0'] - match['x1'], 'right'))
            
            # Label-Above condition: line is below the label
            elif 0 <= (b['top'] - match['bottom']) <= 30 and max(b['x0'], match['x0']) < min(b['x1'], match['x1']):
                candidates.append((b, b['top'] - match['bottom'], 'below'))
                
        if candidates:
            best = sorted(candidates, key=lambda x: x[1])[0]
            return best[0], best[2]
        return None, None

def get_anchor_coordinates(
    blank_pdf_path: Path,
    fields_to_locate: list[dict],
) -> dict[str, dict]:
    """Find deterministic OCR bounding boxes for target fields.

    Args:
        blank_pdf_path: Path to the template PDF (unfilled).
        fields_to_locate: List of field dictionaries containing 'label'.
    
    Returns:
        Mapping of {label: {"x": float, "bottom": float, "is_checkbox": bool}}
    """
    # Group fields by page
    page_fields = {}
    for f in fields_to_locate:
        p = f.get("page", 1)
        if p not in page_fields:
            page_fields[p] = []
        page_fields[p].append(f)
        
    results = {}
    
    with pdfplumber.open(blank_pdf_path) as pdf:
        for page_num, fields in page_fields.items():
            if page_num > len(pdf.pages):
                continue
                
            page = pdf.pages[page_num - 1]
            # Extract words and sort by top-to-bottom, left-to-right
            blanks = get_blanks(page)
            words = sorted(page.extract_words(), key=lambda w: (w['top'], w['x0']))
            
            # Group words into lines (threshold 5 points vertical difference)
            lines = []
            current_line = []
            for w in words:
                if not current_line or abs(w['top'] - current_line[-1]['top']) < 5:
                    current_line.append(w)
                else:
                    current_line.sort(key=lambda x: x['x0'])
                    lines.append(current_line)
                    current_line = [w]
            if current_line:
                current_line.sort(key=lambda x: x['x0'])
                lines.append(current_line)
                
            # Track matches by clean label
            label_matches = {}
            for f in fields:
                target_clean = normalize_text(f["label"].strip())
                is_cb = f.get("is_checkbox", False)
                if is_cb and "(" in target_clean:
                    target_clean = target_clean.split("(")[0].strip()
                if target_clean not in label_matches:
                    label_matches[target_clean] = []
            
            for f in fields:
                target_original = f["label"]
                target_clean = normalize_text(target_original.strip())
                num_words = len(target_clean.split())
                is_cb = f.get("is_checkbox", False)
                
                if is_cb and "(" in target_clean:
                    target_clean = target_clean.split("(")[0].strip()
                    num_words = len(target_clean.split())
                
                for line in lines:
                    for window_size in range(1, num_words + 3):
                        for i in range(len(line) - window_size + 1):
                            window = line[i:i+window_size]
                            raw_text = " ".join(w['text'] for w in window)
                            clean_text = normalize_text(dedupe_chars(raw_text))
                            
                            score = fuzz.ratio(target_clean, clean_text)
                                
                            if score > 75:
                                if target_clean == "mobile phone": print(f"MATCH: {clean_text} ({raw_text}) = {score}")
                                box = {
                                    "x0": window[0]['x0'],
                                    "x1": window[-1]['x1'],
                                    "top": min(w['top'] for w in window),
                                    "bottom": max(w['bottom'] for w in window),
                                    "score": score,
                                    "raw_text": raw_text
                                }
                                label_matches[target_clean].append(box)
            
            # Assign best matches to fields
            for target_clean, matches in label_matches.items():
                if not matches:
                    print(f"[Anchor Mapper] Warning: No match found for '{target_clean}'")
                    continue
                    
                unique_matches = []
                for m in sorted(matches, key=lambda x: x["score"], reverse=True):
                    overlap = False
                    for u in unique_matches:
                        if abs(m["top"] - u["top"]) < 5 and max(m["x0"], u["x0"]) < min(m["x1"], u["x1"]):
                            overlap = True
                            break
                    if not overlap:
                        unique_matches.append(m)
                        
                req_fields = []
                for f in fields:
                    tc = normalize_text(f["label"].strip())
                    if f.get("is_checkbox") and "(" in tc:
                        tc = tc.split("(")[0].strip()
                    if tc == target_clean:
                        req_fields.append(f)
                        
                req_count = len(req_fields)
                
                unique_matches = sorted(unique_matches, key=lambda m: m["score"], reverse=True)
                best_matches = unique_matches[:req_count]
                best_matches = sorted(best_matches, key=lambda m: (m['top'], m['x0']))
                
                for i, f_dict in enumerate(req_fields):
                    if i < len(best_matches):
                        match = best_matches[i]
                        
                        is_cb = f_dict.get("is_checkbox", False)
                        b, rel = find_best_blank(match, blanks, is_cb)
                        
                        if f_dict.get("force_rel"):
                            # Filter candidates to only matching relation
                            rel_wanted = f_dict["force_rel"]
                            if rel != rel_wanted:
                                b, rel = None, None
                                # Re-run search forcing rel
                                cands = []
                                for bb in blanks:
                                    if bb['x1'] - bb['x0'] < 15: continue
                                    vd = match['top'] - bb['bottom']
                                    if rel_wanted == 'above' and -15 <= vd <= 20 and max(bb['x0'], match['x0']) < min(bb['x1'], match['x1']):
                                        cands.append((bb, abs(vd), 'above'))
                                    elif rel_wanted == 'right' and bb['x0'] >= match['x1'] - 10 and abs(bb['bottom'] - match['bottom']) < 15:
                                        cands.append((bb, bb['x0'] - match['x1'], 'right'))
                                    elif rel_wanted == 'below' and 0 <= (bb['top'] - match['bottom']) <= 30 and max(bb['x0'], match['x0']) < min(bb['x1'], match['x1']):
                                        cands.append((bb, bb['top'] - match['bottom'], 'below'))
                                if cands:
                                    best = sorted(cands, key=lambda x: x[1])[0]
                                    b, rel = best[0], best[2]

                        if is_cb:
                            if b:
                                x = b['x0'] + (b['x1'] - b['x0']) / 2.0 - 4
                                bottom = (match["top"] + match["bottom"]) / 2.0
                            else:
                                rt = match.get("raw_text", "").strip()
                                if rt.startswith("_") or rt.startswith("□"):
                                    x = match["x0"] + 6
                                else:
                                    x = match["x0"] - 12
                                bottom = (match["top"] + match["bottom"]) / 2.0
                        else:
                            if b:
                                if rel == 'right':
                                    x = b['x0'] + 2
                                    bottom = b['bottom'] - 2
                                elif rel == 'above':
                                    x = match['x0']
                                    bottom = b['bottom'] - 2
                                elif rel == 'below':
                                    x = b['x0'] + 2
                                    bottom = b['bottom'] - 2
                            else:
                                x = match["x1"] + 5
                                bottom = match["bottom"]
                            
                        x += f_dict.get("x_offset", 0)
                        bottom += f_dict.get("y_offset", 0)
                        
                        results[f_dict["label"]] = {
                            "x": x,
                            "bottom": bottom,
                            "is_checkbox": is_cb
                        }
                        print(f"[Anchor Mapper] Anchored '{f_dict['label']}' at x={x:.1f}, y_anchor={bottom:.1f} (score: {match['score']:.1f})")
                    
    return results
