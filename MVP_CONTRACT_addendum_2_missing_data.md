# MVP_CONTRACT — Addendum 2: Missing-data handling & field-mapping confidence

**How to apply:** Two parts.
- **Part A (v1)** — paste into your saved `MVP_CONTRACT.md` immediately before `## Acceptance criteria (v1 done)`, after the Preflight section. Also append the listed acceptance items to the existing checklist.
- **Part B (v1.5)** — paste into the same file but in a new section titled `## v1.5 deferred features` (create the section if it doesn't exist). v1.5 is post-MVP; Sonnet does NOT build it now.

---

## Part A — v1 additions (build during MVP)

### Field-mapping confidence & alternatives

The `field_mapper.map_pdf_field()` return shape is expanded from `(value, source_explanation)` to a structured dict so the dry-run preview can render confidence and the LLM agent can decide when to ask the user.

**Updated signature:**

```python
def map_pdf_field(pdf_field_name: str, pdf_field_alt: str,
                  resolved_profile: dict, index: dict) -> dict:
    """Returns a result dict (never None). Empty/missing values are still
    represented in the result with confidence='none'."""
```

**Return shape (stable contract):**

```json
{
  "pdf_field_name": "Subscribers Name",
  "pdf_field_alt": "Subscribers Name",
  "value": "Tyler Combs",
  "confidence": "high",
  "source": "insurance.primary.subscriber_profile_id -> tyler_combs.identity.legal_name",
  "alternatives": [],
  "notes": []
}
```

**Confidence tiers (stable):**

| Tier | Meaning | Dry-run treatment | LLM action |
|---|---|---|---|
| `high` | Exact synonym match OR direct profile field present | Auto-fill, show value | None |
| `medium` | Synonym match with one plausible alternative, OR resolved via relationship walk | Auto-fill, but list alternatives | Mention briefly in chat; proceed unless user objects |
| `low` | Multiple plausible mappings OR weak synonym match | Fill, flag clearly | Ask user to confirm before commit |
| `none` | No mapping found, field will be empty | Show as missing, list what's needed | Defer to v1.5 missing-data modes; in v1, ask user inline if critical |

**`alternatives[]` shape:** when confidence is medium/low, each entry is:

```json
{
  "candidate_value": "Madeline Miller",
  "candidate_source": "external_persons.mother -> Lynsee Combs (or partner.legal_name -> Madeline Miller)",
  "score": 0.6
}
```

**`notes[]` shape:** free-text hints surfaced in dry-run (e.g., `"Field appears in 'Responsible Party' section; subscriber inheritance applied"`).

### Dry-run preview rendering

`autofill.py --dry-run` output is a structured dict (JSON to stdout; `--human` for table format). For each fillable field:

```
y=552  CONFIDENT  [ID]                      = "O2F 240272015"
                  via insurance.primary.member_id

y=636  ASK        [Printed Name]            = "Tyler Combs"
                  via identity.legal_name
                  ALT: "Madeline Miller" (external_persons.partner) score=0.4

y=675  MISSING    [Client Printed Name]     = (none)
                  no mapping found; nearest profile field: identity.legal_name (but already used for "Printed Name")
```

The autofill CLI never auto-commits when any field is `low` confidence — requires `--commit-unsafe` flag OR a `--resolve` interactive prompt (v1.5).

### Acceptance items to append

- [ ] `map_pdf_field()` returns the new dict shape with all 6 keys present
- [ ] `confidence` tier is one of `high|medium|low|none` only
- [ ] Dry-run output includes a confidence indicator per field
- [ ] Running autofill against Tyler_Med_Data.pdf with Tyler's profile yields zero `low` and zero `none` for the 33 originally-populated fields
- [ ] CLI refuses to `--commit` if any field is `low`; suggests `--commit-unsafe` or `--resolve` (the latter is v1.5 stub)

---

## Part B — v1.5 deferred features (do NOT build in MVP)

### Missing-data handling: interview / manual / skip modes

When autofill finishes mapping and finds any `confidence: none` fields (or any `low` if user requests strict mode), the CLI offers three routing modes:

#### Mode A — Interview (default if no flag)

1. Group missing fields by semantic section (identity / contact / insurance / school / emergency_contact / etc.)
2. Batch questions to minimize round-trips: present 3-5 related fields at a time
3. Validate types as user answers (phone format, date format, email format)
4. Persist answers back to the relevant profile JSON file (updates `last_updated`, appends a `source_extraction_notes` entry referencing the form name)
5. Re-run autofill with the augmented profile data
6. Proceed to dry-run preview as normal

**Persistence rule:** answers are saved to the profile JSON *only after* the user confirms the dry-run preview is correct. If user aborts, no profile data is mutated.

#### Mode B — Manual (PDF for human completion)

1. Fill all `high` and `medium`-confidence fields
2. Do NOT flatten the PDF — preserve form fields so blanks remain editable
3. Output a sidecar markdown checklist named `<output>.missing.md`:
   ```
   # Manual fields for <form_name>
   The following fields could not be auto-filled:
   - [ ] Field "Patient Allergies" (no profile data)
       Profile field that would store this: external_entities.allergies (new)
   - [ ] Field "Blood Type" (no profile data)
       Profile field that would store this: identity.blood_type (new)
   ```
4. After user manually completes the PDF, optional follow-up: `extract.py` can be run on the completed PDF to harvest the manually-entered values back into the profile (closing the loop with v1's extraction skill)

#### Mode C — Skip (best-effort fill, flatten)

1. Fill all `high` and `medium`-confidence fields
2. Leave `low` and `none` fields empty
3. Flatten output PDF
4. Print summary of skipped fields to stdout (not a sidecar file)

**CLI flag:** `--missing-mode interview|manual|skip` (default: `interview`).

### Ambiguity resolution flow (low-confidence fields)

For `confidence: low` fields, an `--resolve` interactive flag triggers structured questioning:

1. For each low-confidence field, present the question:
   ```
   Field "Father's Name" on this form.
   I would fill: "Tyler Combs" (via fiona_combs.relationships -> father)
   Alternative: "<other plausible candidate>"
   
   Use Tyler Combs? [Y]es / [N]o → pick alternative / [E]nter different value / [S]kip
   ```
2. Capture answer, update the field result
3. If user picks an alternative, optionally update synonyms.json to learn the mapping for next time (with user confirmation)
4. After all low-confidence fields resolved, proceed to commit

### Profile-write-back safety

All v1.5 modes that modify profile JSONs must:
- Write to a temp file first, then atomic rename
- Update `last_updated` timestamp
- Append a `source_extraction_notes` entry: `{field, source_form, source_form_path, applied_by: "user via interview/manual/resolve"}`
- Never mutate `profile_id`, `schema_version`, or `relationships` array (those are user-controlled)

### v1.5 deferred features list (consolidated)

- Spatial-overlay fill for flattened PDFs (already specified in the original contract)
- Missing-data modes (interview / manual / skip) — this section
- Low-confidence field resolution loop (`--resolve`) — this section
- Synonyms.json learning from user answers
- Round-trip closure: `extract.py` re-ingests a manually-completed PDF to update profile

### Acceptance items for v1.5 (defer, do NOT verify during MVP build)

- [ ] All three missing-data modes selectable via CLI flag
- [ ] Interview mode batches questions ≥3 per round
- [ ] Manual mode output PDF passes pypdf field-fillable test (fields remain interactive)
- [ ] Profile write-back is atomic (temp + rename pattern)
- [ ] `--resolve` flow handles each low-confidence field once, no infinite loops on user "N" answers
- [ ] Spatial overlay implemented (cross-references original contract's v1.5 section)
