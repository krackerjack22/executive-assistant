import re

# 1. Patch layout_analyzer.py
with open("skills/pdf-form-autofill/layout_analyzer.py", "r") as f:
    la = f.read()
    
# Remove dedupe_chars and get_blanks
la = re.sub(r'def dedupe_chars\(.*?return "".join\(res\)', '', la, flags=re.DOTALL)
la = re.sub(r'def get_blanks\(.*?(?=def analyze_pdf)', '', la, flags=re.DOTALL)

# Add import
la = la.replace("import json", "import json\nfrom blanks_extractor import get_blanks, dedupe_chars")

with open("skills/pdf-form-autofill/layout_analyzer.py", "w") as f:
    f.write(la)

# 2. Patch anchor_mapper.py
with open("skills/pdf-form-autofill/anchor_mapper.py", "r") as f:
    am = f.read()

am = re.sub(r'def dedupe_chars\(.*?return "".join\(res\)', '', am, flags=re.DOTALL)
am = re.sub(r'def get_blanks\(.*?(?=def find_best_blank)', '', am, flags=re.DOTALL)

am = am.replace("from rapidfuzz import fuzz", "from rapidfuzz import fuzz\nfrom blanks_extractor import get_blanks, dedupe_chars")

with open("skills/pdf-form-autofill/anchor_mapper.py", "w") as f:
    f.write(am)

