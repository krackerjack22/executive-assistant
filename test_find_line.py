import pdfplumber

def find_line_above(target_word, all_words):
    target_x_mid = (target_word["x0"] + target_word["x1"]) / 2
    candidates = []
    for w in all_words:
        if "_" in w["text"]:
            # Check if it overlaps horizontally and is above (smaller top/bottom)
            if w["x0"] <= target_x_mid <= w["x1"]:
                if w["bottom"] < target_word["top"] and (target_word["top"] - w["bottom"]) < 40:
                    candidates.append(w)
    if candidates:
        # Get the closest one
        candidates.sort(key=lambda w: target_word["top"] - w["bottom"])
        return candidates[0]
    return None

with pdfplumber.open("tests/test_docs/signature_tests/Liability Waiver Guardian.pdf") as pdf:
    for i, p in enumerate(pdf.pages):
        words = p.extract_words()
        for w in words:
            if "Signature" in w["text"]:
                line_w = find_line_above(w, words)
                if line_w:
                    print(f"Found line above '{w['text']}': {line_w['text']} at y1={line_w['bottom']}")
                else:
                    print(f"No line above '{w['text']}'")
