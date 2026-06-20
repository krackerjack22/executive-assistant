"""Tests for extract.py --apply flag."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXTRACT_CLI = PROJECT_ROOT / "skills" / "pdf-form-extraction" / "extract.py"
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
SYNTHETIC_PDF = FIXTURE_DIR / "synthetic_form.pdf"


def test_apply_requires_target_profile(tmp_path):
    """--apply without --target-profile exits non-zero with a clear error message."""
    proc = subprocess.run(
        [
            sys.executable,
            str(EXTRACT_CLI),
            "--input", str(SYNTHETIC_PDF),
            "--apply",
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0, (
        f"Expected non-zero exit when --apply used without --target-profile. "
        f"stdout: {proc.stdout[:300]}"
    )
    assert "target-profile" in proc.stderr.lower() or "target_profile" in proc.stderr.lower(), (
        f"Error message should mention --target-profile. stderr: {proc.stderr}"
    )


# Note: --apply with --target-profile set requires an interactive terminal (stdin tty).
# Full interactive flow must be verified manually:
#   python3 skills/pdf-form-extraction/extract.py \
#       --input <filled_pdf> --target-profile tyler_combs --apply
# The non-tty guard exits 1 cleanly when stdin is not a terminal.

def test_apply_exits_on_non_tty(tmp_path):
    """--apply with --target-profile exits 1 when stdin is not a tty."""
    proc = subprocess.run(
        [
            sys.executable,
            str(EXTRACT_CLI),
            "--input", str(SYNTHETIC_PDF),
            "--target-profile", "tyler_combs",
            "--apply",
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        input="",
    )
    assert proc.returncode == 1, (
        f"Expected exit 1 for non-tty --apply, got {proc.returncode}. "
        f"stderr: {proc.stderr}"
    )
    assert "interactive terminal" in proc.stderr.lower() or "tty" in proc.stderr.lower(), (
        f"Error should mention interactive terminal. stderr: {proc.stderr}"
    )
