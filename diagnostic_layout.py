import pdfplumber
import sys
from pathlib import Path

pdf_files = list(Path("tests/test_docs").rglob("*.pdf"))

print(f"Analyzing {len(pdf_files)} PDFs...\n")

for pdf_path in pdf_files:
    if "filled" in pdf_path.name.lower():
        continue # Skip filled PDFs
    try:
        with pdfplumber.open(pdf_path) as pdf:
            page = pdf.pages[0]
            
            # Count elements
            rect_count = len(page.rects)
            line_count = len(page.lines)
            curve_count = len(page.curves)
            char_count = len(page.chars)
            underscore_count = len([c for c in page.chars if c['text'] == '_'])
            
            # Analyze rects
            h_rects = [r for r in page.rects if r['bottom'] - r['top'] < 5 and r['x1'] - r['x0'] > 10]
            checkboxes = [r for r in page.rects if 5 <= r['bottom'] - r['top'] <= 20 and 5 <= r['x1'] - r['x0'] <= 20 and abs((r['x1'] - r['x0']) - (r['bottom'] - r['top'])) < 4]
            cells = [r for r in page.rects if 10 < r['bottom'] - r['top'] < 40 and 5 < r['x1'] - r['x0'] < 30]
            
            print(f"=== {pdf_path.name} ===")
            print(f"Total Elements -> Rects: {rect_count}, Lines: {line_count}, Curves: {curve_count}, Underscores: {underscore_count}")
            print(f"Detected Blanks -> Horizontal Rects: {len(h_rects)}, Checkboxes: {len(checkboxes)}, Segmented Cells: {len(cells)}")
            
            # If nothing was detected, what else is there?
            if len(h_rects) == 0 and underscore_count == 0 and line_count == 0 and curve_count > 0:
                print(">>> WARNING: Form relies completely on curves or has no physical lines!")
            if rect_count == 0 and line_count == 0 and curve_count == 0 and underscore_count == 0:
                print(">>> WARNING: Form has ZERO physical graphics or underscores (pure text only).")
            print()
    except Exception as e:
        print(f"Error opening {pdf_path.name}: {e}")
