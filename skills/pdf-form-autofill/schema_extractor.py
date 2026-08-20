import json
import hashlib
from pathlib import Path
import layout_analyzer
import os

CACHE_DIR = Path("/Users/tylercombs/.gemini/antigravity-ide/cache/schemas")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

def hash_file(filepath: Path) -> str:
    hasher = hashlib.md5()
    with open(filepath, "rb") as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()

def get_or_create_schema(pdf_path: Path) -> list[dict]:
    file_hash = hash_file(pdf_path)
    cache_file = CACHE_DIR / f"{file_hash}.json"
    
    if cache_file.exists():
        with open(cache_file, "r") as f:
            return json.load(f)
            
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
    
    prompt = f"""
You are a PDF form schema extractor.
I have run a layout analyzer on a flattened PDF form. It detected physical blanks (lines and underscores) and mapped them to the nearest text.

Here is the physical layout map of the form:
{json.dumps(layout_map, indent=2)}

Your task:
Analyze this physical map and generate a clean JSON array of the logical fields that need to be filled.
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
    
    with open(cache_file, "w") as f:
        json.dump(schema, f, indent=2)
        
    return schema
