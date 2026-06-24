import re

with open("skills/form-autofill/autofill.py", "r") as f:
    content = f.read()

# Add _fill_pdf function after imports
routing_func = """
import overlay as _overlay
import pypdf

def _fill_pdf(template_pdf, **kwargs):
    reader = pypdf.PdfReader(str(template_pdf))
    root = reader.trailer.get("/Root", {})
    if "/AcroForm" in root:
        return _acroform.fill(template_pdf=template_pdf, **kwargs)
    return _overlay.fill(template_pdf=template_pdf, **kwargs)

"""

content = content.replace("import acroform as _acroform", "import acroform as _acroform\n" + routing_func)
content = content.replace("_acroform.fill(", "_fill_pdf(")

with open("skills/form-autofill/autofill.py", "w") as f:
    f.write(content)
