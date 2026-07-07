import pdfplumber
with pdfplumber.open("tests/test_docs/signature_tests/2008 Player-Parent Agreement.pdf") as pdf:
    page = pdf.pages[0]
    words = page.extract_words()
    for w in words:
        if "PLAYER" in w["text"] or "NAME" in w["text"] or "Signature" in w["text"]:
            print(w["text"], round(w["top"], 1), round(w["bottom"], 1))
