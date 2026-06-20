# Handoff — Tier 3 Issues (GitHub issues #6–#9)

**Prerequisite:** HANDOFF_TIER1_TIER2.md must be complete before starting
this session. All 153+ tests from that session must be passing.

Paste everything below into a fresh Claude Code session opened in
`/Users/tylercombs/Dev/executive-assistant`.

---

## Scope evaluation note

Issues #7, #6, and #8 are tightly chained (#7 is a prerequisite for the
others) and together form one coherent "profile write-back" feature arc.
Issue #9 (spatial overlay) is architecturally independent and significantly
heavier — treat it as optional within this session. Complete #7 → #6 → #8
first; only start #9 if those three are done and tested.

---

## Project context

Personal executive-assistant CLI. Fills blank AcroForm PDFs from family
profile JSON files. Two child skills:

- `skills/form-autofill/` — fills blank PDFs
- `skills/pdf-form-extraction/` — extracts values from filled PDFs

Shared library in `lib/`. Profile JSONs live at
`~/Assets_Library/Executive-Assistant/profiles/` (env-var driven — never
hardcode that path).

**Zero PII ever goes in any `.py`, `.md`, or config file in the repo.**

---

## Current state

- 153+ tests passing. Run with `/usr/bin/python3 -m pytest tests/ -q`
- Python is `/usr/bin/python3` (3.9.6). Never use bare `python3`.
  Every file needs `from __future__ import annotations`.
- pypdf 6.11.0, pdfplumber installed.

Read these files before touching anything:
1. `lib/profile_loader.py` — how profiles are loaded and resolved
2. `skills/form-autofill/autofill.py` — CLI entry point
3. `skills/pdf-form-extraction/extract.py` — extraction CLI
4. `MVP_CONTRACT_addendum_2_missing_data.md` — full spec for all three
   missing-data modes and the profile write-back safety contract

---

## Critical constraints

- Zero PII in any `.py`, `.md`, or config file.
- Never hardcode `/Users/tylercombs/...` — use `lib/env.py`.
- Dry-run is default; `--commit` required to write files.
- Profile writes must be atomic (temp file + rename). Spec below.
- All existing tests must pass after each issue.
- Use `/usr/bin/python3` for all test runs.

---

## Issue #7 — FEATURE: Profile atomic write-back (build this first)

**New file:** `lib/profile_writer.py`

This is the prerequisite for #6 interview mode and #8. Build it first,
independently, with its own tests.

**Contract (from MVP_CONTRACT_addendum_2.md):**

```python
def write_profile(
    profile_id: str,
    updated_dict: dict,
    source_note: dict,
) -> None:
    """Atomically write an updated profile JSON.

    source_note shape:
      {
        "field": "contact.primary_phone",
        "source_form": "LOCC Intake Form",
        "source_form_path": "/path/to/form.pdf",  # or None
        "applied_by": "user via interview"
      }

    Rules:
    - Write to a temp file in the same directory, then os.replace() (atomic)
    - Update profile["last_updated"] to today's ISO date (YYYY-MM-DD)
    - Append source_note to profile["source_extraction_notes"] list
    - Never mutate profile_id, schema_version, or relationships array
    - Raises ValueError if updated_dict["profile_id"] != profile_id
    - Raises ValueError if schema_version changed
    - Raises ValueError if relationships array changed
    """
```

Profile JSON path is resolved via `lib/env.py` → `env.profiles_dir()` /
`{profile_id}.json`.

**Tests:** `tests/test_profile_writer.py`
- `test_write_updates_last_updated` — written profile has today's date
- `test_write_appends_source_note` — source_extraction_notes grows by 1
- `test_write_is_atomic` — simulate crash mid-write (mock os.replace to
  raise); original file must be unchanged
- `test_write_rejects_changed_profile_id` — ValueError raised
- `test_write_rejects_changed_schema_version` — ValueError raised
- `test_write_rejects_changed_relationships` — ValueError raised
- Use `tmp_path` fixture and a copy of a real profile for all write tests;
  never write to the live profiles directory in tests

---

## Issue #6 — STUB: Missing-data modes (skip → manual → interview)

**File:** `skills/form-autofill/autofill.py`

Add `--missing-mode skip|manual|interview` flag. Default: no mode (current
behaviour). Only activate when explicitly passed.

**Build in this order: skip first, manual second, interview third.**

### Mode A — skip (build first, ~30 lines)

After the dry-run, if `--missing-mode skip`:
1. Proceed to fill with only `high` and `medium` confidence fields
2. Remove any `low` or `none` confidence entries from `fill_data` before
   the commit call
3. Print a summary to stdout listing skipped field names and their
   confidence level
4. Write the output PDF (flatten is optional for now — leave editable)

### Mode B — manual (build second)

After the dry-run, if `--missing-mode manual`:
1. Fill only `high` and `medium` confidence fields (same as skip)
2. Leave form fields editable (do not flatten)
3. Write a sidecar file `<output_stem>.missing.md` alongside the output PDF:
   ```markdown
   # Manual fields for <form_name>
   The following fields could not be auto-filled:
   - [ ] Field "Patient Allergies" (confidence: none)
       Nearest profile field: none found
   - [ ] Field "Blood Type" (confidence: none)
       Nearest profile field: none found
   ```
4. Print location of both the output PDF and the sidecar file

### Mode C — interview (build third, depends on issue #7)

After the dry-run, if `--missing-mode interview`:
1. Group `none`-confidence fields by semantic section (identity / contact /
   insurance / school / emergency_contact / other — derive from the field's
   source or first path segment if partially matched)
2. Present 3–5 fields at a time, grouped by section:
   ```
   === Identity fields ===
   1. "Legal First Name" — no profile data found
      Enter value (or press Enter to skip):
   2. "Blood Type" — no profile data found
      Enter value (or press Enter to skip):
   ```
3. After user provides values, show a confirmation summary of what will be
   written
4. On confirmation:
   - Fill the PDF with all high/medium answers plus user-provided values
   - Call `lib/profile_writer.write_profile()` for each answered field,
     with `applied_by: "user via interview"` and the form path as
     `source_form_path`
5. Only write to profile AFTER user confirms the dry-run preview is correct
   (never mutate profile on abort)
6. If stdin is not a tty, exit 1 with message "interview mode requires
   interactive terminal"

**Tests:** `tests/test_dry_run.py` (extend existing file)
- `test_missing_mode_skip_exits_zero` — `--missing-mode skip` with
  synthetic form exits 0
- `test_missing_mode_skip_still_fills_confident_fields` — output JSON
  shows high-confidence fields filled
- `test_missing_mode_manual_writes_sidecar` — sidecar `.missing.md` exists
  alongside output PDF
- Do not test interactive stdin in pytest — note in file that interview mode
  requires manual testing

---

## Issue #8 — FEATURE: Round-trip extract → profile write-back

**File:** `skills/pdf-form-extraction/extract.py`

Add `--apply` flag. When passed, after extraction the user is shown each
proposed profile update and asked to confirm before writing.

**Algorithm:**
```
1. Run extraction as normal → candidate_delta
2. For each proposed update in candidate_delta["proposed_updates"]:
     print: Field "{field_label}" → profile path "{dot_path}"
            Current value: {current} | Extracted: {extracted}
     prompt: Apply? [Y]es / [N]o / [E]dit value
3. Collect accepted updates into a dict
4. Call lib/profile_writer.write_profile(profile_id, updated_profile, source_note)
   where source_note references the source PDF path and today's date
5. Print: "Profile {profile_id} updated. {n} fields written."
```

Notes:
- `--apply` requires `--target-profile` to be set; error clearly if not.
- If stdin is not a tty, exit 1 with a clear message.
- The write must be atomic (handled by `profile_writer`).
- `candidate_delta` is already produced by the existing extraction pipeline.
  This issue is purely the confirmation loop + write call.

**Tests:** `tests/test_extract_apply.py` (new file)
- `test_apply_requires_target_profile` — `--apply` without `--target-profile`
  exits non-zero with a clear error message
- Do not test interactive stdin; note it requires manual testing

---

## Issue #9 — STUB: Spatial overlay for flattened PDFs (optional this session)

**File:** `skills/form-autofill/overlay.py`

Only start this if #7, #6, and #8 are complete and tested.

**Current state:** File may exist as a stub raising `NotImplementedError`.

**What this does:** Fills PDFs that have no AcroForm fields (flattened or
pre-printed forms) by overlaying typed text at the correct coordinates,
derived from pdfplumber's spatial word map.

**Algorithm:**
1. Accept same args as `acroform.fill()`: `template_pdf`, `profile`,
   `index`, `output_pdf`, `dry_run`
2. Use pdfplumber to produce a spatial word map (list of
   `{text, x0, y0, x1, y1, page}` dicts) — `extract.py` already does
   this via `pdf_inspect.py`; reuse that logic
3. For each word cluster that looks like a field label (short phrase
   followed by whitespace or a line), call `map_pdf_field()` to get a
   candidate value
4. If a value is found, record a fill instruction:
   `{page, x, y, text, font_size}` — place text just to the right of or
   just below the label bounding box
5. In commit mode: use pypdf canvas to overlay the text at the recorded
   coordinates and write the output PDF
6. Return the same result dict shape as `acroform.fill()` for compatibility

**Key difficulty:** Label-to-blank-area detection on arbitrary layouts.
Start with the heuristic: "blank space of width ≥ 1 inch immediately to
the right of a label on the same line, or a blank line directly below."
This covers 80% of real form layouts.

**Tests:** `tests/test_overlay.py` (new file)
- `test_overlay_raises_on_acroform_pdf` — if the PDF has an AcroForm,
  raise ValueError with message "use acroform.fill() for AcroForm PDFs"
- `test_overlay_dry_run_returns_dict` — dry-run returns the standard
  result dict shape
- Full fill tests require a flattened fixture PDF; note if not available

---

## Sequence and acceptance

Work in this order: **#7 → #6 (skip, then manual, then interview) → #8 → #9 (if time)**

After each issue:
1. Run `/usr/bin/python3 -m pytest tests/ -q`
2. Confirm all prior tests still pass
3. Do not start the next issue if tests are red

Final acceptance: all tests pass, GitHub issues #6–#9 can be closed
(or #9 left open if deferred). Update this file with final test count.
