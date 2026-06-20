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

_CONFIDENCE_LABEL = {
    "high": "CONFIDENT",
    "medium": "CHECK",
    "low": "ASK",
    "none": "MISSING",
}


def _run_preflight(output_dir: Path, human: bool) -> None:
    result = _preflight.run(output_dir=output_dir)
    if human:
        print(_preflight.human_report(result))
    else:
        print(json.dumps(result, indent=2))
    sys.exit(0 if result["ok"] else 1)


def _render_human(result: dict) -> str:
    """Format a fill result as a human-readable table."""
    lines = []
    mode = result["mode"]
    lines.append(
        f"\n=== Autofill {mode.upper()}  "
        f"filled={result['filled_count']}  "
        f"skipped={result['skipped_count']}  "
        f"low={result['low_count']} ==="
    )
    lines.append("")
    for f in result["fields"]:
        label = _CONFIDENCE_LABEL.get(f.get("confidence", "none"), "?")
        val_display = f"= {f['mapped_value']!r}" if f["mapped_value"] else "= (none)"
        lines.append(f"  {label:9s}  [{f['name']}]  {val_display}")
        if f.get("source"):
            lines.append(f"             via: {f['source']}")
        for alt in f.get("alternatives") or []:
            lines.append(
                f"             ALT: {alt['candidate_value']!r}"
                f" ({alt['candidate_source']}) score={alt['score']:.2f}"
            )
        for note in f.get("notes") or []:
            lines.append(f"             NOTE: {note}")
    if mode == "filled":
        lines.append(f"\nOutput written to: {result['output']}")
    else:
        lines.append("\n[DRY-RUN] Pass --commit to write the file.")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Autofill an AcroForm PDF from a family profile."
    )
    parser.add_argument("--template", type=Path, help="Path to blank AcroForm PDF.")
    parser.add_argument(
        "--profile", default="tyler_combs", help="Profile ID to fill from."
    )
    parser.add_argument(
        "--output", type=Path, help="Output PDF path (default: <template>_filled.pdf)."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory (default: same as template).",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Write the filled PDF. Refused if any field is low-confidence.",
    )
    parser.add_argument(
        "--commit-unsafe",
        action="store_true",
        help="Write the filled PDF even when low-confidence fields are present.",
    )
    parser.add_argument(
        "--resolve",
        action="store_true",
        help="(v1.5 stub) Interactively resolve low-confidence fields before commit.",
    )
    parser.add_argument(
        "--check-env",
        "--preflight",
        action="store_true",
        help="Run preflight and exit.",
    )
    parser.add_argument(
        "--human",
        action="store_true",
        help="Human-readable output (table format).",
    )
    parser.add_argument(
        "--json-output",
        action="store_true",
        help="Force JSON output for fill result.",
    )

    args = parser.parse_args()

    # --resolve is a v1.5 stub
    if args.resolve:
        print("--resolve: v1.5 feature not yet implemented")
        sys.exit(0)

    output_dir = args.output_dir or (
        args.template.parent if args.template else Path.cwd()
    )

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

    if args.output:
        output_pdf = args.output
    else:
        stem = args.template.stem
        output_pdf = output_dir / f"{stem}_filled.pdf"

    # First always do a dry-run to gather the mapping result
    dry_result = _acroform.fill(
        template_pdf=args.template,
        profile=profile,
        index=index,
        output_pdf=output_pdf,
        dry_run=True,
    )

    want_commit = args.commit or args.commit_unsafe

    # Refuse --commit (without --commit-unsafe) if any field is low confidence
    if args.commit and not args.commit_unsafe and dry_result["low_count"] > 0:
        low_names = [
            f["name"]
            for f in dry_result["fields"]
            if f.get("confidence") == "low"
        ]
        msg = (
            f"Commit refused: {dry_result['low_count']} field(s) have low confidence: "
            f"{low_names}.\n"
            "Pass --commit-unsafe to write anyway, or --resolve (v1.5) to fix interactively."
        )
        print(msg, file=sys.stderr)
        sys.exit(1)

    if want_commit:
        result = _acroform.fill(
            template_pdf=args.template,
            profile=profile,
            index=index,
            output_pdf=output_pdf,
            dry_run=False,
        )
    else:
        result = dry_result

    use_json = args.json_output or (not args.human and not sys.stdout.isatty())

    if use_json:
        print(json.dumps(result, indent=2))
    else:
        print(_render_human(result))


if __name__ == "__main__":
    main()
