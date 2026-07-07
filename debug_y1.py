import pdfplumber
with pdfplumber.open("tests/test_docs/signature_tests/Special Meeting Minutes from RareBird.pdf") as pdf:
    page = pdf.pages[0]
    print(page.rects)
    print(page.lines)
    print(page.curves)
