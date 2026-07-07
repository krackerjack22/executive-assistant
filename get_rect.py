import pdfplumber
import sys

with pdfplumber.open("/Users/tylercombs/Downloads/RW Annual Information Form (1).pdf") as pdf:
    page = pdf.pages[0]
    words = page.extract_words()
    for w in words:
        print(f"'{w['text']}': x1={w['x1']:.1f}, bottom={w['bottom']:.1f}")
