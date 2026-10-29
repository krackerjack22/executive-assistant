import json
import hashlib
from pathlib import Path
import layout_analyzer
import os

CACHE_DIR = Path("/Users/tylercombs/.gemini/antigravity-ide/cache/schemas")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Bump whenever anything upstream of the LLM call changes the schema we would
# produce for the same bytes: blank detection, the layout map shape, or either
# prompt. The cache key includes this, so old entries are ignored rather than
# silently replayed. Without it, a PDF analyzed before a pipeline fix keeps
# returning the pre-fix schema forever -- the file hash never changes.
SCHEMA_VERSION = 2

def hash_file(filepath: Path) -> str:
    hasher = hashlib.md5()
    with open(filepath, "rb") as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()

def cache_path_for(pdf_path: Path) -> Path:
    """Versioned cache location for a PDF's extracted schema."""
    return CACHE_DIR / f"{hash_file(pdf_path)}-v{SCHEMA_VERSION}.json"


def _read_cache(cache_file: Path) -> list[dict] | None:
    """Return a cached schema only if it is current, well-formed and non-empty."""
    if not cache_file.exists():
        return None
    try:
        with open(cache_file, "r") as f:
            payload = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    # Pre-versioning entries were bare JSON arrays written by an older
    # pipeline. Treat them as stale rather than trusting them.
    if not isinstance(payload, dict):
        return None
    if payload.get("schema_version") != SCHEMA_VERSION:
        return None

    schema = payload.get("schema")
    # An empty schema is a failure, not a result. Caching one would make a
    # single bad run permanent for that file.
    if not isinstance(schema, list) or not schema:
        return None
    return schema


def get_or_create_schema(pdf_path: Path, refresh: bool = False) -> list[dict]:
    """Extract (or reuse) the logical field schema for a form.

    Args:
        pdf_path: The blank template PDF.
        refresh: Ignore any cached entry and re-extract. Also set by the
            PDF_AUTOFILL_REFRESH_SCHEMA environment variable.
    """
    cache_file = cache_path_for(pdf_path)
    refresh = refresh or os.environ.get("PDF_AUTOFILL_REFRESH_SCHEMA") == "1"

    if not refresh:
        cached = _read_cache(cache_file)
        if cached is not None:
            return cached

    print("[Schema Extractor] Cache miss. Analyzing layout and calling LLM...")
    
    # 1. Run Layout Analyzer
    layout_map = layout_analyzer.analyze_pdf(str(pdf_path))
    
    # 2. Call LLM
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing. Cannot extract schema.")
        
    from google import genai
    from google.genai import types
    
    client = genai.Client(api_key=api_key)
    
    has_blanks = any(len(blanks) > 0 for blanks in layout_map.values())

    import pdfplumber
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text += f"\n--- Page {i+1} ---\n"
            text += page.extract_text() or ""

    if has_blanks:
        prompt = f"""
You are a PDF form schema extractor.
I have run a layout analyzer on a flattened PDF form. It detected physical blanks (lines and underscores) and mapped them to the nearest text.

Here is the physical layout map of the form. Each entry is a detected blank
(a rule or a checkbox) with its position and the text nearest to it:
{json.dumps(layout_map, indent=2)}

Here is the full text of the form, for context the layout map does not carry:
{text}

Your task:
Analyze BOTH inputs together and generate a clean JSON array of the logical fields that need to be filled.
Use the layout map to find blanks and to disambiguate repeated labels by position.
Use the form text to recover the full, human-readable prompt for each blank -- the layout map's
nearest-word labels are often truncated (for example "Name:" where the form actually reads "Student Name:").
IMPORTANT: also include fields that the layout map missed. Some forms provide an open area to write in
rather than a printed line, so a prompt visible in the text with no matching blank is still a real field.

CRITICAL LABEL RULE: each "label" is matched back against the literal text of the form by a fuzzy
string matcher. It MUST be the text as it actually appears on the page.
- For a checkbox in a group, use ONLY the option's own text -- "Mouth", "Eye", "Nose".
  Do NOT prefix it with the group heading. "Method of administration: Mouth" does not appear
  anywhere on the page, so it cannot be located, and every option in the group collapses onto
  the same checkbox.
- If an option needs disambiguating context, append it in parentheses after the exact text,
  e.g. "Yes (parent consent)". Everything from the "(" onward is stripped before matching.
If a single prompt (like "Name:") has multiple blanks underneath it (like "First", "Last"), you MUST output them as separate fields (e.g. "First Name", "Last Name").
If a field is a checkbox (like a small line next to "YES" or "NO"), mark it as is_checkbox: true.

Output a raw JSON array of objects. Each object MUST have:
- "label": A descriptive string label for the field (e.g. "First Name", "DOB:", "Address", "YES (for special medication)"). This label will be used for mapping and anchoring, so make it exactly match the text on the form if possible, or combine the prompt and sub-label.
- "is_checkbox": true/false
- "page": The integer page number the blank was found on (e.g., 1 or 2). Parse this from the 'page_X' keys in the layout map.

Example output:
[
  {{"label": "Last", "is_checkbox": false, "page": 1}},
  {{"label": "First", "is_checkbox": false, "page": 1}},
  {{"label": "DOB:", "is_checkbox": false, "page": 1}},
  {{"label": "YES (for special medication)", "is_checkbox": true, "page": 1}}
]

Output ONLY the raw JSON array. No markdown, no explanation.
"""
    else:
        prompt = f"""
You are a PDF form schema extractor.
This is an OCR'd scanned form without vector blanks. I have extracted the raw text from the form.

Here is the raw text from the form:
{text}

Your task:
Analyze this text and generate a clean JSON array of the logical fields that a user would need to fill out on this form.
Look for obvious prompts like "Name:", "Date:", "Signature", or checkbox options like "[] Yes [] No".
If a field is a checkbox, mark it as is_checkbox: true.

Output a raw JSON array of objects. Each object MUST have:
- "label": A descriptive string label for the field. This MUST exactly match the prompt text on the form so it can be anchored (e.g. "Student Name:" or "Skin").
- "is_checkbox": true/false
- "page": The integer page number the field was found on.

Output ONLY the raw JSON array. No markdown, no explanation.
"""

    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.0,
        )
    )
    
    raw_text = response.text.strip()
    if raw_text.startswith("```json"):
        raw_text = raw_text[7:]
    if raw_text.startswith("```"):
        raw_text = raw_text[3:]
    if raw_text.endswith("```"):
        raw_text = raw_text[:-3]
        
    schema = json.loads(raw_text.strip())

    if not schema:
        # Do not persist a failure. The next run should try again rather than
        # replay an empty schema and silently fill nothing.
        print(
            "[Schema Extractor] Warning: extraction produced no fields; "
            "not caching. Re-run after checking the source PDF."
        )
        return schema

    blank_count = sum(len(b) for b in layout_map.values())
    payload = {
        "schema_version": SCHEMA_VERSION,
        "source_pdf": pdf_path.name,
        "extraction_mode": "layout" if has_blanks else "text_only",
        "blank_count": blank_count,
        "schema": schema,
    }
    with open(cache_file, "w") as f:
        json.dump(payload, f, indent=2)

    return schema
