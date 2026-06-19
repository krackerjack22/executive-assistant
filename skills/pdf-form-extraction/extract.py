#!/usr/bin/env python3
"""CLI entry point for pdf-form-extraction skill."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Set up sys.path so lib/ and this skill dir are importable
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_SKILL_DIR = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
if str(_SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(_SKILL_DIR))

from lib import preflight as _preflight
from lib import profile_loader as _pl
import pdf_inspect as _inspect


def extract(pdf_path: Path, target_profile_id: str | None = None) -> dict:
    """Extract filled AcroForm values and return a candidate profile-update dict.

    Does NOT write to disk. User reviews + commits manually.

    Returns:
        dict with keys:
          - 'pdf_path': str
          - 'has_acroform': bool
          - 'page_count': int
          - 'fields': list of {name, alt, field_type, value, confidence}
          - 'spatial_map': list of word dicts (from pdfplumber)
          - 'candidate_delta': dict (suggested profile fields to update)
          - 'target_profile_id': str | None
    """
    has_acroform = _inspect.has_acroform(pdf_path)
    page_count = _inspect.get_page_count(pdf_path)

    fields = []
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
            })

    spatial_map = _inspect.get_spatial_map(pdf_path)

    # Build a simple candidate delta from populated fields
    candidate_delta = _build_candidate_delta(fields, target_profile_id)

    return {
        "pdf_path": str(pdf_path),
        "has_acroform": has_acroform,
        "page_count": page_count,
        "fields": fields,
        "spatial_map": spatial_map,
        "candidate_delta": candidate_delta,
        "target_profile_id": target_profile_id,
    }


def _build_candidate_delta(fields: list[dict], profile_id: str | None) -> dict:
    """Build a naive field-name → value mapping for non-empty fields."""
    delta: dict = {}
    for f in fields:
        if f.get("value"):
            delta[f["name"]] = f["value"]
    return {"profile_id": profile_id, "proposed_updates": delta}


def _run_preflight(output_dir: Path, human: bool) -> None:
    result = _preflight.run(output_dir=output_dir)
    if human:
        print(_preflight.human_report(result))
    else:
        print(json.dumps(result, indent=2))
    sys.exit(0 if result["ok"] else 1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract AcroForm fields from a filled PDF."
    )
    parser.add_argument("--input", type=Path, required=False, help="Path to filled PDF.")
    parser.add_argument("--target-profile", default=None, help="Profile ID to annotate the delta.")
    parser.add_argument("--output", type=Path, default=None, help="Write JSON result to this file.")
    parser.add_argument("--check-env", "--preflight", action="store_true", help="Run preflight and exit.")
    parser.add_argument("--human", action="store_true", help="Human-readable preflight output.")

    args = parser.parse_args()

    output_dir = args.output.parent if args.output else Path.cwd()

    if args.check_env:
        _run_preflight(output_dir, args.human)
        return

    # Always run preflight before main operation
    pf = _preflight.run(output_dir=output_dir)
    if not pf["ok"]:
        print(json.dumps({"preflight": pf}, indent=2), file=sys.stderr)
        sys.exit(1)
    if pf["warnings"]:
        for w in pf["warnings"]:
            print(f"[WARNING] [{w['code']}] {w['message']}", file=sys.stderr)

    if not args.input:
        parser.error("--input is required.")

    if not args.input.exists():
        print(f"Error: input PDF not found: {args.input}", file=sys.stderr)
        sys.exit(2)

    result = extract(args.input, target_profile_id=args.target_profile)

    output_json = json.dumps(result, indent=2, default=str)

    if args.output:
        args.output.write_text(output_json)
        print(f"Extraction written to: {args.output}")
    else:
        print(output_json)


if __name__ == "__main__":
    main()
