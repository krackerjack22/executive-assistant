import pdfplumber
import json
from blanks_extractor import get_blanks, dedupe_chars
import sys
from pathlib import Path



def analyze_pdf(pdf_path: str) -> dict:
    results = {}
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            blanks = get_blanks(page)
            words = page.extract_words()
            
            page_results = []
            for b in blanks:
                labels_above = []
                labels_below = []
                labels_left = []
                
                for w in words:
                    # Clean the OCR text
                    text = dedupe_chars(w['text']).strip()
                    if not text or len(text) < 2: continue
                    
                    # Label Below (Line is above label)
                    if 0 <= w['top'] - b['bottom'] <= 15 and max(b['x0'], w['x0']) < min(b['x1'], w['x1']):
                        labels_below.append(text)
                    # Label Left (Line is right of label)
                    elif 0 <= b['x0'] - w['x1'] <= 25 and abs(b['bottom'] - w['bottom']) < 15:
                        labels_left.append(text)
                    # Label Above (Line is below label)
                    elif 0 <= b['top'] - w['bottom'] <= 25 and max(b['x0'], w['x0']) < min(b['x1'], w['x1']):
                        labels_above.append(text)
                        
                if labels_below or labels_left or labels_above:
                    page_results.append({
                        "blank_type": b["type"],
                        "width": round(b["x1"] - b["x0"], 1),
                        "labels_left": labels_left,
                        "labels_above": labels_above,
                        "labels_below": labels_below
                    })
            results[f"page_{page_num}"] = page_results
    return results

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python layout_analyzer.py <pdf_path>")
        sys.exit(1)
        
    analysis = analyze_pdf(sys.argv[1])
    print(json.dumps(analysis, indent=2))
