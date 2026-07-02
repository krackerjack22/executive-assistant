# Graph Report - /Users/tylercombs/Dev/skills/executive-assistant  (2026-07-02)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 749 nodes · 1088 edges · 49 communities (33 shown, 16 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 9 edges (avg confidence: 0.81)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `e90ff171`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_field_mapper.py|field_mapper.py]]
- [[_COMMUNITY_profile_loader.py|profile_loader.py]]
- [[_COMMUNITY_test_formatters.py|test_formatters.py]]
- [[_COMMUNITY_test_learning.py|test_learning.py]]
- [[_COMMUNITY_test_acroform_roundtrip.py|test_acroform_roundtrip.py]]
- [[_COMMUNITY_preflight.py|preflight.py]]
- [[_COMMUNITY_test_overlay.py|test_overlay.py]]
- [[_COMMUNITY_test_dry_run.py|test_dry_run.py]]
- [[_COMMUNITY_test_qa_reviewer.py|test_qa_reviewer.py]]
- [[_COMMUNITY__index|_index]]
- [[_COMMUNITY_test_preflight.py|test_preflight.py]]
- [[_COMMUNITY_test_vault.py|test_vault.py]]
- [[_COMMUNITY_acroform.py|acroform.py]]
- [[_COMMUNITY_autofill.py|autofill.py]]
- [[_COMMUNITY_test_address_resolver.py|test_address_resolver.py]]
- [[_COMMUNITY_vault.py|vault.py]]
- [[_COMMUNITY_test_emergency_contact.py|test_emergency_contact.py]]
- [[_COMMUNITY_test_field_mapper.py|test_field_mapper.py]]
- [[_COMMUNITY_test_env.py|test_env.py]]
- [[_COMMUNITY_Child Skills Registry|Child Skills Registry]]
- [[_COMMUNITY_review_fills|review_fills]]
- [[_COMMUNITY_test_profile_loader.py|test_profile_loader.py]]
- [[_COMMUNITY_test_profile_writer.py|test_profile_writer.py]]
- [[_COMMUNITY_pdf_inspect.py|pdf_inspect.py]]
- [[_COMMUNITY__profile_with_siblings|_profile_with_siblings]]
- [[_COMMUNITY__make_synonyms_with_learned|_make_synonyms_with_learned]]
- [[_COMMUNITY_test_extract_apply.py|test_extract_apply.py]]
- [[_COMMUNITY__tyler_with_vault_ref|_tyler_with_vault_ref]]
- [[_COMMUNITY__tyler_no_email|_tyler_no_email]]
- [[_COMMUNITY_schema_builder.py|schema_builder.py]]
- [[_COMMUNITY_make_flattened_form|make_flattened_form]]
- [[_COMMUNITY_conftest.py|conftest.py]]
- [[_COMMUNITY_test_phone_email_is_low|test_phone_email_is_low]]
- [[_COMMUNITY_test_trust_name_allowed_for_trust_field|test_trust_name_allowed_for_trust_field]]
- [[_COMMUNITY_test_trust_name_excluded_for_subscriber_name|test_trust_name_excluded_for_subscriber_name]]
- [[_COMMUNITY_test_pcp_phone_with_section_hint|test_pcp_phone_with_section_hint]]
- [[_COMMUNITY_test_phone_without_section_hint_returns_patient_phone|test_phone_without_section_hint_returns_patient_phone]]
- [[_COMMUNITY_test_source_explanation_present_all_fields|test_source_explanation_present_all_fields]]
- [[_COMMUNITY_test_vietnamese_does_not_match_legal_name|test_vietnamese_does_not_match_legal_name]]
- [[_COMMUNITY_test_city_does_not_match_electricity|test_city_does_not_match_electricity]]
- [[_COMMUNITY_test_name_still_matches_patient_name|test_name_still_matches_patient_name]]
- [[_COMMUNITY_test_street_still_returned_for_address_field|test_street_still_returned_for_address_field]]
- [[_COMMUNITY_test_universal_context_rule_applies_to_non_tyler_profile|test_universal_context_rule_applies_to_non_tyler_profile]]
- [[_COMMUNITY_test_email_filled_when_contact_email_present|test_email_filled_when_contact_email_present]]
- [[_COMMUNITY_test_address_not_returned_for_employer_address|test_address_not_returned_for_employer_address]]
- [[_COMMUNITY_test_alternative_shape|test_alternative_shape]]
- [[_COMMUNITY_Executive Assistant README|Executive Assistant README]]

## God Nodes (most connected - your core abstractions)
1. `_index()` - 61 edges
2. `_tyler()` - 42 edges
3. `map_pdf_field()` - 25 edges
4. `_profile()` - 17 edges
5. `_index()` - 17 edges
6. `_run_interview_mode()` - 9 edges
7. `_make_result()` - 9 edges
8. `TestBuildPrompt` - 9 edges
9. `_load_all_profiles()` - 9 edges
10. `run()` - 8 edges

## Surprising Connections (you probably didn't know these)
- `test_minimum_token_length_guard_exact_two_chars()` --calls--> `_score_match()`  [INFERRED]
  tests/test_field_mapper.py → skills/pdf-form-autofill/field_mapper.py
- `test_minimum_token_length_guard_two_char_token()` --calls--> `_score_match()`  [INFERRED]
  tests/test_field_mapper.py → skills/pdf-form-autofill/field_mapper.py
- `test_three_char_token_still_uses_boundary_matching()` --calls--> `_score_match()`  [INFERRED]
  tests/test_field_mapper.py → skills/pdf-form-autofill/field_mapper.py
- `Executive Assistant Master Skill` --references--> `Child Skills Registry`  [EXTRACTED]
  SKILL.md → child-skills.md
- `Child Skills Registry` --references--> `Campsite Hunter`  [EXTRACTED]
  child-skills.md → skills/campsite-hunter/SKILL.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Executive Assistant Orchestration Flow** — skill, child_skills, assets_library [EXTRACTED 1.00]
- **Form Processing Suite** — skills_pdf_form_extraction_skill, skills_pdf_form_autofill_skill, skills_web_form_autofill_skill [INFERRED 0.90]

## Communities (49 total, 16 thin omitted)

### Community 0 - "field_mapper.py"
Cohesion: 0.07
Nodes (51): clear_synonyms_cache(), _determine_confidence(), _is_combined_city_state_zip(), _is_emergency_contact_field(), _is_language_field(), _is_mailing_if_different(), _is_permitted_by_context(), _is_race_ethnicity_field() (+43 more)

### Community 1 - "profile_loader.py"
Cohesion: 0.06
Nodes (43): list_profiles(), _load_all_raws(), load_index(), load_profile(), _load_raw(), _profiles_path(), Path, Load and resolve profile JSON files with inheritance expansion. (+35 more)

### Community 2 - "test_formatters.py"
Cohesion: 0.05
Nodes (16): get_emergency_contact(), Resolve emergency contact data from a profile's emergency_contacts list., Return emergency contact info for the given priority (1=primary, 2=secondary)., apply_format(), format_date(), format_grade(), format_phone(), format_today() (+8 more)

### Community 3 - "test_learning.py"
Cohesion: 0.05
Nodes (25): build_entry(), derive_token(), _is_human_readable(), is_pollution_candidate(), _normalize(), Path, Synonym learning: derive tokens from PDF field labels and persist to synonyms.js, Lowercase, strip non-alpha/digit/space, collapse whitespace. (+17 more)

### Community 4 - "test_acroform_roundtrip.py"
Cohesion: 0.05
Nodes (24): Round-trip test: fill synthetic_form.pdf with Tyler's profile, verify populated, Tyler's profile → synthetic form: no field should be low confidence., Each field result dict must include alternatives (may be empty list)., ambiguous_form.pdf has 'phone email' → low confidence → low_count >= 1., The 'phone email' field in ambiguous_form.pdf must be low confidence., Patient name in ambiguous form still maps correctly., /Btn gender field in btn_form.pdf maps to the correct gender value., /Btn form fills and commits without error. (+16 more)

### Community 5 - "preflight.py"
Cohesion: 0.08
Nodes (34): config(), profiles_dir(), profiles_dir_source(), Path, Env-var resolution and path canonicalization for executive-assistant., Return resolved absolute Path to profiles directory.      Resolution order: EXEC, Return 'env_var' or 'default' depending on which resolution path is used., Load optional config.json. Returns {} if file missing or unreadable. Never raise (+26 more)

### Community 6 - "test_overlay.py"
Cohesion: 0.06
Nodes (34): _detect_label(), fill(), _group_into_lines(), Path, Spatial overlay fill for flattened (non-AcroForm) PDFs., Cluster words into text lines by top-edge proximity., Fill a flattened (non-AcroForm) PDF by overlaying typed text at label positions., Return label metadata if the line contains a colon-terminated label.      Looks (+26 more)

### Community 7 - "test_dry_run.py"
Cohesion: 0.05
Nodes (33): Test dry-run behavior, commit refusal, --commit-unsafe bypass, and --resolve stu, CLI dry-run JSON output includes low_count key., CLI --commit writes the output file when no low-confidence fields exist., --commit JSON output has mode=filled., --commit exits 1 when ambiguous_form.pdf has a low-confidence field., Refusal message hints at --commit-unsafe., --commit-unsafe writes the file even when low-confidence fields are present., --commit-unsafe JSON output shows mode=filled. (+25 more)

### Community 8 - "test_qa_reviewer.py"
Cohesion: 0.06
Nodes (9): _make_field(), Tests for qa_reviewer.py — prompt building, JSON parsing, API error handling., TestBuildPrompt, TestExtractFormText, TestParseIssues, TestProfileSummary, TestReviewFillsMissingKey, TestReviewFillsMockedApi (+1 more)

### Community 9 - "_index"
Cohesion: 0.12
Nodes (30): _index(), insurance company' is exact for the carrier, but 'company' also matches employer, legal.trust_name must never appear as the result for a patient name field., test_alternatives_is_list(), test_city_high(), test_confidence_is_valid_tier(), test_dob_high(), test_email_matched() (+22 more)

### Community 10 - "test_preflight.py"
Cohesion: 0.07
Nodes (29): Tests for lib/preflight.py., Preflight must complete in under 500ms on a warm filesystem., --check-env exits 0 and prints ok=true JSON when env is valid., --check-env exits 1 with PROFILES_DIR_MISSING when dir doesn't exist., --check-env exits 1 with PROFILES_INDEX_MISSING when index is absent., Preflight passes with a valid environment., Warning BW_SESSION_NOT_SET appears when bw binary exists but BW_SESSION is absen, No BW_SESSION_NOT_SET warning when bw binary is not installed. (+21 more)

### Community 11 - "test_vault.py"
Cohesion: 0.07
Nodes (5): _clear_vault_cache(), Tests for lib/vault.py — Bitwarden CLI integration., Two get() calls with same item name → only one subprocess invocation., Reset the per-process cache before each test., test_cached_bw_call_invokes_subprocess_once()

### Community 12 - "acroform.py"
Cohesion: 0.11
Nodes (24): DictionaryObject, PdfReader, fill(), _get_acroform_fields(), _get_btn_values(), _normalize_section(), Path, Fill AcroForm PDFs using pypdf. (+16 more)

### Community 13 - "autofill.py"
Cohesion: 0.16
Nodes (24): _collect_batch(), _dot_path_from_source(), _field_section(), _fill_pdf(), main(), _offer_learning(), Path, Interactive resolution of low-confidence fields, then commit. (+16 more)

### Community 14 - "test_address_resolver.py"
Cohesion: 0.11
Nodes (14): is_subject_address(), Render addresses in various formats and detect subject-vs-third-party fields., Render an address dict in the requested format.      Args:         address: dict, Return True if the field label refers to the profile holder's address.      Cons, render(), _index(), Tests for lib/address_resolver.py — all 5 formats + subject detection., test_is_not_subject_employer_office() (+6 more)

### Community 15 - "vault.py"
Cohesion: 0.16
Nodes (20): Exception, _cached_bw_call(), clear_cache(), _extract_field(), get(), is_available(), Bitwarden CLI integration for vault-backed profile fields., Subprocess call to bw, cached per item_name within this process. (+12 more)

### Community 16 - "test_emergency_contact.py"
Cohesion: 0.25
Nodes (19): _index(), _profile(), Tests for skills/form-autofill/emergency_contact.py, test_charlotte_ec_priority1_is_tyler(), test_charlotte_ec_priority1_phone(), test_charlotte_ec_priority1_relationship(), test_charlotte_ec_priority2_is_lynsee(), test_charlotte_ec_priority2_relationship() (+11 more)

### Community 17 - "test_field_mapper.py"
Cohesion: 0.20
Nodes (14): _charlotte_profile(), _demographics_profile(), Tests for field_mapper.py — dict return shape, confidence tiers, synonym resolut, test_ethnicity_hispanic_false_returns_no(), test_ethnicity_hispanic_true_returns_yes(), test_guardian_email_resolved_for_student(), test_guardian_phone_resolved_for_student(), test_language_first_field() (+6 more)

### Community 18 - "test_env.py"
Cohesion: 0.14
Nodes (14): Tests for lib/env.py — env-var resolution, default fallback, missing-dir error., Default path should resolve to an existing directory (symlink or real)., EXEC_ASSISTANT_PROFILES_DIR env var should override the default., FileNotFoundError with actionable message when dir doesn't exist., profiles_dir_source returns 'env_var' when env var is set., config() returns {} when config file is absent. Never raises., CLI (via preflight) exits non-zero with actionable message when profiles dir mis, test_cli_exits_nonzero_on_missing_dir() (+6 more)

### Community 19 - "Child Skills Registry"
Cohesion: 0.17
Nodes (13): Personal Assets Library, Child Skills Registry, Google Calendar Integration, Executive Assistant Master Skill, Calendar Integration Logic, Add2Calendar, Campsite Availability Tracker, Campsite Hunter (+5 more)

### Community 20 - "review_fills"
Cohesion: 0.22
Nodes (12): _build_prompt(), extract_form_text(), _parse_issues(), _profile_summary(), Path, LLM-powered quality-assurance review of a form-fill proposal.  Sends the fill pr, Call Claude to review the fill proposal for contextual errors.      Args:, Extract the issues list from the model's JSON response. (+4 more)

### Community 21 - "test_profile_loader.py"
Cohesion: 0.15
Nodes (5): Tests for lib/profile_loader.py — load all 5 profiles, verify inheritance., Fiona's addresses.home = {same_as_profile: tyler_combs} → Tyler's home address., Fiona's insurance inherits from Tyler as subscriber., test_load_fiona_address_inherits_tyler(), test_load_fiona_insurance_inherits_tyler()

### Community 22 - "test_profile_writer.py"
Cohesion: 0.37
Nodes (12): _load(), patch_profiles_dir(), profile_dir(), Path, Tests for lib/profile_writer.write_profile()., test_write_appends_source_note(), test_write_is_atomic(), test_write_rejects_changed_profile_id() (+4 more)

### Community 23 - "pdf_inspect.py"
Cohesion: 0.24
Nodes (10): get_acroform_fields(), get_page_count(), get_spatial_map(), has_acroform(), Path, pypdf + pdfplumber helpers for PDF field inspection., Extract all AcroForm fields from a PDF using pypdf.      Returns a list of dicts, Return True if the PDF contains an AcroForm. (+2 more)

### Community 24 - "_profile_with_siblings"
Cohesion: 0.25
Nodes (8): _profile_with_siblings(), Profile with a siblings array for testing the sibling resolver., Resolver skips siblings whose subfield is null and returns the first non-null va, test_sibling_first_name_resolved(), test_sibling_grade_resolved(), test_sibling_last_name_resolved(), test_sibling_school_resolved(), test_sibling_skips_null_subfield_to_next()

### Community 25 - "_make_synonyms_with_learned"
Cohesion: 0.29
Nodes (7): _make_synonyms_with_learned(), Path, Write a minimal synonyms.json with a learned section to tmp_path., Loader reads a learned entry with {'dot_path': ...} shape and maps it correctly., Learned entry with same token as curated → loader picks learned; warning emitted, test_loader_learned_overrides_curated(), test_loader_reads_learned_dict_shape()

### Community 26 - "test_extract_apply.py"
Cohesion: 0.33
Nodes (5): Tests for extract.py --apply flag., --apply without --target-profile exits non-zero with a clear error message., --apply with --target-profile exits 1 when stdin is not a tty., test_apply_exits_on_non_tty(), test_apply_requires_target_profile()

### Community 27 - "_tyler_with_vault_ref"
Cohesion: 0.33
Nodes (6): Load tyler profile and inject a non-null vault_references.ssn pointer., vault_references.ssn with locked vault → confidence='none', note mentions vault, vault_references.ssn with unlocked vault → value returned, confidence='high'., test_vault_reference_with_locked_vault_returns_none_with_note(), test_vault_reference_with_unlocked_vault_returns_value(), _tyler_with_vault_ref()

### Community 28 - "_tyler_no_email"
Cohesion: 0.33
Nodes (6): Tyler profile with contact.email set to None to simulate missing email., addresses.home.street_1 must be blocked when 'email' appears in the field label., Universal block rule covers any label containing 'email', not just exact match., test_street_not_returned_for_email_address_field(), test_street_not_returned_for_student_email_field(), _tyler_no_email()

### Community 29 - "schema_builder.py"
Cohesion: 0.50
Nodes (4): _build_prompt(), generate_schema_mapping(), LLM-powered schema mapping for entirely new fields., Call Claude to suggest dot-paths for unmapped fields.

### Community 30 - "make_flattened_form"
Cohesion: 0.40
Nodes (4): make_flattened_form(), Path, Generate a flattened (non-AcroForm) PDF for overlay testing.  Run directly to cr, Write a simple flattened PDF with label text and blank fill areas.

## Knowledge Gaps
- **6 isolated node(s):** `Executive Assistant README`, `Web Form Autofill`, `Calendar Integration Logic`, `Summer Camps 2026 Master List`, `Campsite Availability Tracker` (+1 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **16 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What connects `Render addresses in various formats and detect subject-vs-third-party fields.`, `Render an address dict in the requested format.      Args:         address: dict`, `Return True if the field label refers to the profile holder's address.      Cons` to the rest of the system?**
  _237 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `field_mapper.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06711915535444947 - nodes in this community are weakly interconnected._
- **Should `profile_loader.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06382978723404255 - nodes in this community are weakly interconnected._
- **Should `test_formatters.py` be split into smaller, more focused modules?**
  _Cohesion score 0.053156146179401995 - nodes in this community are weakly interconnected._
- **Should `test_learning.py` be split into smaller, more focused modules?**
  _Cohesion score 0.04994192799070848 - nodes in this community are weakly interconnected._
- **Should `test_acroform_roundtrip.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05 - nodes in this community are weakly interconnected._
- **Should `preflight.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07681365576102418 - nodes in this community are weakly interconnected._