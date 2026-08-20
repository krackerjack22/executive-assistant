import sys
from pathlib import Path

sys.path.append("/Users/tylercombs/Dev/executive-assistant")
sys.path.append("/Users/tylercombs/Dev/executive-assistant/skills/pdf-form-autofill")

from lib import profile_loader as _pl
import autofill

profile = _pl.load_profile("tyler_combs")
index = _pl.load_index()

kwargs = {
    "profile": profile,
    "index": index,
    "output_pdf": Path("/Users/tylercombs/Downloads/W-9_TylerCombs_Filled.pdf"),
    "dry_run": False,
    "skip_confidences": set(),
    "field_overrides": {"tax or proprietor": "X"}
}

res = autofill._fill_pdf(template_pdf=Path("tests/test_docs/autofill_tests/W-9_Blank.pdf"), **kwargs)
print("FILLED COUNT:", res["filled_count"])
