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
from lib import profile_writer as _pw
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


def _run_resolve(
    dry_result: dict,
    template_pdf: Path,
    profile: dict,
    index: dict,
    output_pdf: Path,
    use_json: bool,
    qa_corrections: dict | None = None,
) -> None:
    """Interactive resolution of low-confidence fields, then commit."""
    if dry_result["low_count"] == 0:
        print("No low-confidence fields — committing directly.")
        result = _acroform.fill(
            template_pdf=template_pdf,
            profile=profile,
            index=index,
            output_pdf=output_pdf,
            dry_run=False,
            field_overrides=qa_corrections or {},
        )
        if use_json:
            print(json.dumps(result, indent=2))
        else:
            print(_render_human(result))
        sys.exit(0)

    # Interactive loop requires a terminal
    if not sys.stdin.isatty():
        print(
            "Error: --resolve requires an interactive terminal (stdin is not a tty).",
            file=sys.stderr,
        )
        sys.exit(1)

    overrides: dict[str, str | None] = {}
    learning_candidates: list[dict] = []

    for field in dry_result["fields"]:
        if field.get("confidence") != "low":
            continue
        print(
            f'\nField "{field["name"]}" — suggested: {field["mapped_value"]!r}'
            f' via {field["source"]}'
        )
        alts = field.get("alternatives") or []
        if alts:
            print("  Alternatives:")
            for i, alt in enumerate(alts, 1):
                print(
                    f"    {i}. {alt['candidate_value']!r}"
                    f" ({alt['candidate_source']}) score={alt['score']:.2f}"
                )
        print("  [Y]es / [N]o pick alternative / [E]nter value / [S]kip : ", end="", flush=True)
        choice = input().strip().upper()

        if choice in ("Y", ""):
            overrides[field["name"]] = field["mapped_value"]
            dot_path = _dot_path_from_source(field.get("source", ""))
            if dot_path:
                learning_candidates.append({
                    "pdf_field_name": field["name"],
                    "pdf_field_alt": field.get("alt", ""),
                    "dot_path": dot_path,
                    "action": "confirmed",
                })
        elif choice == "N":
            if not alts:
                print("  (no alternatives) keeping original.")
                overrides[field["name"]] = field["mapped_value"]
            else:
                print(f"  Pick 1-{len(alts)}: ", end="", flush=True)
                pick = input().strip()
                try:
                    idx = int(pick) - 1
                    chosen_alt = alts[idx]
                    overrides[field["name"]] = chosen_alt["candidate_value"]
                    learning_candidates.append({
                        "pdf_field_name": field["name"],
                        "pdf_field_alt": field.get("alt", ""),
                        "dot_path": chosen_alt["candidate_source"],
                        "action": "alternative_picked",
                    })
                except (ValueError, IndexError):
                    print("  Invalid pick — keeping original.")
                    overrides[field["name"]] = field["mapped_value"]
        elif choice == "E":
            print("  Enter value: ", end="", flush=True)
            raw_val = input().strip()
            overrides[field["name"]] = raw_val or None
            # E values: no dot_path can be inferred — skip from learning
        elif choice == "S":
            overrides[field["name"]] = None
        else:
            # Unrecognised → keep
            overrides[field["name"]] = field["mapped_value"]

    # Apply overrides into the dry_result fields so the commit picks them up
    for field in dry_result["fields"]:
        if field["name"] in overrides:
            field["mapped_value"] = overrides[field["name"]]

    result = _acroform.fill(
        template_pdf=template_pdf,
        profile=profile,
        index=index,
        output_pdf=output_pdf,
        dry_run=False,
        field_overrides={**overrides, **(qa_corrections or {})},
    )
    if use_json:
        print(json.dumps(result, indent=2))
    else:
        print(_render_human(result))

    _offer_learning(learning_candidates, template_pdf, profile)
    sys.exit(0)


def _dot_path_from_source(source: str) -> str | None:
    """Extract dot_path from a source string like 'token → dot.path'."""
    if " → " in source:
        return source.split(" → ")[-1].strip()
    return None


def _offer_learning(
    candidates: list[dict],
    template_pdf: Path,
    profile: dict,
) -> None:
    """Batch learning prompt: offer to save resolved fields as learned synonyms."""
    if not candidates or not sys.stdin.isatty():
        return

    import learning as _learning

    saveable: list[dict] = []
    for cand in candidates:
        token = _learning.derive_token(
            cand["pdf_field_name"], cand["pdf_field_alt"]
        )
        if token is None or _learning.is_pollution_candidate(token):
            continue
        saveable.append({**cand, "_token": token})

    if not saveable:
        return

    n_total = len(candidates)
    n_saveable = len(saveable)
    high_volume = n_total > 10

    if high_volume:
        prompt = (
            f"\nYou resolved {n_total} fields. Save {n_saveable} as learned synonyms"
            " so future forms recognize them automatically? [N]o / [Y]es / [P]ick: "
        )
    else:
        prompt = (
            f"\nYou resolved {n_total} fields. Save {n_saveable} as learned synonyms"
            " so future forms recognize them automatically? [Y]es / [N]o / [P]ick: "
        )

    print(prompt, end="", flush=True)
    choice = input().strip().upper()

    if high_volume and choice not in ("Y", "P"):
        return
    if not high_volume and choice not in ("Y", "P"):
        return

    subset = saveable
    if choice == "P":
        print("  Entries to save:")
        for i, c in enumerate(saveable, 1):
            print(f"    {i}. [{c['_token']}] → {c['dot_path']} ({c['action']})")
        print(
            f"  Enter numbers (1–{len(saveable)}, comma-separated): ",
            end="", flush=True,
        )
        raw = input().strip()
        try:
            indices = [int(x.strip()) - 1 for x in raw.split(",")]
            subset = [saveable[i] for i in indices if 0 <= i < len(saveable)]
        except (ValueError, IndexError):
            print("  Invalid selection — saving none.")
            return

    if not subset:
        return

    source_form = template_pdf.name
    profile_id = profile.get("profile_id")
    entries: dict[str, dict] = {}
    for cand in subset:
        token = cand["_token"]
        entry = _learning.build_entry(
            dot_path=cand["dot_path"],
            source_form=source_form,
            pdf_field_name=cand["pdf_field_name"],
            pdf_field_alt=cand["pdf_field_alt"],
            learn_action=cand["action"],
            profile_id=profile_id,
            notes=[],
        )
        entries[token] = entry

    synonyms_path = Path(__file__).parent / "data" / "synonyms.json"
    try:
        _learning.save_learned(entries, synonyms_path)
        import field_mapper as _fmmod
        _fmmod.clear_synonyms_cache()
        print(f"  Saved {len(entries)} learned synonym(s).")
    except PermissionError:
        print(
            "Cannot write synonyms.json: check permissions.",
            file=sys.stderr,
        )


_SKIP_CONFIDENCES: frozenset = frozenset({"low", "none"})

_SECTION_KEYWORDS: list[tuple[str, str]] = [
    ("insurance", "insurance"),
    ("subscriber", "insurance"),
    ("member id", "insurance"),
    ("school", "school"),
    ("emergency", "emergency_contact"),
    ("phone", "contact"),
    ("email", "contact"),
    ("address", "contact"),
    ("zip", "contact"),
    ("city", "contact"),
    ("state", "contact"),
    ("name", "identity"),
    ("birth", "identity"),
    ("dob", "identity"),
    ("ssn", "identity"),
    ("sex", "identity"),
    ("gender", "identity"),
    ("date of birth", "identity"),
]


def _field_section(field: dict) -> str:
    """Derive a semantic section label from field name or source."""
    name = (field.get("name") or "").lower()
    source = (field.get("source") or "").lower()
    for kw, section in _SECTION_KEYWORDS:
        if kw in name:
            return section
    first_seg = source.split(".")[0].strip()
    mapping = {
        "identity": "identity",
        "contact": "contact",
        "insurance": "insurance",
        "school": "school",
        "emergency_contacts": "emergency_contact",
    }
    return mapping.get(first_seg, "other")


def _run_skip_mode(
    dry_result: dict,
    template_pdf: Path,
    profile: dict,
    index: dict,
    output_pdf: Path,
    use_json: bool,
    qa_corrections: dict | None = None,
) -> None:
    """Fill only high/medium confidence fields; skip low/none and print summary."""
    low_none = [
        f for f in dry_result["fields"]
        if f.get("confidence") in ("low", "none")
    ]
    if low_none:
        print("Skipped fields (low/none confidence):")
        for f in low_none:
            print(f"  - {f['name']} (confidence: {f.get('confidence', 'none')})")

    result = _acroform.fill(
        template_pdf=template_pdf,
        profile=profile,
        index=index,
        output_pdf=output_pdf,
        dry_run=False,
        skip_confidences=_SKIP_CONFIDENCES,
        field_overrides=qa_corrections or {},
    )
    if use_json:
        print(json.dumps(result, indent=2))
    else:
        print(_render_human(result))
    sys.exit(0)


def _run_manual_mode(
    dry_result: dict,
    template_pdf: Path,
    profile: dict,
    index: dict,
    output_pdf: Path,
    use_json: bool,
    qa_corrections: dict | None = None,
) -> None:
    """Fill high/medium fields only; write a sidecar .missing.md checklist."""
    result = _acroform.fill(
        template_pdf=template_pdf,
        profile=profile,
        index=index,
        output_pdf=output_pdf,
        dry_run=False,
        skip_confidences=_SKIP_CONFIDENCES,
        field_overrides=qa_corrections or {},
    )

    missing = [
        f for f in dry_result["fields"]
        if f.get("confidence") in ("low", "none")
    ]

    form_name = template_pdf.stem
    sidecar_path = output_pdf.with_name(output_pdf.stem + ".missing.md")
    lines = [
        f"# Manual fields for {form_name}",
        "The following fields could not be auto-filled:",
        "",
    ]
    for f in missing:
        conf = f.get("confidence", "none")
        nearest = f.get("source") or "none found"
        lines.append(f'- [ ] Field "{f["name"]}" (confidence: {conf})')
        lines.append(f"    Nearest profile field: {nearest}")
    sidecar_path.write_text("\n".join(lines) + "\n")

    print(f"Output PDF: {output_pdf}")
    print(f"Missing fields checklist: {sidecar_path}")
    if use_json:
        print(json.dumps(result, indent=2))
    else:
        print(_render_human(result))
    sys.exit(0)


def _run_interview_mode(
    dry_result: dict,
    template_pdf: Path,
    profile: dict,
    profile_id: str,
    index: dict,
    output_pdf: Path,
    use_json: bool,
    qa_corrections: dict | None = None,
) -> None:
    """Interactively collect values for none-confidence fields, then fill and write back."""
    if not sys.stdin.isatty():
        print(
            "Error: --missing-mode interview requires an interactive terminal "
            "(stdin is not a tty).",
            file=sys.stderr,
        )
        sys.exit(1)

    none_fields = [
        f for f in dry_result["fields"]
        if f.get("confidence") == "none"
    ]

    if not none_fields:
        print("No missing fields — proceeding with full fill.")
        result = _acroform.fill(
            template_pdf=template_pdf,
            profile=profile,
            index=index,
            output_pdf=output_pdf,
            dry_run=False,
            field_overrides=qa_corrections or {},
        )
        if use_json:
            print(json.dumps(result, indent=2))
        else:
            print(_render_human(result))
        sys.exit(0)

    # Group by semantic section
    from collections import defaultdict
    by_section: dict[str, list[dict]] = defaultdict(list)
    for f in none_fields:
        by_section[_field_section(f)].append(f)

    user_answers: dict[str, str] = {}

    for section, fields in by_section.items():
        print(f"\n=== {section.replace('_', ' ').title()} fields ===")
        batch: list[dict] = []
        for f in fields:
            batch.append(f)
            if len(batch) >= 5:
                _collect_batch(batch, user_answers)
                batch = []
        if batch:
            _collect_batch(batch, user_answers)

    if not user_answers:
        print("No values provided — filling with confident fields only.")
        result = _acroform.fill(
            template_pdf=template_pdf,
            profile=profile,
            index=index,
            output_pdf=output_pdf,
            dry_run=False,
            skip_confidences=_SKIP_CONFIDENCES,
            field_overrides=qa_corrections or {},
        )
        if use_json:
            print(json.dumps(result, indent=2))
        else:
            print(_render_human(result))
        sys.exit(0)

    # Confirmation summary
    print("\n=== Confirm the following values ===")
    for fname, val in user_answers.items():
        print(f'  "{fname}" → {val!r}')
    print("\nApply? [Y]es / [N]o (abort): ", end="", flush=True)
    choice = input().strip().upper()
    if choice not in ("Y", ""):
        print("Aborted. No files written, no profile updated.")
        sys.exit(0)

    # Fill PDF with confident fields + user-provided values
    result = _acroform.fill(
        template_pdf=template_pdf,
        profile=profile,
        index=index,
        output_pdf=output_pdf,
        dry_run=False,
        skip_confidences=_SKIP_CONFIDENCES,
        field_overrides={**user_answers, **(qa_corrections or {})},
    )

    # Write back to profile (one source_note per answered field)
    import json as _json_mod
    raw_profile_path = (
        Path(__file__).resolve().parent.parent.parent
        / "lib"
    )
    from lib import env as _env
    from lib import env as _env2  # noqa: F811
    profiles_dir = _env.profiles_dir()
    profile_file = profiles_dir / f"{profile_id}.json"

    for fname, val in user_answers.items():
        with profile_file.open() as pf:
            current = _json_mod.load(pf)
        source_note = {
            "field": fname,
            "source_form": template_pdf.stem,
            "source_form_path": str(template_pdf),
            "value_provided": val,
            "applied_by": "user via interview",
        }
        _pw.write_profile(profile_id, current, source_note)
        print(f"  Profile updated: {fname!r} noted.")

    if use_json:
        print(json.dumps(result, indent=2))
    else:
        print(_render_human(result))
    sys.exit(0)


def _collect_batch(batch: list[dict], answers: dict[str, str]) -> None:
    """Present a batch of fields and collect answers into `answers`."""
    for i, f in enumerate(batch, 1):
        hint = f.get("source") or "no profile data found"
        print(f'{i}. "{f["name"]}" — {hint}')
        print("   Enter value (or press Enter to skip): ", end="", flush=True)
        val = input().strip()
        if val:
            answers[f["name"]] = val


def _run_qa_pass(
    dry_result: dict,
    template_pdf: Path,
    profile: dict,
    model: str,
) -> dict[str, str | None]:
    """Run the LLM QA review; return a dict of accepted field corrections.

    Interactively prompts the user to accept or reject each suggested correction
    when running in a tty. In non-interactive mode, issues are printed but no
    corrections are applied (re-run interactively to apply them).

    Returns:
        Mapping of ``{pdf_field_name: corrected_value}`` for accepted corrections.
        Empty dict if no issues found or none accepted.
    """
    import qa_reviewer

    print("\n[QA] Running LLM review — this may take a few seconds...")
    try:
        issues = qa_reviewer.review_fills(
            dry_result["fields"], template_pdf, profile, model
        )
    except RuntimeError as exc:
        print(f"[QA] Skipped: {exc}", file=sys.stderr)
        return {}

    if not issues:
        print("[QA] No contextual issues found.")
        return {}

    print(f"\n[QA] {len(issues)} issue(s) found:")
    corrections: dict[str, str | None] = {}

    if not sys.stdin.isatty():
        for issue in issues:
            print(
                f"  [{issue.get('confidence', '?')}] {issue['field_name']!r}: "
                f"{issue.get('current_value')!r} → {issue.get('suggested_value')!r}"
            )
            print(f"    {issue.get('reason', '')}")
        print(
            "\n[QA] Non-interactive mode — corrections not applied. "
            "Re-run in a terminal to apply them."
        )
        return {}

    for issue in issues:
        field = issue.get("field_name", "")
        cur = issue.get("current_value")
        sug = issue.get("suggested_value")
        reason = issue.get("reason", "")
        print(f"\n  Field:     {field!r}")
        print(f"  Current:   {cur!r}")
        print(f"  Suggested: {sug!r}")
        print(f"  Reason:    {reason}")
        print("  Apply? [Y]es / [N]o (default N): ", end="", flush=True)
        choice = input().strip().upper()
        if choice == "Y":
            corrections[field] = sug

    if corrections:
        print(f"\n[QA] Accepted {len(corrections)} correction(s).")
    else:
        print("\n[QA] No corrections accepted.")
    return corrections


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
        help="Interactively resolve low-confidence fields before committing.",
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
    parser.add_argument(
        "--missing-mode",
        choices=["skip", "manual", "interview"],
        dest="missing_mode",
        help=(
            "How to handle low/none-confidence fields: "
            "skip=omit and print summary; "
            "manual=write sidecar checklist; "
            "interview=prompt user interactively."
        ),
    )
    parser.add_argument(
        "--qa",
        action="store_true",
        help=(
            "Run a Claude LLM quality-assurance pass after the fill to catch "
            "section-context errors (e.g. sibling fields filled with subject data). "
            "Requires ANTHROPIC_API_KEY to be set."
        ),
    )
    parser.add_argument(
        "--qa-model",
        default="claude-haiku-4-5-20251001",
        dest="qa_model",
        metavar="MODEL",
        help="Claude model ID to use for --qa (default: claude-haiku-4-5-20251001).",
    )

    args = parser.parse_args()

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

    use_json = args.json_output or (not args.human and not sys.stdout.isatty())

    # First always do a dry-run to gather the mapping result
    dry_result = _acroform.fill(
        template_pdf=args.template,
        profile=profile,
        index=index,
        output_pdf=output_pdf,
        dry_run=True,
    )

    # Optional LLM QA pass — flags section-context errors before commit
    qa_corrections: dict[str, str | None] = {}
    if args.qa:
        qa_corrections = _run_qa_pass(dry_result, args.template, profile, args.qa_model)
        for field in dry_result["fields"]:
            if field["name"] in qa_corrections:
                field["mapped_value"] = qa_corrections[field["name"]]
                field.setdefault("notes", []).append("[QA-corrected]")

    # --missing-mode: handle missing/low-confidence fields
    if args.missing_mode == "skip":
        _run_skip_mode(
            dry_result, args.template, profile, index, output_pdf, use_json,
            qa_corrections=qa_corrections,
        )
        return  # always calls sys.exit()

    if args.missing_mode == "manual":
        _run_manual_mode(
            dry_result, args.template, profile, index, output_pdf, use_json,
            qa_corrections=qa_corrections,
        )
        return  # always calls sys.exit()

    if args.missing_mode == "interview":
        _run_interview_mode(
            dry_result, args.template, profile, args.profile, index, output_pdf, use_json,
            qa_corrections=qa_corrections,
        )
        return  # always calls sys.exit()

    # --resolve: interactive low-confidence resolution then commit
    if args.resolve:
        _run_resolve(
            dry_result, args.template, profile, index, output_pdf, use_json,
            qa_corrections=qa_corrections,
        )
        return  # _run_resolve always calls sys.exit()

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
            "Pass --commit-unsafe to write anyway, or --resolve to fix interactively."
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
            field_overrides=qa_corrections or {},
        )
    else:
        result = dry_result

    if use_json:
        print(json.dumps(result, indent=2))
    else:
        print(_render_human(result))

    # Summarize vault-locked fields when committing (not commit-unsafe)
    if want_commit and not args.commit_unsafe:
        vault_locked = [
            f for f in result["fields"]
            if f.get("confidence") == "none"
            and any(
                "Vault locked" in (n or "")
                for n in (f.get("notes") or [])
            )
        ]
        if vault_locked:
            print(
                f"Note: {len(vault_locked)} vault-backed field(s) skipped (vault locked)."
                " Run 'bw unlock' and re-run to include them.",
                file=sys.stderr,
            )


if __name__ == "__main__":
    main()
