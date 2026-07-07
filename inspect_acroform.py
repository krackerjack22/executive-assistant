from pypdf import PdfReader
reader = PdfReader("tests/test_docs/signature_tests/Liability Waiver Guardian.pdf")
fields = reader.get_fields()
if fields:
    for name, f in fields.items():
        print(f"{name}: {f.get('/Rect')}")
else:
    print("No fields found")
