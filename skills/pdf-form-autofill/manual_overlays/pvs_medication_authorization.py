"""Manual reportlab/pypdf overlay for the "Authorization for Medication
Administration by School Personnel" form (PVS Medication Authorization,
07/2018 revision).

Why this exists: this specific PDF is a flattened/scanned image with no
AcroForm fields and no vector line/rect graphics for its blanks and
checkboxes -- confirmed true even after running it through a standard OCR
pass (OCR adds a searchable text layer but does not vectorize the
underlines/checkbox borders, and did not transcribe blanks as "_____").
That means skills/pdf-form-autofill/autofill.py's normal pipeline
(layout_analyzer -> schema_extractor -> overlay.py) can't be used: its
schema extraction depends on pdfplumber finding blank-line/checkbox
rects or underscore runs, and finds none on this document, so it always
returns an empty schema regardless of GEMINI_API_KEY. See the
"project-executive-assistant-scanned-pdf-limits" memory for the full
diagnosis.

All coordinates below were calibrated by hand against a 150-dpi render of
the blank template (page is 612x792pt / letter) and verified with zoomed
pixel crops -- not just full-page glances, since small elements like
checkboxes (~15-25px) are easy to mis-place by a few px and still look
fine at full-page scale. Confirmed working 2026-08-20 for Charlotte's 6
forms (3 AM meds + 3 AN/as-needed meds; PM meds intentionally excluded
per user instruction).

Verified elements: header fields, Medication Name, Dose, Mouth checkbox,
Inhalation checkbox, Time/Duration/Reason, Prescription/Nonprescription
checkboxes, Special Instructions, prescriber line, signature + date.

NOT independently verified (copied from an earlier pass, low confidence):
Ear/Eye/Nose/Skin checkbox coordinates -- none of Charlotte's medications
used them. Zoom-check these specifically before trusting them for a
medication administered by ear/eye/nose/skin.

Usage:
    from pvs_medication_authorization import make_overlay
    make_overlay(data_dict, "/path/to/output.pdf", template_path="/path/to/blank_or_ocrd.pdf")

`data_dict` keys:
    student_name, dob, grade, school_name, teacher   (all str)
    medication_name, dose, reason                     (str)
    method   one of "mouth"/"ear"/"eye"/"nose"/"skin"/"inhalation", or None
    time_of_day, start_date, end_date                  (str)
    rx        bool -- True checks Prescription, False checks Nonprescription
    prescriber_name, prescriber_phone   (str, only drawn if rx=True)
    special_instructions                (str, optional)
    signature_image   path to a signature PNG (optional -- omit to leave blank)
    sign_date          (str, optional -- only drawn if signature_image is set)
"""
import io
import os
import textwrap
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

DEFAULT_TEMPLATE = "/Users/tylercombs/Downloads/PVS Medication Authorization.pdf"
SCALE = 150 / 72.0  # template was rendered/measured at 150dpi
PAGE_H = 792.0
PAGE_W = 612.0


def pt(x_px, y_px):
    """Convert 150dpi pixel coords (top-left origin) to PDF points (bottom-left origin)."""
    return x_px / SCALE, PAGE_H - y_px / SCALE


def make_overlay(data, out_path, template_path=DEFAULT_TEMPLATE):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(PAGE_W, PAGE_H))
    c.setFont("Helvetica", 10)

    def draw(x_px, y_px, text, size=10, font="Helvetica"):
        c.setFont(font, size)
        x, y = pt(x_px, y_px)
        c.drawString(x, y, text)

    def draw_wrapped(x_px, y_px, text, width_chars=44, size=9, leading=11, font="Helvetica"):
        c.setFont(font, size)
        lines = []
        for para in text.split("\n"):
            lines.extend(textwrap.wrap(para, width=width_chars) or [""])
        x, y = pt(x_px, y_px)
        for line in lines:
            c.drawString(x, y, line)
            y -= leading

    def check(x_px, y_px):
        c.setFont("Helvetica-Bold", 11)
        x, y = pt(x_px, y_px)
        c.drawString(x, y, "X")

    # Header
    draw(232, 163, data["student_name"])
    draw(800, 163, data["dob"])
    draw(1090, 166, data["grade"])
    draw(232, 211, data["school_name"])
    draw(840, 211, data["teacher"])

    # Left column
    draw(100, 360, data["medication_name"], size=10)
    draw_wrapped(100, 465, data["dose"], width_chars=44, size=9)

    method = data.get("method")  # mouth/ear/eye/nose/skin/inhalation, or None
    method_pts = {
        "mouth": (160, 561),        # verified
        "ear": (280, 561),          # NOT independently verified
        "eye": (372, 561),          # NOT independently verified
        "nose": (467, 561),         # NOT independently verified
        "skin": (160, 591),         # NOT independently verified
        "inhalation": (274, 591),   # verified
    }
    if method in method_pts:
        check(*method_pts[method])

    draw(100, 685, data["time_of_day"])
    draw(335, 706, data["start_date"])
    draw(300, 738, data["end_date"])
    draw_wrapped(100, 822, data["reason"], width_chars=44, size=9)

    # Right column: Prescription / Nonprescription checkboxes
    if data["rx"]:
        check(635, 410)
    else:
        check(635, 482)

    if data.get("special_instructions"):
        draw_wrapped(645, 663, data["special_instructions"], width_chars=44, size=8.5, leading=10.5)

    # Prescriber line (only relevant for rx=True)
    if data["rx"]:
        draw(100, 1288, data.get("prescriber_name", ""), size=9)
        draw(615, 1288, data.get("prescriber_phone", ""), size=9)

    # Parent/Guardian/Student Signature line: label glyphs end at x_px=441, underline
    # runs x_px=450-955 at y_px=1543; "healthcare provider." text above bottoms out at
    # y_px=1492. Final calibration after two rounds of user feedback (bigger + lower twice).
    sig_path = data.get("signature_image")
    if sig_path:
        if not os.path.isfile(sig_path):
            raise FileNotFoundError(f"signature_image not found: {sig_path}")
        img = ImageReader(sig_path)
        iw, ih = img.getSize()
        target_h = 18 * 1.15 * 1.15  # pt
        target_w = target_h * (iw / ih)
        sig_x, sig_y = pt(470, 1556)
        c.drawImage(img, sig_x, sig_y, width=target_w, height=target_h,
                    mask='auto', preserveAspectRatio=True)

    if data.get("sign_date"):
        draw(1020, 1538, data["sign_date"], size=9)

    c.save()
    buf.seek(0)

    overlay_reader = PdfReader(buf)
    base_reader = PdfReader(template_path)
    writer = PdfWriter()
    page = base_reader.pages[0]
    page.merge_page(overlay_reader.pages[0])
    writer.add_page(page)
    with open(out_path, "wb") as f:
        writer.write(f)
