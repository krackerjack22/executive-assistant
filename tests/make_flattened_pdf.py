"""Generate a flattened (non-AcroForm) PDF for overlay testing.

Run directly to create tests/fixtures/flattened_form.pdf:
    /usr/bin/python3 tests/make_flattened_pdf.py
"""

from __future__ import annotations

from pathlib import Path


LABELS = [
    "Patient Name:",
    "Date of Birth:",
    "Phone Number:",
    "Email Address:",
    "Street Address:",
    "City:",
    "State:",
    "Zip Code:",
    "Insurance Company:",
    "Member ID:",
]

_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def make_flattened_form(output_path: Path) -> None:
    """Write a simple flattened PDF with label text and blank fill areas."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter

    width, height = letter  # 612 x 792 pts

    c = canvas.Canvas(str(output_path), pagesize=letter)
    c.setFont("Helvetica", 11)

    title_y = height - 54
    c.setFont("Helvetica-Bold", 14)
    c.drawString(72, title_y, "Patient Information Form")
    c.setFont("Helvetica", 11)

    y = title_y - 48
    for label in LABELS:
        c.drawString(72, y, label)
        y -= 36

    c.save()
    print(f"Written: {output_path}")


if __name__ == "__main__":
    _FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    make_flattened_form(_FIXTURE_DIR / "flattened_form.pdf")
