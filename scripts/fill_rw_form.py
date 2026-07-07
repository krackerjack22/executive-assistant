import sys
import io
import pypdf
from reportlab.pdfgen import canvas
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

import importlib.util
spec = importlib.util.spec_from_file_location("spatial_mapper", str(Path(__file__).parent.parent / "skills/pdf-form-autofill/spatial_mapper.py"))
spatial_mapper = importlib.util.module_from_spec(spec)
sys.modules["spatial_mapper"] = spatial_mapper
spec.loader.exec_module(spatial_mapper)

template_path = Path("/Users/tylercombs/Downloads/RW Annual Information Form (1).pdf")
output_path = Path("/Users/tylercombs/Downloads/RW Annual Information Form_Filled.pdf")
signature_path = "/Users/tylercombs/Library/CloudStorage/GoogleDrive-tylercombs@gmail.com/Shared drives/Combslink/Assets_Library/Executive-Assistant/profiles/signature/signature.png"

# Read dimensions
reader = pypdf.PdfReader(template_path)
page0_box = reader.pages[0].mediabox
page1_box = reader.pages[1].mediabox
w0, h0 = float(page0_box.width), float(page0_box.height)
w1, h1 = float(page1_box.width), float(page1_box.height)

data_page1 = [
    {"label": "Student's Name:", "text": "Charlotte Jean Combs", "page": 1},
    {"label": "DOB:", "text": "12/04/2013", "page": 1},
    {"label": "Address:", "text": "5910 SW Rockwood Ct", "page": 1},
    {"label": "City:", "text": "Lake Oswego", "page": 1},
    {"label": "State:", "text": "OR", "page": 1},
    {"label": "Zip:", "text": "97035", "page": 1},
    {"label": "Mobile Phone #:", "text": "971-202-3483", "page": 1},
    {"label": "Mother's Name:", "text": "Lynsee Combs", "page": 1},
    {"label": "Father's Name:", "text": "Tyler Combs", "page": 1},
    {"label": "E-mail:", "text": "lynseecombs@gmail.com", "page": 1},
    {"label": "E-mail: ", "text": "tylercombs@gmail.com", "page": 1}, # Added space for uniqueness
    {"label": "Mobile Phone #: ", "text": "971-322-5577", "page": 1},
    {"label": " Mobile Phone #: ", "text": "503-545-4177", "page": 1},
    {"label": "Insurance Company:", "text": "OHP/CareOregon", "page": 1, "max_width": 200},
    {"label": "Policy #:", "text": "MH801N9B", "page": 1},
    {"label": "Group #:", "text": "None", "page": 1},
    {"label": "Physician:", "text": "Dr. Sivan Ben-David", "page": 1},
    {"label": "Phone #:", "text": "503-691-9777", "page": 1},
    {"label": "Please list any known allergies (including allergies to medications):", "text": "Peanuts", "page": 1},
    {"label": "Please list any dietary restrictions and/or allergies:", "text": "No Peanuts", "page": 1},
    {"label": "YES (for special medication)", "text": "X", "page": 1, "is_checkbox": True},
    {"label": "If “YES”, please identify the special medication(s):", "text": "Epinephrine, Albuterol, Fluoxetine", "page": 1},
    {"label": "Date of most recent tetanus shot, if know:", "text": "5/1/25", "page": 1},
    {"label": "Medical or health conditions or problems (asthma, diabetes, epilepsy, etc.):", "text": "Asthma, anxiety.", "page": 1},
    {"label": "YES (for over-the-counter medication)", "text": "X", "page": 1, "is_checkbox": True},
    {"label": "NO (for swimming restrictions)", "text": "X", "page": 1, "is_checkbox": True},
    {"label": "NO (for restrict the Student's participation)", "text": "X", "page": 1, "is_checkbox": True},
]

data_page2 = [
    {"label": "NO (for restrict participation on page 2)", "text": "X", "page": 2, "is_checkbox": True},
    {"label": "I DO NOT (give permission to record likeness)", "text": "X", "page": 2, "is_checkbox": True},
    {"label": "Date:", "text": datetime.now().strftime("%m/%d/%Y"), "page": 2},
    {"label": "Printed Name:", "text": "Tyler Combs", "page": 2},
]

# Fetch coordinates
print("Fetching spatial coordinates from Gemini 1.5 Flash...")
coords = spatial_mapper.get_spatial_coordinates(template_path, data_page1 + data_page2)

# Merge coordinates back into data
for f in data_page1 + data_page2:
    if f["label"] in coords:
        c = coords[f["label"]]
        f["x"] = c["x"]
        f["bottom"] = c["bottom"]
    else:
        print(f"Warning: Failed to get coordinates for '{f['label']}'. Defaulting to 0,0.")
        f["x"] = 0
        f["bottom"] = 0

def create_overlay(data, w, h, add_signature=False):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(w, h))
    c.setFillColorRGB(0, 0, 0.5) # Navy Blue
    
    for f in data:
        text = f.get("text", "")
        if not text or "x" not in f:
            continue
            
        x = f["x"]
        bottom = f["bottom"]
        y = h - bottom
        
        # Checkbox handling
        if f.get("is_checkbox"):
            c.setFont("Helvetica", 14)
            # Center the X horizontally based on string width
            sw = c.stringWidth(text, "Helvetica", 14)
            # Adjust y so the middle of X sits on center_y
            c.drawString(x - (sw/2), y - 4, text)
            continue
            
        # Determine font size (auto-shrink)
        font_size = 11
        max_w = f.get("max_width")
        if max_w:
            while font_size > 6:
                c.setFont("Helvetica", font_size)
                if c.stringWidth(text, "Helvetica", font_size) <= max_w:
                    break
                font_size -= 1
        c.setFont("Helvetica", font_size)
        
        # pad 2 points above the underscore baseline
        c.drawString(x, y + 2, text)
        
    if add_signature:
        # We can hardcode the signature roughly relative to Date for now, 
        # or we could have requested the 'Parent/Guardian Signature' box!
        # Let's request it via spatial mapper... wait we didn't add it.
        # I'll just use the old hardcoded sig for now, or request it in data_page2.
        pass
        
    c.save()
    buf.seek(0)
    return pypdf.PdfReader(buf)

# Add signature to data_page2 to get its box!
data_page2.append({"label": "Parent/Guardian Signature:", "text": "[SIG]", "page": 2, "is_sig": True})
coords_sig = spatial_mapper.get_spatial_coordinates(template_path, [{"label": "Parent/Guardian Signature:", "page": 2}])
if "Parent/Guardian Signature:" in coords_sig:
    sig_c = coords_sig["Parent/Guardian Signature:"]
    # append it to data_page2 so create_overlay can handle it
    for f in data_page2:
        if f["label"] == "Parent/Guardian Signature:":
            f["x"] = sig_c["x"]
            f["bottom"] = sig_c["bottom"]
            break

def create_overlay_p2(data, w, h):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(w, h))
    c.setFillColorRGB(0, 0, 0.5) 
    
    for f in data:
        text = f.get("text", "")
        if not text or "x" not in f:
            continue
            
        x = f["x"]
        bottom = f["bottom"]
        y = h - bottom
        
        if f.get("is_checkbox"):
            c.setFont("Helvetica", 14)
            sw = c.stringWidth(text, "Helvetica", 14)
            c.drawString(x - (sw/2), y - 4, text)
            continue
            
        if f.get("is_sig"):
            # signature needs to move down slightly based on scale so it sits on the line
            c.drawImage(signature_path, x, y - 10, width=70, height=21, mask='auto')
            continue
            
        font_size = 11
        c.setFont("Helvetica", font_size)
        c.drawString(x, y + 2, text)
        
    c.save()
    buf.seek(0)
    return pypdf.PdfReader(buf)

print("Generating final PDF...")
overlay0 = create_overlay(data_page1, w0, h0)
overlay1 = create_overlay_p2(data_page2, w1, h1)

writer = pypdf.PdfWriter(clone_from=str(template_path))
writer.pages[0].merge_page(overlay0.pages[0])
if len(writer.pages) > 1:
    writer.pages[1].merge_page(overlay1.pages[0])

with open(output_path, "wb") as f:
    writer.write(f)

print(f"Success! Filled PDF saved to {output_path}")
