"""Generate a minimal AcroForm PDF for round-trip testing.

Run directly to create tests/fixtures/synthetic_form.pdf:
    /usr/bin/python3 tests/make_test_pdf.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

FIELD_DEFS = [
    ("patient name",            "Patient Name"),
    ("dob",                     "Date of Birth"),
    ("gender",                  "Gender"),
    ("phone",                   "Phone Number"),
    ("email",                   "Email Address"),
    ("street address",          "Address"),
    ("city",                    "City"),
    ("state",                   "State"),
    ("zip code",                "Zip Code"),
    ("employer",                "Employer Name"),
    ("insurance company",       "Insurance Carrier"),
    ("member id",               "Member ID"),
    ("group number",            "Group Number"),
    ("primary care physician",  "PCP Name"),
]


def make_acroform_pdf(output_path: Path) -> None:
    """Create a minimal PDF with proper AcroForm fields."""
    import pypdf
    from pypdf.generic import (
        ArrayObject,
        BooleanObject,
        DictionaryObject,
        NameObject,
        NumberObject,
        TextStringObject,
    )

    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=612, height=792)
    page = writer.pages[0]

    annot_refs = []
    y = 700
    for name, alt in FIELD_DEFS:
        field_dict = DictionaryObject({
            NameObject("/Type"): NameObject("/Annot"),
            NameObject("/Subtype"): NameObject("/Widget"),
            NameObject("/FT"): NameObject("/Tx"),
            NameObject("/T"): TextStringObject(name),
            NameObject("/TU"): TextStringObject(alt),
            NameObject("/Rect"): ArrayObject([
                NumberObject(72),
                NumberObject(y),
                NumberObject(400),
                NumberObject(y + 14),
            ]),
            NameObject("/V"): TextStringObject(""),
            NameObject("/DV"): TextStringObject(""),
        })
        ref = writer._add_object(field_dict)
        annot_refs.append(ref)
        y -= 20

    # Attach widgets to page /Annots
    page_obj = page.get_object()
    page_obj[NameObject("/Annots")] = ArrayObject(annot_refs)

    # Build root-level /AcroForm pointing to all fields
    acroform = DictionaryObject({
        NameObject("/Fields"): ArrayObject(annot_refs),
        NameObject("/NeedAppearances"): BooleanObject(True),
    })
    acroform_ref = writer._add_object(acroform)
    writer._root_object[NameObject("/AcroForm")] = acroform_ref

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as f:
        writer.write(f)
    print(f"Created AcroForm PDF ({len(FIELD_DEFS)} fields): {output_path}")


if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "fixtures" / "synthetic_form.pdf"
    make_acroform_pdf(out)
