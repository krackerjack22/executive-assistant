# Handoff — Tier 1 & Tier 2 Issues (GitHub issues #1–#5)

Paste everything below into a fresh Claude Code session opened in
`/Users/tylercombs/Dev/executive-assistant`.

---

## What this project is

A personal executive-assistant CLI that fills blank AcroForm PDFs from
family profile JSON files. Two child skills:

- `skills/form-autofill/` — fills blank PDFs
- `skills/pdf-form-extraction/` — extracts field values from filled PDFs

Shared library lives in `lib/`. All personal data is in JSON files at
`~/Assets_Library/Executive-Assistant/profiles/` — **zero PII ever goes
in any `.py`, `.md`, or config file in the repo.**

---

## Current state

- **153 tests passing.** Run with `/usr/bin/python3 -m pytest tests/ -q`
- Python is `/usr/bin/python3` (3.9.6). Do NOT use `python3` — it links to
  a broken 3.14 install. Every file needs `from __future__ import annotations`
  for union-type syntax.
- pypdf 6.11.0, pdfplumber installed.
- Key skill files: `skills/form-autofill/field_mapper.py`,
  `acroform.py`, `autofill.py`, `formatters.py`, `emergency_contact.py`
- Synonym map: `skills/form-autofill/data/synonyms.json`
- Context rules: `skills/form-autofill/data/field_context_rules.json`

Read these files before touching anything:
1. `skills/form-autofill/field_mapper.py` — full field resolver
2. `skills/form-autofill/acroform.py` — AcroForm fill logic
3. `skills/form-autofill/autofill.py` — CLI entry point
4. `skills/form-autofill/data/field_context_rules.json` — usage constraints
5. `tests/test_field_mapper.py`, `tests/test_acroform_roundtrip.py`,
   `tests/test_dry_run.py` — existing test contracts

---

## Critical constraints (never violate)

- Zero PII in any `.py`, `.md`, or config file.
- Paths are env-var driven — never hardcode `/Users/tylercombs/...`.
  Use `lib/env.py` → `env.profiles_dir()`.
- Dry-run is default; `--commit` required to write files.
- All existing 153 tests must continue to pass after each issue.
- Use `/usr/bin/python3` for all test runs.

---

## Issue #1 — BUG: Multi-page AcroForm fill only writes page 0

**File:** `skills/form-autofill/acroform.py`

**Problem:** The fill function calls:
```python
writer.update_page_form_field_values(writer.pages[0], fill_data)
```
This silently skips all fields on pages 2+. Real forms span multiple pages.

**Fix:** pypdf's `update_page_form_field_values` can be called with each
page individually. Iterate over all pages:
```python
for page in writer.pages:
    writer.update_page_form_field_values(page, fill_data)
```
Verify this doesn't double-write fields that appear only on page 1 (pypdf
only writes fields it finds on that page — safe to iterate all).

**Test to add:** `tests/test_acroform_roundtrip.py` — add a test using the
existing `SYNTHETIC_PDF` fixture that asserts `filled_count > 0` after a
commit (regression guard). If you can create a 2-page fixture
(`tests/make_test_pdf.py` already exists — extend it), add a test that
fills fields on both pages.

---

## Issue #2 — BUG: field_context_rules.json never consulted

**File:** `skills/form-autofill/field_mapper.py`

**Problem:** `data/field_context_rules.json` defines usage constraints but
is never loaded. The critical rule: `tyler_combs.legal.trust_name`
("Tyler Combs Revocable Trust") must only be used when the field label
contains keywords like "trust", "grantor", "beneficiary", "entity name" —
never for patient name, subscriber name, or standard form fields.

**Fix:**
1. Load `field_context_rules.json` at module startup alongside synonyms
   (cache it like `_synonyms_cache`).
2. After the synonym lookup resolves a `(dot_path, value)` candidate,
   check whether that `dot_path` has a matching rule for the active
   `profile_id`. A rule matches when:
   - `rule["profile_id"]` matches the profile being filled
   - `rule["dot_path"]` matches the candidate's dot_path
3. If a rule exists, check `rule["keywords_that_permit_use"]` against the
   normalised field label (both `pdf_field_name` and `pdf_field_alt`).
   If none of the permit keywords appear in the label, **exclude that
   candidate** from `best_by_path` entirely (treat as score 0 / skip).
4. The profile dict is passed to `map_pdf_field` as `resolved_profile`.
   The profile's `profile_id` is at `resolved_profile.get("profile_id")`.

**Test to add:** `tests/test_field_mapper.py`
- `test_trust_name_excluded_for_patient_name` — field "patient name" with
  tyler profile must NOT return the trust name value.
- `test_trust_name_allowed_for_trust_field` — field "trust name" or
  "grantor name" with tyler profile should be able to return the trust value
  (confidence may be low — just assert the trust value is a candidate).

---

## Issue #3 — FEATURE: Radio/checkbox button field support

**Files:** `skills/form-autofill/acroform.py`,
`skills/form-autofill/field_mapper.py`

**Problem:** AcroForm `/Btn` fields (radio groups, checkboxes) are not
filled. Common on real forms: phone type (cell/home/work), gender
(male/female), yes/no checkboxes. The profile has
`contact.primary_phone_type = "cell"` and `identity.gender = "Female"`.

**Fix — acroform.py:**
1. In `_get_acroform_fields`, already reads `/FT`. For `/Btn` fields,
   also read the allowed on-values from `/AP` (appearance dict keys)
   or `/Opt`. Include them in the field dict as `"btn_values": [...]`.
2. In the `fill()` loop, when field type is `/Btn`, pass the mapped value
   directly to `update_page_form_field_values` — pypdf expects the on-value
   string (e.g., `"Yes"`, `"Cell"`, `"Female"`). Case must match exactly;
   use the `btn_values` list to find the correct casing.

**Fix — field_mapper.py:**
Add synonyms for button-type fields to `data/synonyms.json`:
```json
"phone type": "contact.primary_phone_type",
"cell home work": "contact.primary_phone_type"
```
The formatter does not need to change — the raw profile value (e.g. "cell")
will be compared case-insensitively against `btn_values` in acroform.py.

**Test to add:** `tests/test_acroform_roundtrip.py` — if the synthetic
fixture has any `/Btn` fields, assert they are correctly set. Otherwise add
a note; don't block the issue on fixture creation.

---

## Issue #4 — FEATURE: Context-sensitive field routing (PCP phone)

**Files:** `skills/form-autofill/field_mapper.py`,
`skills/form-autofill/acroform.py`

**Problem:** A field labeled "Phone" inside a PCP section of a form maps
to the patient's own phone instead of the physician's. Confirmed in the
LOCC 133-field intake form test. `field_mapper.py` scores all synonyms
against each field in isolation — no section context.

**Fix:**
1. **acroform.py `fill()` loop:** As fields are iterated, track whether
   recent field names contain PCP-section keywords: `{"physician",
   "doctor", "pcp", "provider", "practice", "clinic"}`. Normalise with
   the same `_normalize()` function used in field_mapper. Pass a
   `section_hint: str | None` to `map_pdf_field()` — value is
   `"pcp"` when in a PCP section, `None` otherwise. Reset to `None` when
   a non-PCP-adjacent field appears (after 3 consecutive non-PCP fields).

2. **field_mapper.py `map_pdf_field()`:** Add `section_hint: str | None = None`
   parameter. When `section_hint == "pcp"` and the field label is a generic
   term like "phone", "telephone", "fax", "name", "address":
   - Boost `external_entities.primary_care_physician.*` candidates by
     multiplying their score by 2.0 before comparison.
   - Suppress `contact.primary_phone` / `contact.work_phone` candidates
     by skipping them if a PCP candidate with score ≥ 0.3 exists.

3. Update `acroform.py`'s call to pass the hint:
   ```python
   fm_result = _fm.map_pdf_field(
       name, alt, profile, index,
       today=datetime.date.today(),
       section_hint=current_section_hint,
   )
   ```

**Test to add:** `tests/test_field_mapper.py`
- `test_pcp_phone_with_section_hint` — field "phone" with `section_hint="pcp"`
  should return the PCP phone, not the patient phone (use tyler profile which
  has a PCP phone).
- `test_phone_without_section_hint_returns_patient_phone` — same field, no
  hint, returns patient phone.

---

## Issue #5 — STUB: `--resolve` interactive flow

**File:** `skills/form-autofill/autofill.py`

**Current stub:**
```python
if args.resolve:
    print("--resolve: v1.5 feature not yet implemented")
    sys.exit(0)
```

**Fix:** Replace the stub with a real interactive loop. The dry-run result
is already computed before this check runs — use it.

**Algorithm (from MVP_CONTRACT_addendum_2.md, Part B):**
```
for each field in dry_result["fields"] where confidence == "low":
    print: Field "{name}" — suggested: "{mapped_value}" via {source}
    if alternatives exist: print each with its score
    prompt: [Y]es / [N]o pick alternative / [E]nter value / [S]kip
    
    Y → keep mapped_value
    N → show numbered list of alternatives, prompt pick
    E → read raw input from stdin, use as value
    S → set value to None (leave blank)

After all low fields resolved, re-build fill_data with user answers
and call acroform.fill(..., dry_run=False)
```

Implementation notes:
- Run this block only after the dry-run is complete and
  `dry_result["low_count"] > 0`.
- If `low_count == 0`, print "No low-confidence fields — committing
  directly." and go straight to commit.
- The field results list is already in `dry_result["fields"]`.
  Mutate `mapped_value` in place before the commit fill call, or build
  a separate override dict.
- stdin interaction: use `input()`. If stdin is not a tty (piped),
  skip the loop and error with a message.

**Tests to add:** `tests/test_dry_run.py`
- `test_resolve_with_no_low_fields_commits_directly` — use synthetic form
  (zero low fields), `--resolve` should exit 0 and write the file.
- Do not try to test the interactive stdin prompts in pytest — mark those
  paths as requiring manual testing and note it in the test file.

---

## Sequence and acceptance

Work issues in order: #1 → #2 → #3 → #4 → #5.

After each issue:
1. Run `/usr/bin/python3 -m pytest tests/ -q`
2. Confirm all prior tests still pass plus any new ones
3. Do not move to the next issue if tests are red

Final acceptance: all 153+ tests pass, GitHub issues #1–#5 can be closed.
Update this file with the final test count when done.
