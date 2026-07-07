import pdfplumber
import sys
import os
sys.path.append(os.path.join(os.getcwd(), "skills", "pdf-form-autofill"))
import overlay as _overlay

with pdfplumber.open("tests/test_docs/signature_tests/2008 Player-Parent Agreement.pdf") as pdf:
    page = pdf.pages[0]
    words = page.extract_words(x_tolerance=2, y_tolerance=2)
    page_words = [{"x0": w["x0"], "x1": w["x1"], "y0": w["top"], "y1": w["bottom"], "text": w["text"]} for w in words]
    lines = _overlay._group_into_lines(page_words)
    print(f"Got {len(lines)} lines")
    for i, line in enumerate(lines):
        labels_info = _overlay._detect_label(line, page.width, page_words, pdf_page=page)
        if labels_info:
            for l in labels_info:
                print(l)
