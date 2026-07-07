import sys
from pathlib import Path

# Mock vision_qa
def mock_review_signatures(fields, rendered_pdf_path):
    print("MOCK: Pretending to find an overlap!")
    return {"Parent/Guardian Signature Date": "[SIGNATURE_IMAGE:0.5]:/Users/tylercombs/Library/CloudStorage/GoogleDrive-tylercombs@gmail.com/Shared drives/Combslink/Assets_Library/Executive-Assistant/profiles/signature/signature.png"}

import vision_qa
vision_qa.review_signatures = mock_review_signatures

# Run autofill programmatically
import sys
sys.argv = ["autofill.py", "--template", "tests/test_docs/signature_tests/Liability Waiver Guardian.pdf", "--profile", "charlotte_combs", "--commit-unsafe", "--human", "--vision-qa"]
from autofill import main
main()
