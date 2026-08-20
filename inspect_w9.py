import pdfplumber

with pdfplumber.open("tests/test_docs/autofill_tests/W-9_Blank.pdf") as pdf:
    page = pdf.pages[0]
    print(f"Total rects: {len(page.rects)}")
    print(f"Total lines: {len(page.lines)}")
    print(f"Total curves: {len(page.curves)}")
    
    # Let's see what underscores are present
    underscores = [c for c in page.chars if c['text'] == '_']
    print(f"Total underscores: {len(underscores)}")
    
    # Let's inspect the first 20 rects
    for i, r in enumerate(page.rects[:20]):
        w = r['x1'] - r['x0']
        h = r['bottom'] - r['top']
        print(f"Rect {i}: w={w:.1f}, h={h:.1f}, x0={r['x0']:.1f}, top={r['top']:.1f}")

    # Let's inspect the first 20 lines
    for i, l in enumerate(page.lines[:20]):
        print(f"Line {i}: x0={l['x0']:.1f}, y0={l['top']:.1f}, x1={l['x1']:.1f}, y1={l['bottom']:.1f}")
