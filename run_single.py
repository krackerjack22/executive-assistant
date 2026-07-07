import sys
import os
sys.path.append(os.getcwd())

import skills.pdf_form_autofill.autofill as autofill

class Args:
    template = "tests/test_docs/signature_tests/2008 Player-Parent Agreement.pdf"
    profile = "charlotte_combs"
    output = None
    output_dir = None
    commit = False
    commit_unsafe = True
    resolve = False
    check_env = False
    human = False
    json_output = False
    missing_mode = "skip"
    qa = False
    qa_model = "gemini-1.5-flash"
    vision_qa = False

# We must mock sys.argv or use the functions directly
import pathlib
args = Args()
args.template = pathlib.Path(args.template)

import lib.profiles as _pl
profile = _pl.load_profile(args.profile)
index = _pl.load_index()

import skills.pdf_form_autofill.overlay as _overlay
res = _overlay.fill(
    template_pdf=args.template,
    profile=profile,
    index=index,
    output_pdf=None,
    dry_run=True,
    skip_confidences=frozenset()
)
import pprint
pprint.pprint(res["fields"])
