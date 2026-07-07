import pdfplumber

with pdfplumber.open("tests/test_docs/signature_tests/Liability Waiver Guardian.pdf") as pdf:
    for i, p in enumerate(pdf.pages):
        words = p.extract_words()
        for w in words:
            if "print" in w["text"].lower() or "name" in w["text"].lower():
                print(f"Page {i}: {w['text']}")
