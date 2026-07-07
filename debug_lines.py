import json
import pdfplumber

with pdfplumber.open("tests/test_docs/signature_tests/Liability Waiver Guardian.pdf") as pdf:
    for i, p in enumerate(pdf.pages):
        words = p.extract_words()
        for w in words:
            if "parent" in w["text"].lower() or "signature" in w["text"].lower() or "initial" in w["text"].lower() or "_" in w["text"]:
                print(f"Page {i}: {w}")
