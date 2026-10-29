# Graph Report - .  (2026-08-20)

## Corpus Check
- 92 files · ~61,166 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 165 nodes · 207 edges · 36 communities (16 shown, 20 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 5 edges (avg confidence: 0.76)
- Token cost: 6,731 input · 10,423 output

## Community Hubs (Navigation)
- Profile Loader Module
- Form Autofill Module
- Acroform Skills Module
- Form Skills Module
- Skills Skill Module
- Field Skills Module
- Field Skills Module
- Skills Form Module
- Calendar Agent Module
- Calendar Agent Module
- Field Skills Module
- Skills Form Module
- Agents File Module
- Agents Graphify Module
- Tests Entry Module
- Skills Form Module
- Skills Form Module
- Skills Form Module
- Field Skills Module
- Field Skills Module
- Skills Form Module
- Agents Temporary Module
- Browser Module
- Calendar Integration Module
- Graphify Tool Module
- Langchain Google Module
- Playwright Module
- Readme Module
- Calendar Skills Module
- Calendar Skills Module
- Calendar Skills Module
- Skills Summer Module
- Summer Skills Module

## God Nodes (most connected - your core abstractions)
1. `map_pdf_field()` - 30 edges
2. `pdf-form-autofill Skill` - 13 edges
3. `_make_result()` - 11 edges
4. `_resolve_and_format()` - 8 edges
5. `review_fills()` - 7 edges
6. `load_index()` - 6 edges
7. `load_profile()` - 6 edges
8. `fill()` - 6 edges
9. `_profiles_path()` - 5 edges
10. `_get_acroform_fields()` - 5 edges

## Surprising Connections (you probably didn't know these)
- `pdf-form-autofill Skill` --processes--> `Flattened Form PDF`  [INFERRED]
  skills/pdf-form-autofill/SKILL.md → tests/fixtures/flattened_form.pdf
- `pdf-form-autofill Skill` --generates--> `W-9 Tyler Combs Filled QA Screenshot`  [INFERRED]
  skills/pdf-form-autofill/SKILL.md → .tmp/qa_debug_W-9_TylerCombs_Filled_QA.pdf.png
- `Executive Assistant Master Skill` --references--> `Child Skills Registry`  [EXTRACTED]
  SKILL.md → child-skills.md
- `Web Form Autofill` --shares_data_with--> `Personal Assets Library`  [INFERRED]
  skills/web-form-autofill/SKILL.md → SKILL.md
- `Add2Calendar` --calls--> `Google Calendar Integration`  [INFERRED]
  skills/Add2Calendar/SKILL.md → SKILL.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Executive Assistant Orchestration Flow** — skill, child_skills, assets_library [EXTRACTED 1.00]
- **Form Processing Suite** — skills_pdf_form_extraction_skill, skills_pdf_form_autofill_skill, skills_web_form_autofill_skill [INFERRED 0.90]
- **Calendar Agent Workflow** — skills_add2calendar_references_calendar_agent_sop_pdf_calendar_agent, skills_add2calendar_references_calendar_agent_sop_pdf_event_extraction, skills_add2calendar_references_calendar_agent_sop_pdf_geocode_locations, skills_add2calendar_references_calendar_agent_sop_pdf_event_preview, skills_add2calendar_references_calendar_agent_sop_pdf_event_creation [EXTRACTED 1.00]
- **XC Calendar Agent Workflow** — skills_add2calendar_references_xc_calendar_agent_instructions_pdf_xc_calendar_agent, skills_add2calendar_references_xc_calendar_agent_instructions_pdf_file_intake_recognition, skills_add2calendar_references_xc_calendar_agent_instructions_pdf_event_extraction, skills_add2calendar_references_xc_calendar_agent_instructions_pdf_address_verification, skills_add2calendar_references_xc_calendar_agent_instructions_pdf_table_preview, skills_add2calendar_references_xc_calendar_agent_instructions_pdf_event_creation_rules [EXTRACTED 1.00]
- **PDF Form Autofill Workflow** — skills_pdf_form_autofill_skill_pdf_form_autofill, skills_pdf_form_autofill_skill_check_env, skills_pdf_form_autofill_skill_dry_run_preview, skills_pdf_form_autofill_skill_profile_null_check, skills_pdf_form_autofill_skill_vault_check, skills_pdf_form_autofill_skill_commit [EXTRACTED 1.00]

## Communities (36 total, 20 thin omitted)

### Community 0 - "Profile Loader Module"
Cohesion: 0.16
Nodes (18): list_profiles(), _load_all_raws(), load_index(), load_profile(), _load_raw(), _profiles_path(), Path, Load and resolve profile JSON files with inheritance expansion. (+10 more)

### Community 1 - "Form Autofill Module"
Cohesion: 0.13
Nodes (16): AskUserQuestion Tool Call, bw unlock command, Check Environment, Commit Operation, Dry-run Preview, form-autofill.py script, lib.profile_loader, overlay.py script (+8 more)

### Community 2 - "Acroform Skills Module"
Cohesion: 0.21
Nodes (12): DictionaryObject, PdfReader, fill(), _get_acroform_fields(), _get_btn_values(), _normalize_section(), Path, Fill AcroForm PDFs using pypdf. (+4 more)

### Community 3 - "Form Skills Module"
Cohesion: 0.22
Nodes (12): _build_prompt(), extract_form_text(), _parse_issues(), _profile_summary(), Path, LLM-powered quality-assurance review of a form-fill proposal.  Sends the fill pr, Call Claude to review the fill proposal for contextual errors.      Args:, Extract the issues list from the model's JSON response. (+4 more)

### Community 4 - "Skills Skill Module"
Cohesion: 0.17
Nodes (12): Personal Assets Library, Child Skills Registry, Google Calendar Integration, Executive Assistant Master Skill, Calendar Integration Logic, Add2Calendar, Campsite Availability Tracker, Campsite Hunter (+4 more)

### Community 5 - "Field Skills Module"
Cohesion: 0.26
Nodes (12): date, _make_result(), Resolve a dot-path from the profile and apply value formatting., Return the first sibling's data for the requested subfield., _resolve_and_format(), _resolve_combined_csz(), _resolve_emergency_contact(), _resolve_language_field() (+4 more)

### Community 6 - "Field Skills Module"
Cohesion: 0.17
Nodes (12): _is_language_field(), _is_mailing_if_different(), _is_parent_name_field(), _is_printed_name_field(), _is_sibling_field(), map_pdf_field(), True when the field asks for mailing address only if it differs from home., True when the field asks for parent/guardian printed name. (+4 more)

### Community 7 - "Skills Form Module"
Cohesion: 0.22
Nodes (9): _is_permitted_by_context(), _load_context_rules(), _load_synonyms(), _normalize(), Map PDF field names/alt text to resolved profile values via synonym lookup., Lowercase, strip non-alpha/digit/space, collapse whitespace., Score how well a synonym token matches a normalised field label.      Returns 1., Return False when a context rule blocks this dot_path for the given field label. (+1 more)

### Community 8 - "Calendar Agent Module"
Cohesion: 0.25
Nodes (8): Address Verification (XC), Event Creation Rules (XC), Event Extraction (XC), File Intake and Recognition, Google Calendar 'Charlotte and Fiona', Google Maps (XC), Table Preview Before Import (XC), XC Calendar Agent

### Community 9 - "Calendar Agent Module"
Cohesion: 0.29
Nodes (7): Calendar Agent, Event Creation, Event Information Extraction, Event Preview, Geocode Locations, Google Calendar, Google Maps

### Community 10 - "Field Skills Module"
Cohesion: 0.50
Nodes (4): _is_signature_date(), _is_signature_or_initials_field(), True when the field is a signature-adjacent date (not a DOB or named date)., Detect if field is for signature or initials, and return (type, value, confidenc

### Community 11 - "Skills Form Module"
Cohesion: 0.33
Nodes (4): Return 'skip' result when mailing == home address., Fill race/ethnicity checkboxes from demographics.race / demographics.ethnicity_h, _resolve_mailing_if_different(), _resolve_race_ethnicity()

### Community 12 - "Agents File Module"
Cohesion: 0.67
Nodes (3): .env file, Environment Variables & API Keys, GEMINI_API_KEY

## Knowledge Gaps
- **44 isolated node(s):** `run_all_tests.sh script`, `Graphify Tool`, `Executive Assistant README`, `Google Calendar Integration`, `browser-use` (+39 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **20 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `map_pdf_field()` connect `Field Skills Module` to `Field Skills Module`, `Skills Form Module`, `Field Skills Module`, `Skills Form Module`, `Skills Form Module`, `Skills Form Module`, `Field Skills Module`, `Field Skills Module`, `Skills Form Module`?**
  _High betweenness centrality (0.044) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `pdf-form-autofill Skill` (e.g. with `Flattened Form PDF` and `W-9 Tyler Combs Filled QA Screenshot`) actually correct?**
  _`pdf-form-autofill Skill` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Load and resolve profile JSON files with inheritance expansion.`, `Load profiles_index.json.`, `Return minimal {profile_id, legal_name, status} per registered profile.` to the rest of the system?**
  _85 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Form Autofill Module` be split into smaller, more focused modules?**
  _Cohesion score 0.13333333333333333 - nodes in this community are weakly interconnected._