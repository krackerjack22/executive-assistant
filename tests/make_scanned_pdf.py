"""Generate an image-only (scanned-looking) PDF for raster blank detection tests.

Draws a form with rules and checkboxes at known coordinates, rasterizes the
whole page, then rebuilds a PDF containing nothing but that image. The result
has zero vector graphics and zero text -- the same shape as a scan.

Run directly to create tests/fixtures/scanned_form.pdf:
    python tests/make_scanned_pdf.py
"""

from __future__ import annotations

import io
from pathlib import Path

_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"

PAGE_W, PAGE_H = 612.0, 792.0
RENDER_DPI = 200

# (label, label_x, baseline_y, rule_x0, rule_x1) in reportlab bottom-origin pts.
RULE_FIELDS = [
    ("Patient Name:", 72.0, 700.0, 150.0, 400.0),
    ("Date of Birth:", 72.0, 660.0, 150.0, 300.0),
    ("Phone Number:", 72.0, 620.0, 160.0, 380.0),
    ("City:", 72.0, 580.0, 110.0, 320.0),
]

# (label, box_x, box_y, side) in reportlab bottom-origin pts.
CHECKBOX_FIELDS = [
    ("Yes", 90.0, 500.0, 12.0),
    ("No", 190.0, 500.0, 12.0),
    ("Maybe", 290.0, 500.0, 12.0),
]


def expected_rules_top_origin() -> list[tuple[float, float, float]]:
    """Rules as (x0, x1, top) in top-origin points, matching detector output."""
    return [(x0, x1, PAGE_H - y) for _, _, y, x0, x1 in RULE_FIELDS]


def expected_checkboxes_top_origin() -> list[tuple[float, float, float, float]]:
    """Checkboxes as (x0, x1, top, bottom) in top-origin points."""
    return [
        (x, x + side, PAGE_H - (y + side), PAGE_H - y)
        for _, x, y, side in CHECKBOX_FIELDS
    ]


def _draw_source_page() -> bytes:
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(PAGE_W, PAGE_H))

    c.setFont("Helvetica-Bold", 14)
    c.drawString(72, 740, "Patient Information Form")

    c.setFont("Helvetica", 11)
    c.setLineWidth(1)
    for label, lx, y, rx0, rx1 in RULE_FIELDS:
        c.drawString(lx, y + 3, label)
        c.line(rx0, y, rx1, y)

    c.drawString(72, 503, "Consent:")
    for label, x, y, side in CHECKBOX_FIELDS:
        c.rect(x, y, side, side, stroke=1, fill=0)
        c.drawString(x + side + 5, y + 3, label)

    c.save()
    return buf.getvalue()


def make_scanned_form(output_path: Path) -> None:
    """Write an image-only PDF: no vector graphics, no text layer."""
    import pypdfium2 as pdfium
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    src = _draw_source_page()
    pdf = pdfium.PdfDocument(src)
    try:
        pil = pdf[0].render(scale=RENDER_DPI / 72.0).to_pil().convert("L")
    finally:
        pdf.close()

    out = canvas.Canvas(str(output_path), pagesize=(PAGE_W, PAGE_H))
    out.drawImage(ImageReader(pil), 0, 0, width=PAGE_W, height=PAGE_H)
    out.save()
    print(f"Written: {output_path}")


if __name__ == "__main__":
    _FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    make_scanned_form(_FIXTURE_DIR / "scanned_form.pdf")
