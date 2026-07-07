import pdfplumber
import sys

with pdfplumber.open("/Users/tylercombs/Downloads/RW Annual Information Form (1).pdf") as pdf:
    if len(pdf.pages) > 1:
        page = pdf.pages[1]
        words = page.extract_words()
        for w in words:
            print(f"'{w['text']}': x1={w['x1']:.1f}, bottom={w['bottom']:.1f}")
