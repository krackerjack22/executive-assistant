"""Generate minimal AcroForm PDFs for round-trip testing.

Run directly to create all test fixtures:
    /usr/bin/python3 tests/make_test_pdf.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Standard form: all fields have exact synonym matches → all high confidence
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

# Ambiguous form: contains a field that produces low-confidence mapping.
# "phone email" matches both contact.primary_phone (score 0.5) and
# contact.email (score 0.5) → 2 plausible candidates → low confidence.
AMBIGUOUS_FIELD_DEFS = [
    ("patient name", "Patient Name"),
    ("phone email",  "Phone or Email"),  # deliberately ambiguous
]

# Two-page form: fields are split across page 1 and page 2.
# Used to regression-test multi-page fill (Issue #1).
TWO_PAGE_P1_DEFS = [
    ("patient name", "Patient Name"),
    ("dob",          "Date of Birth"),
    ("phone",        "Phone Number"),
]
TWO_PAGE_P2_DEFS = [
    ("city",    "City"),
    ("state",   "State"),
    ("zip code","Zip Code"),
]


def _write_pdf(output_path: Path, field_defs: list) -> None:
    """Write a minimal AcroForm PDF with the given field definitions."""
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
    for name, alt in field_defs:
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

    page_obj = page.get_object()
    page_obj[NameObject("/Annots")] = ArrayObject(annot_refs)

    acroform = DictionaryObject({
        NameObject("/Fields"): ArrayObject(annot_refs),
        NameObject("/NeedAppearances"): BooleanObject(True),
    })
    acroform_ref = writer._add_object(acroform)
    writer._root_object[NameObject("/AcroForm")] = acroform_ref

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as f:
        writer.write(f)
    print(f"Created AcroForm PDF ({len(field_defs)} fields): {output_path}")


def make_acroform_pdf(output_path: Path) -> None:
    """Create the standard synthetic form."""
    _write_pdf(output_path, FIELD_DEFS)


def make_ambiguous_pdf(output_path: Path) -> None:
    """Create a form with a deliberately ambiguous field for low-confidence testing."""
    _write_pdf(output_path, AMBIGUOUS_FIELD_DEFS)


def make_btn_pdf(output_path: Path) -> None:
    """Create a form with /Btn (radio) fields to test button fill support."""
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

    # Text field: patient name
    tx_field = DictionaryObject({
        NameObject("/Type"): NameObject("/Annot"),
        NameObject("/Subtype"): NameObject("/Widget"),
        NameObject("/FT"): NameObject("/Tx"),
        NameObject("/T"): TextStringObject("patient name"),
        NameObject("/TU"): TextStringObject("Patient Name"),
        NameObject("/Rect"): ArrayObject([
            NumberObject(72), NumberObject(y), NumberObject(400), NumberObject(y + 14),
        ]),
        NameObject("/V"): TextStringObject(""),
        NameObject("/DV"): TextStringObject(""),
    })
    annot_refs.append(writer._add_object(tx_field))
    y -= 30

    # /Btn field: gender with /Opt = ["Male", "Female"]
    # /Ff bit 15 (32768) = Radio, bit 16 (65536) = NoToggleToOff
    # Using /Opt for the on-values list (easier to inspect than /AP dicts)
    btn_field = DictionaryObject({
        NameObject("/Type"): NameObject("/Annot"),
        NameObject("/Subtype"): NameObject("/Widget"),
        NameObject("/FT"): NameObject("/Btn"),
        NameObject("/T"): TextStringObject("gender"),
        NameObject("/TU"): TextStringObject("Gender"),
        NameObject("/Ff"): NumberObject(49152),  # Radio + NoToggleToOff
        NameObject("/Rect"): ArrayObject([
            NumberObject(72), NumberObject(y), NumberObject(400), NumberObject(y + 14),
        ]),
        NameObject("/V"): NameObject("/Off"),
        NameObject("/DV"): NameObject("/Off"),
        NameObject("/Opt"): ArrayObject([
            TextStringObject("Male"),
            TextStringObject("Female"),
        ]),
    })
    annot_refs.append(writer._add_object(btn_field))

    page_obj = page.get_object()
    page_obj[NameObject("/Annots")] = ArrayObject(annot_refs)

    acroform = DictionaryObject({
        NameObject("/Fields"): ArrayObject(annot_refs),
        NameObject("/NeedAppearances"): BooleanObject(True),
    })
    acroform_ref = writer._add_object(acroform)
    writer._root_object[NameObject("/AcroForm")] = acroform_ref

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as f:
        writer.write(f)
    print(f"Created /Btn AcroForm PDF (gender radio field): {output_path}")


def make_two_page_pdf(output_path: Path) -> None:
    """Create a 2-page AcroForm PDF with fields split across both pages."""
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
    all_field_refs = []

    for page_defs in (TWO_PAGE_P1_DEFS, TWO_PAGE_P2_DEFS):
        writer.add_blank_page(width=612, height=792)
        page = writer.pages[-1]
        annot_refs = []
        y = 700
        for name, alt in page_defs:
            field_dict = DictionaryObject({
                NameObject("/Type"): NameObject("/Annot"),
                NameObject("/Subtype"): NameObject("/Widget"),
                NameObject("/FT"): NameObject("/Tx"),
                NameObject("/T"): TextStringObject(name),
                NameObject("/TU"): TextStringObject(alt),
                NameObject("/Rect"): ArrayObject([
                    NumberObject(72), NumberObject(y),
                    NumberObject(400), NumberObject(y + 14),
                ]),
                NameObject("/V"): TextStringObject(""),
                NameObject("/DV"): TextStringObject(""),
            })
            ref = writer._add_object(field_dict)
            annot_refs.append(ref)
            all_field_refs.append(ref)
            y -= 20
        page_obj = page.get_object()
        page_obj[NameObject("/Annots")] = ArrayObject(annot_refs)

    acroform = DictionaryObject({
        NameObject("/Fields"): ArrayObject(all_field_refs),
        NameObject("/NeedAppearances"): BooleanObject(True),
    })
    acroform_ref = writer._add_object(acroform)
    writer._root_object[NameObject("/AcroForm")] = acroform_ref

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as f:
        writer.write(f)
    total = len(TWO_PAGE_P1_DEFS) + len(TWO_PAGE_P2_DEFS)
    print(f"Created 2-page AcroForm PDF ({total} fields, 2 pages): {output_path}")


if __name__ == "__main__":
    fixture_dir = Path(__file__).resolve().parent / "fixtures"
    make_acroform_pdf(fixture_dir / "synthetic_form.pdf")
    make_ambiguous_pdf(fixture_dir / "ambiguous_form.pdf")
    make_two_page_pdf(fixture_dir / "two_page_form.pdf")
    make_btn_pdf(fixture_dir / "btn_form.pdf")
