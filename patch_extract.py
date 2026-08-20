import re

with open("skills/pdf-form-extraction/extract.py", "r") as f:
    content = f.read()

old_extract = """    fields = []
    if has_acroform:
        raw_fields = _inspect.get_acroform_fields(pdf_path)
        for f in raw_fields:
            val = f.get("value")
            # Strip pypdf type wrappers
            if hasattr(val, "get_object"):
                val = str(val.get_object())
            elif val is not None:
                val = str(val)
            confidence = "high" if val else "empty"
            fields.append({
                "name": f["name"],
                "alt": f["alt"],
                "field_type": f["field_type"],
                "value": val,
                "confidence": confidence,
            })"""

new_extract = """    fields = []
    if has_acroform:
        raw_fields = _inspect.get_acroform_fields(pdf_path)
        for f in raw_fields:
            val = f.get("value")
            if hasattr(val, "get_object"):
                val = str(val.get_object())
            elif val is not None:
                val = str(val)
            confidence = "high" if val else "empty"
            fields.append({
                "name": f["name"],
                "alt": f["alt"],
                "field_type": f["field_type"],
                "value": val,
                "confidence": confidence,
            })
    else:
        # If it's flattened, use the new AI layout schema extractor!
        import schema_extractor
        schema = schema_extractor.get_or_create_schema(pdf_path)
        for item in schema:
            label = item.get("label")
            if label:
                # We don't have filled values for flattened PDFs in this flow yet (that requires a VLM OCR pass)
                # But this gets the schema blanks into the system!
                fields.append({
                    "name": label,
                    "alt": label,
                    "field_type": "checkbox" if item.get("is_checkbox") else "text",
                    "value": None,
                    "confidence": "empty"
                })"""

content = content.replace(old_extract, new_extract)

with open("skills/pdf-form-extraction/extract.py", "w") as f:
    f.write(content)

