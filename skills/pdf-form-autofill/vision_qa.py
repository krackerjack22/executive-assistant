"""Vision LLM QA review to ensure signatures do not overlap text.

Sends rendered PDF pages containing signatures to a Gemini Vision model 
to check if the signature obscures printed text. Returns scale corrections.
"""

from __future__ import annotations

import json
import os
import io
from pathlib import Path

_DEFAULT_MODEL = "gemini-2.5-flash"
_API_TIMEOUT = 120


def review_signatures(
    fields: list[dict],
    rendered_pdf_path: Path,
    model: str = _DEFAULT_MODEL,
) -> dict[str, str]:
    """Call Gemini Vision to check for signature text overlaps.

    Args:
        fields: The ``fields`` list from the dry_result or final fill result dict.
        rendered_pdf_path: Path to the PDF that has signatures injected on it.
        model: Gemini model ID.
    
    Returns:
        Mapping of ``{pdf_field_name: "[SIGNATURE_IMAGE:0.7]:/path..."}`` for corrections.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY not set. Export it to use --vision-qa.\n"
            "  export GEMINI_API_KEY=AIza..."
        )

    try:
        from google import genai
        from google.genai import types
        import PIL.Image
    except ImportError:
        raise RuntimeError("google-genai and pillow packages are required for vision QA. uv pip install google-genai pillow")

    # Find fields that have a signature/initials injected
    sig_fields = {}
    for f in fields:
        val = str(f.get("mapped_value") or "")
        if val.startswith("[SIGNATURE_IMAGE") or val.startswith("[INITIALS_IMAGE"):
            sig_fields[f["name"]] = val
            
    if not sig_fields:
        return {}

    # Since we need to check the document, we'll convert all pages to images and send them.
    import pdfplumber
    num_pages = 0
    with pdfplumber.open(str(rendered_pdf_path)) as pdf:
        num_pages = len(pdf.pages)
        
    client = genai.Client(api_key=api_key)
    
    corrections = {}
    
    # Process each page
    for i in range(num_pages):
        with pdfplumber.open(str(rendered_pdf_path)) as pdf:
            page = pdf.pages[i]
            img = page.to_image(resolution=150).original
        
        prompt = (
            "You are a QA reviewer checking an automatically filled PDF form. "
            "Examine this page image and perform four checks:\n\n"
            "1. Signature Overlaps: If there are any hand-written signatures or initials, "
            "check if they vertically overlap or obscure the printed text ABOVE the signature line. "
            "It is completely fine if they cross the actual signature line itself, but they MUST NOT "
            "obscure printed labels or paragraphs of text above the line.\n"
            "If a signature or initials overlaps printed text unacceptably, identify the label next to or below it, "
            "and suggest a scale factor between 0.5 and 0.9 to shrink it.\n\n"
            "2. Missing Printed Names: Look for any empty blank lines labeled 'Printed Name', 'Print Name', 'Name', or 'Signor'. "
            "If it is positioned directly next to or below a signature, it MUST be filled out with the typed name of the person who signed. "
            "If you see a blank line for a printed name next to a signature, you must flag it as missing.\n\n"
            "3. Missing Signatures: Look for any empty blank lines labeled 'Signature', 'Sign Here', or indicating a signature is required. "
            "If a signature line is completely empty but appears it should have been signed based on context, you must flag it as missing.\n\n"
            "4. General Text Overlaps: Check if any typed text (like names, dates, or other fill-ins) is overlapping with other printed text or lines in a way that makes it difficult to read.\n\n"
            "Return your response ONLY as a JSON array of objects. Each object should represent one issue with these keys:\n"
            '  "label": "the printed text near the issue"\n'
            '  "issue_type": "overlap", "missing_name", "missing_signature", or "text_overlap"\n'
            '  "recommended_scale": float (e.g. 0.7) (only if issue_type is overlap)\n'
            '  "missing_value": "Tyler Combs" (only if issue_type is missing_name, guess the name if it is Tyler\'s signature)\n'
            '  "reason": "explanation of what it overlapped or what is missing"\n\n'
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
                raise RuntimeError("No text returned from Vision QA.")

            # Extract JSON block
            if "```json" in raw_text:
                json_str = raw_text.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_text:
                json_str = raw_text.split("```")[1].strip()
            else:
                json_str = raw_text.strip()
                
            issues = json.loads(json_str)
            
            # Match issues back to our fields
            for issue in issues:
                issue_type = issue.get("issue_type")
                if issue_type == "overlap" or issue.get("overlap"):
                    label = issue.get("label", "").lower()
                    scale = issue.get("recommended_scale", 0.7)
                    
                    # Simple fuzzy match against sig_fields
                    matched_field = None
                    for fname, val in sig_fields.items():
                        if label in fname.lower() or fname.lower() in label:
                            matched_field = fname
                            break
                    
                    # If substring fails, just use the first signature field on the document (fallback)
                    if not matched_field and len(sig_fields) == 1:
                        matched_field = list(sig_fields.keys())[0]
                        
                    if matched_field:
                        orig_val = sig_fields[matched_field]
                        # Rewrite to include scale: [SIGNATURE_IMAGE:0.7]:/path
                        parts = orig_val.split("]:")
                        if len(parts) == 2:
                            # strip existing scale if any
                            prefix = parts[0].split(":")[0] 
                            new_val = f"{prefix}:{scale}]:{parts[1]}"
                            corrections[matched_field] = new_val
                            print(f"[Vision QA] Detected signature overlap for '{matched_field}'. Suggested scale: {scale}. Reason: {issue.get('reason')}")
                elif issue_type == "missing_name":
                    label = issue.get("label", "")
                    val = issue.get("missing_value", "Tyler Combs")
                    print(f"[Vision QA] Detected missing printed name for '{label}'. Suggested value: {val}. Reason: {issue.get('reason')}")
                    # We inject a correction that will override any field matching this label
                    corrections[label] = val
                elif issue_type == "missing_signature":
                    label = issue.get("label", "")
                    print(f"[Vision QA] Detected missing signature for '{label}'. Reason: {issue.get('reason')}")
                    # You could map this to a signature injection if desired, but for now we just flag it.
                elif issue_type == "text_overlap":
                    label = issue.get("label", "")
                    print(f"[Vision QA] Detected text overlap for '{label}'. Reason: {issue.get('reason')}")
        except Exception as e:
            print(f"[Vision QA] Error processing page {i+1}: {e}")
            
    return corrections
