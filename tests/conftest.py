"""Pytest configuration — add project root to sys.path."""
import sys
from pathlib import Path

# Project root
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# pdf-form-autofill skill dir (for acroform, field_mapper, overlay)
_AUTOFILL_DIR = _ROOT / "skills" / "pdf-form-autofill"
if str(_AUTOFILL_DIR) not in sys.path:
    sys.path.insert(0, str(_AUTOFILL_DIR))

# pdf-form-extraction skill dir (for pdf_inspect)
_EXTRACT_DIR = _ROOT / "skills" / "pdf-form-extraction"
if str(_EXTRACT_DIR) not in sys.path:
    sys.path.insert(0, str(_EXTRACT_DIR))
