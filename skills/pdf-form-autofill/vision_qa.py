import json
import os
import io
from pathlib import Path
from PIL import Image, ImageDraw
import pypdfium2 as pdfium
from google import genai
from google.genai import types

def evaluate(
    pdf_path: Path,
    schema: list[dict],
    field_results: list[dict],
    debug_dir: Path | None = None
) -> dict:
    """Run the Vision QA loop to check filled PDF layout and missing fields."""
    
    # 1. Rasterize PDF
    pdf = pdfium.PdfDocument(str(pdf_path))
    # We assume 1 page for now in the QA loop, but can easily loop later.
    page = pdf[0]
    
    # We want a high-res image (e.g. scale=2.0)
    pil_image = page.render(scale=2.0).to_pil()
    pdf.close()
    
    # Coordinates from pypdfium2 are typically 72 DPI, so if we scale=2.0, we multiply coords by 2.
    SCALE = 2.0
    
    # 2. Draw Red Bounding Boxes
    draw = ImageDraw.Draw(pil_image)
    for res in field_results:
        if "rendered_bbox" in res:
            b = res["rendered_bbox"]
            if b["page"] == 1:
                # Top-left and bottom-right
                x0, y0 = b["x0"] * SCALE, b["y0"] * SCALE
                x1, y1 = b["x1"] * SCALE, b["y1"] * SCALE
                draw.rectangle([x0, y0, x1, y1], outline="red", width=3)
                
    if debug_dir:
        debug_dir.mkdir(parents=True, exist_ok=True)
        pil_image.save(debug_dir / f"qa_debug_{pdf_path.name}.png")
        
    # 3. Call Gemini Vision
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    
    prompt = f"""
You are an expert QA Layout Verifier for automated PDF forms.
I am providing you an image of a filled PDF form. 
The system attempted to automatically fill the form based on a user's profile.
I have drawn bright red boxes around every piece of text or checkbox that the system automatically injected.

I am also providing you the original blank schema of fields that we found on this form:
```json
{json.dumps(schema, indent=2)}
```

Your job is to look at the image and the schema, and evaluate two things:
1. **Missed Fields:** Are there checkboxes or fields on the visual form (like an Individual Checkbox) that the user profile should have triggered, but were missed? (Check the original schema to see what the label was).
2. **Alignment:** Look at the text inside the red boxes. Is it bleeding out of its designated box or line? Does it need to be nudged up/down or left/right?

Return a strictly formatted JSON object matching this schema:
{{
  "status": "perfect" | "needs_fixes",
  "fixes": [
    {{
      "field_name": "Exact string from the schema",
      "issue": "Brief description of why this is wrong.",
      "manual_override_value": "If this was missed (like an empty checkbox), provide the exact string (e.g. 'X') to inject. Otherwise omit.",
      "x_offset_nudge": 0,
      "y_offset_nudge": 0 
    }}
  ]
}}
Note: y_offset_nudge is applied mathematically to a bottom-origin coordinate system. A positive y_offset moves the text UP. A negative y_offset moves the text DOWN. A positive x_offset moves the text RIGHT.
If everything looks perfect and no fields are missing, return {{"status": "perfect"}}.
    """
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[pil_image, prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.0
        )
    )
    
    return json.loads(response.text)
