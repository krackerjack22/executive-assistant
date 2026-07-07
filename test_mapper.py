import sys
import os
sys.path.append(os.path.join(os.getcwd(), "skills", "pdf-form-autofill"))
import field_mapper as fm
import importlib
importlib.reload(fm)

profile = {"profile_id": "charlotte_combs"}

norm_name = "signature"
norm_alt = "____________________________ signature:"
adjacent_text = ""
line_text = "PLAYER NAME: ____________________________ Signature: ___________________________________"
fill_state = {}

res = fm._is_signature_or_initials_field(norm_name, norm_alt, adjacent_text, profile, fill_state, line_text)
print("Player Line Result:", res)
