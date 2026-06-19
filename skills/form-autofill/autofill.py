#!/usr/bin/env python3
"""CLI entry point for form-autofill skill."""

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
import acroform as _acroform


def _run_preflight(output_dir: Path, human: bool) -> None:
    result = _preflight.run(output_dir=output_dir)
    if human:
        print(_preflight.human_report(result))
    else:
        print(json.dumps(result, indent=2))
    sys.exit(0 if result["ok"] else 1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Autofill an AcroForm PDF from a family profile."
    )
    parser.add_argument("--template", type=Path, help="Path to blank AcroForm PDF.")
    parser.add_argument("--profile", default="tyler_combs", help="Profile ID to fill from.")
    parser.add_argument("--output", type=Path, help="Output PDF path (default: <template>_filled.pdf).")
    parser.add_argument("--output-dir", type=Path, help="Output directory (default: same as template).")
    parser.add_argument("--commit", action="store_true", help="Actually write the filled PDF. Default is dry-run.")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Preview only (default).")
    parser.add_argument("--check-env", "--preflight", action="store_true", help="Run preflight and exit.")
    parser.add_argument("--human", action="store_true", help="Human-readable preflight output (with --check-env).")
    parser.add_argument("--json-output", action="store_true", help="Force JSON output for fill result.")

    args = parser.parse_args()

    output_dir = args.output_dir or (args.template.parent if args.template else Path.cwd())

    if args.check_env:
        _run_preflight(output_dir, args.human)
        return  # unreachable

    # Always run preflight before main operation
    pf = _preflight.run(output_dir=output_dir)
    if not pf["ok"]:
        print(json.dumps({"preflight": pf}, indent=2), file=sys.stderr)
        sys.exit(1)
    if pf["warnings"]:
        for w in pf["warnings"]:
            print(f"[WARNING] [{w['code']}] {w['message']}", file=sys.stderr)

    if not args.template:
        parser.error("--template is required.")

    if not args.template.exists():
        print(f"Error: template PDF not found: {args.template}", file=sys.stderr)
        sys.exit(2)

    try:
        profile = _pl.load_profile(args.profile)
        index = _pl.load_index()
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    dry_run = not args.commit

    if args.output:
        output_pdf = args.output
    else:
        stem = args.template.stem
        output_pdf = output_dir / f"{stem}_filled.pdf"

    result = _acroform.fill(
        template_pdf=args.template,
        profile=profile,
        index=index,
        output_pdf=output_pdf,
        dry_run=dry_run,
    )

    if args.json_output or not sys.stdout.isatty():
        print(json.dumps(result, indent=2))
    else:
        mode = result["mode"]
        print(f"\n=== Autofill {mode.upper()} ===")
        print(f"Profile: {args.profile}  |  Fields: {result['filled_count']} filled, {result['skipped_count']} skipped\n")
        for f in result["fields"]:
            status = "✓" if not f["skipped"] else "—"
            val_display = f"= {f['mapped_value']!r}" if f["mapped_value"] else "(no match)"
            print(f"  {status}  {f['name']!r:40s}  {val_display}")
            if not f["skipped"]:
                print(f"       source: {f['source']}")
        if mode == "filled":
            print(f"\nOutput written to: {result['output']}")
        else:
            print("\n[DRY-RUN] Pass --commit to write the file.")


if __name__ == "__main__":
    main()
