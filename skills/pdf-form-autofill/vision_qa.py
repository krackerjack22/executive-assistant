"""Vision LLM QA review to ensure filled text is aligned and does not overlap.

Sends rendered PDF pages containing Navy Blue filled text to a Gemini Vision model
to check if the text is properly aligned over underscores, doesn't bleed into labels,
and signature images don't obscure printed text. Returns micro-adjustments or abbreviations.
"""

from __future__ import annotations

import json
import os
import io
from pathlib import Path

_DEFAULT_MODEL = "gemini-2.5-flash"
_API_TIMEOUT = 120

def review_fills(
    rendered_pdf_path: Path,
    model: str = _DEFAULT_MODEL,
) -> list[dict]:
    """Call Gemini Vision to check for text overlaps and misalignment.

    Args:
        rendered_pdf_path: Path to the PDF that has text (Navy Blue) and signatures injected.
        model: Gemini model ID.
    
    Returns:
        List of issue dicts containing 'label', 'issue_type', 'x_nudge', 'y_nudge', 'abbreviated_value', 'reason'.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set. Export it to use --vision-qa.")

    try:
        from google import genai
        from google.genai import types
        import PIL.Image
        import pdfplumber
    except ImportError:
        raise RuntimeError("google-genai, pillow, and pdfplumber are required. uv pip install google-genai pillow pdfplumber")

    num_pages = 0
    with pdfplumber.open(str(rendered_pdf_path)) as pdf:
        num_pages = len(pdf.pages)
        
    client = genai.Client(api_key=api_key)
    all_issues = []
    
    for i in range(num_pages):
        with pdfplumber.open(str(rendered_pdf_path)) as pdf:
            page = pdf.pages[i]
            img = page.to_image(resolution=150).original
        
        prompt = (
            "You are a QA reviewer checking an automatically filled PDF form. "
            "All newly filled text has been colored **Navy Blue**, while the original form text is black.\n\n"
            "Examine this page image and perform these checks:\n\n"
            "1. Navy Blue Text Overlaps (Bleed): Check if any Navy Blue text bleeds into or overlaps the black printed labels. "
            "If it does, suggest an 'x_nudge' or 'y_nudge' (in points) to move the Navy Blue text so it doesn't overlap. "
            "If the Navy Blue text is simply too long to fit in the available blank space even if nudged, suggest a much shorter 'abbreviated_value' (e.g. 'OHP/CareOregon' instead of 'OHP (Oregon Health Plan) / CareOregon').\n\n"
            "2. Navy Blue Text Alignment: Check if the Navy Blue text is floating too high above or sitting too far below its designated underscore line. "
            "If it is misaligned vertically, suggest a 'y_nudge' (e.g., -4 to move it down 4 points, or 4 to move it up). "
            "If it is misaligned horizontally (e.g., starting way past the colon or far before the underscore), suggest an 'x_nudge'.\n\n"
            "3. Navy Blue Checkboxes: Check if any Navy Blue 'X' is placed far away from its intended box or underscore. If so, suggest x_nudge and y_nudge.\n\n"
            "4. Signature Overlaps: If there are any hand-written signatures (which may be black or blue), check if they vertically obscure the printed black text ABOVE the signature line. "
            "If they do, suggest a 'scale' factor between 0.5 and 0.9 to shrink the signature.\n\n"
            "Return your response ONLY as a JSON array of objects. Each object should represent one issue with these keys:\n"
            '  "label": "the black printed text nearest the issue (e.g., \'Insurance Company:\')"\n'
            '  "issue_type": "text_overlap", "misalignment", or "signature_overlap"\n'
            '  "x_nudge": float (e.g., 5 to move right, -5 to move left) (optional)\n'
            '  "y_nudge": float (e.g., 5 to move up, -5 to move down) (optional)\n'
            '  "scale": float (e.g., 0.7) (only for signature_overlap)\n'
            '  "abbreviated_value": "Short text" (optional, if text_overlap and nudging won\'t fix the length)\n'
            '  "reason": "explanation of the issue"\n\n'
            "If no issues are found, return an empty JSON array []."
        )
        
        try:
            resp = client.models.generate_content(
                model=model,
                contents=[img, prompt],
                config=types.GenerateContentConfig(
                    temperature=0.0,
                )
            )
            
            raw_text = resp.text
            if not raw_text:
                continue

            # Extract JSON block
            if "```json" in raw_text:
                json_str = raw_text.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_text:
                json_str = raw_text.split("```")[1].strip()
            else:
                json_str = raw_text.strip()
                
            issues = json.loads(json_str)
            for issue in issues:
                issue['page'] = i + 1
                all_issues.append(issue)
                print(f"[Vision QA] Page {i+1} - {issue.get('issue_type')} on '{issue.get('label')}': {issue.get('reason')}")
                if issue.get('x_nudge') or issue.get('y_nudge'):
                    print(f"  Suggested nudges: x={issue.get('x_nudge', 0)}, y={issue.get('y_nudge', 0)}")
                if issue.get('abbreviated_value'):
                    print(f"  Suggested abbreviation: {issue.get('abbreviated_value')}")
        except Exception as e:
            print(f"[Vision QA] Error processing page {i+1}: {e}")
            
    return all_issues

