import re

with open("skills/pdf-form-autofill/layout_analyzer.py", "r") as f:
    content = f.read()

old_rects = """    # physical lines
    for r in page.rects:
        if r['height'] < 5 and r['x1'] - r['x0'] > 10:
            blanks.append({
                "x0": r['x0'], "x1": r['x1'], 
                "top": r['top'], "bottom": r['bottom'], 
                "type": "line"
            })"""

new_rects = """    # physical lines, checkboxes, and boxed cells
    for r in page.rects:
        w = r['x1'] - r['x0']
        h = r['bottom'] - r['top']
        
        # Standard horizontal line
        if h < 5 and w > 10:
            blanks.append({
                "x0": r['x0'], "x1": r['x1'], 
                "top": r['top'], "bottom": r['bottom'], 
                "type": "line"
            })
        # Checkbox (roughly square, small)
        elif 5 <= h <= 15 and 5 <= w <= 15 and abs(w - h) < 4:
            blanks.append({
                "x0": r['x0'], "x1": r['x1'], 
                "top": r['top'], "bottom": r['bottom'], 
                "type": "checkbox_rect"
            })
        # Segmented Cell (e.g. SSN boxes, usually vertical rectangles)
        elif 10 < h < 40 and 5 < w < 30:
            blanks.append({
                "x0": r['x0'], "x1": r['x1'], 
                "top": r['top'], "bottom": r['bottom'], 
                "type": "segmented_cell"
            })"""

content = content.replace(old_rects, new_rects)

with open("skills/pdf-form-autofill/layout_analyzer.py", "w") as f:
    f.write(content)

