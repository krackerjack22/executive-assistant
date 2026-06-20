# Handoff — Tier 4 Planning Session (GitHub issues #10–#13)

This is a **planning and specification session, not an implementation session.**
Your output should be a detailed implementation spec for each issue — the same
format and depth as `HANDOFF_TIER1_TIER2.md` and `HANDOFF_TIER3.md` in this
repo. A future Sonnet session will do the actual coding from your specs.

Paste everything below into a fresh Opus chat.

---

## Project context

Personal executive-assistant CLI. Two child skills:

- `skills/form-autofill/` — fills blank AcroForm PDFs from family profile JSONs
- `skills/pdf-form-extraction/` — extracts field values from filled PDFs

Shared library in `lib/`. All personal data lives in JSON profile files at
`~/Assets_Library/Executive-Assistant/profiles/` — never in code.

**Current state (post tier 1–3 implementation):**
- 185 tests passing
- Python 3.9.6 (`/usr/bin/python3`), pypdf 6.11.0, pdfplumber
- `lib/` contains: `env.py`, `preflight.py`, `profile_loader.py`,
  `profile_writer.py`, `address_resolver.py`, `role_resolver.py`
- `skills/form-autofill/` contains: `autofill.py`, `acroform.py`,
  `field_mapper.py`, `formatters.py`, `emergency_contact.py`, `overlay.py`
  - `field_mapper.py` uses a synonym map (`data/synonyms.json`),
    a context rules file (`data/field_context_rules.json`),
    confidence tiers (high/medium/low/none), special resolvers for
    emergency contacts, combined city/state/zip, signature dates, and
    section-context-aware routing (PCP section hint)
  - `autofill.py` has `--resolve` interactive flow, `--missing-mode
    skip|manual|interview`, `--commit`, `--commit-unsafe`
  - `overlay.py` does spatial fill for flattened PDFs via pdfplumber word maps
- `skills/pdf-form-extraction/extract.py` has `--apply` flag for
  write-back to profiles via `lib/profile_writer.py`
- `lib/profile_writer.py` handles atomic JSON writes with source notes

Read these files before designing anything:
1. `skills/form-autofill/field_mapper.py` — understand the full resolver pipeline
2. `skills/form-autofill/autofill.py` — understand the CLI and --resolve flow
3. `skills/form-autofill/data/synonyms.json` — current synonym structure
4. `skills/form-autofill/data/field_context_rules.json` — usage constraint format
5. `skills/pdf-form-extraction/extract.py` — extraction pipeline and --apply flag
6. `lib/profile_writer.py` — atomic write contract
7. `MVP_CONTRACT.md` and `MVP_CONTRACT_addendum_2_missing_data.md` — original specs
8. The GitHub issues at https://github.com/krackerjack22/executive-assistant/issues
   — issues #10, #11, #12, #13 have brief descriptions; your job is to
   expand them into full implementation specs

---

## What to produce

For each of the four issues below, produce a specification section following
this structure (matching the format in HANDOFF_TIER1_TIER2.md):

```
## Issue #N — [TYPE]: [Title]

**Files affected:** list of files to create or modify

**Problem:** what is broken or missing and why it matters

**Design decisions to resolve:** open questions that affect the implementation
approach — answer each one based on the codebase you read

**Algorithm / approach:** step-by-step implementation plan precise enough
that a Sonnet instance can execute it without asking questions

**Edge cases and failure modes:** what can go wrong and how to handle it

**Tests to add:** specific test names, what they assert, which file they go in

**Dependencies:** other issues or external tools required first
```

Constraints that apply to all specs:
- Zero PII in any `.py`, `.md`, or config file
- Env-var driven paths, never hardcoded
- `from __future__ import annotations` in every new `.py` file
- Python 3.9.6 compatible syntax
- All new code must not break the 185 existing tests
- Dry-run must remain the default for any fill operation

---

## Issue #10 — Synonyms learning from --resolve answers

**Brief:** When a user confirms a field mapping during `--resolve` that
wasn't in `synonyms.json`, offer to persist it so the same field is
recognised automatically next time.

**Key design questions for Opus to resolve:**

1. Where exactly in the `--resolve` loop does the learning prompt appear?
   After each field, or as a batch at the end?

2. `synonyms.json` is currently structured as a nested dict
   (section → token → dot_path). Where does a learned synonym go?
   Should there be a `"learned"` section, or does it merge into existing
   sections? How do duplicate tokens across sections behave at load time?

3. What is the minimum information to save for a learned synonym to be
   useful and auditable?
   Current synonym format: `"subscriber name": "insurance.primary.subscriber_name"`
   A learned entry probably needs more metadata. What metadata?

4. Should the token be derived from the PDF field name, the alt text, or
   both? If the field name is an opaque machine ID like `"Field_47"` and
   the alt text is `"Subscriber Name"`, which becomes the token?

5. What prevents the user from accidentally polluting the synonym map with
   one-off field names that won't generalise across forms?

6. How does this interact with `field_context_rules.json`? If the user
   confirms a mapping that would normally be restricted by a context rule,
   should the rule be updated too?

---

## Issue #11 — OCR support for image-only / scanned PDFs

**Brief:** PDFs that are scanned images (no embedded text layer) return
empty word maps from pdfplumber. Add an OCR pre-processing step that
produces a text + bounding-box layer in the same format as the existing
spatial map so the rest of the pipeline is unchanged.

**Key design questions for Opus to resolve:**

1. How do we reliably detect whether a page is image-only vs. has embedded
   text? pdfplumber's `page.extract_words()` returns `[]` for image-only
   pages, but also for pages with unusual font encoding. What additional
   checks reduce false positives?

2. Two candidate OCR approaches:
   - **Tesseract** (local, `pytesseract` wrapper, requires `tesseract`
     binary via Homebrew, free)
   - **API-based** (e.g., a vision model call, requires network + cost)
   Which fits this project's constraints (personal use, offline-capable,
   no recurring cost)? Design for that one; note the other as an option.

3. The existing spatial map format (produced by `pdf_inspect.py`) is a list
   of word-level dicts. Tesseract's `image_to_data()` output uses a
   different coordinate system (pixel space, top-left origin) vs.
   pdfplumber (points, bottom-left origin for PDF). How should coordinates
   be normalised so downstream code is unaware of the source?

4. OCR adds latency. Should it run automatically when pdfplumber returns
   empty results, or require an explicit `--ocr` flag? What are the
   tradeoffs?

5. Rasterization: `pdf2image` (requires `poppler`) converts PDF pages to
   PIL images. Is poppler already available? If not, is it a reasonable
   dependency for this project? What is the fallback if it's not installed?

6. Where does OCR fit in the preflight check? Should `tesseract` and
   `poppler`/`pdftoppm` be added to optional tool checks in `preflight.py`?
   What is the preflight issue code and actionable message if they're missing
   and OCR is attempted?

7. `overlay.py` is the consumer of spatial maps for fill purposes.
   Does the OCR spatial map need to include confidence scores per word
   (Tesseract provides these), and if so, should low-confidence OCR words
   be excluded or flagged?

---

## Issue #12 — Bitwarden CLI integration for vault-backed fields

**Brief:** Profile JSONs have a `vault_references` block with null values
for sensitive fields (SSN, DL number, passport, etc.). At fill-time, when
a form field maps to a vault-backed path, the actual value should be
retrieved from Bitwarden CLI using an authenticated session token.

**Key design questions for Opus to resolve:**

1. `field_mapper.py` currently resolves dot-paths through the profile dict.
   `vault_references.ssn = null` — the path resolves to None and the field
   gets `confidence: none`. The vault lookup needs to intercept this.
   Should it happen in `field_mapper.py` (after path resolution, before
   returning None), or should `profile_loader.py` dereference vault paths
   at load time? What are the security tradeoffs of each approach?

2. The vault reference value is currently `null`. What should the non-null
   indicator look like? Options:
   - A Bitwarden item name string: `"ssn": "tyler-ssn"`
   - A structured pointer: `"ssn": {"bw_item": "tyler-ssn", "bw_field": "ssn"}`
   - A URI: `"ssn": "bw://tyler-ssn/ssn"`
   Which is most compatible with the Bitwarden CLI's `bw get item` /
   `bw get field` commands?

3. The `BW_SESSION` env var must be set for vault access. Two cases:
   - Session token present → proceed
   - Session token absent → how should the system respond?
     (a) Fail silently, treat vault fields as `confidence: none` with a note
     (b) Prompt the user to run `bw unlock` and set `BW_SESSION`
     (c) Block the entire fill operation
   Which is correct for a CLI tool with dry-run-by-default semantics?

4. Vault access should only happen when a form actually needs a vault-backed
   field, not on every run. How does the dry-run show vault-backed fields
   (they can't be dereferenced without unlocking)? Should dry-run show a
   placeholder like `[VAULT: tyler-ssn]`?

5. `lib/vault.py` is the proposed new module. What is its full public API?
   Consider: caching (don't call `bw` twice for the same item in one run),
   error handling (`bw` CLI not installed, wrong session, item not found),
   and subprocess timeout.

6. The preflight check already looks for the `bw` binary. What additional
   preflight checks are needed? Should a missing `BW_SESSION` be a warning
   or an issue? Should it only be checked when at least one vault-backed
   field exists in the profile?

---

## Issue #13 — Web form autofill via browser-MCP integration

**Brief:** Extend the autofill skill to fill web forms in a browser, using
the same profile data and confidence system as the PDF autofill skill.
This is the largest feature on the roadmap — your spec should be thorough
enough to identify whether this is one deliverable or should be broken into
multiple phases.

**Key design questions for Opus to resolve:**

1. **Skill structure:** Should this be a new child skill
   `skills/web-form-autofill/` with its own `SKILL.md` and CLI entry point,
   or an extension of `skills/form-autofill/`? Consider that the field
   mapping logic (`field_mapper.py`, `synonyms.json`) is entirely reusable,
   but the fill mechanism (DOM vs. AcroForm) is completely different.

2. **Field detection:** AcroForm has explicit field names and alt text.
   Web forms have DOM labels, `placeholder`, `aria-label`, `name` attribute,
   or surrounding visible text. How should the agent extract a canonical
   "field label" from a web form field to pass to `field_mapper.map_pdf_field()`?
   Which DOM attributes should be checked, in what priority order?

3. **Browser tool:** The project environment has the Claude-in-Chrome MCP
   available (`mcp__Claude_in_Chrome__*` tools). Read the tool list in your
   system prompt and determine: which specific tools are needed for
   (a) reading field labels, (b) writing values into inputs, (c) handling
   dropdowns/checkboxes, and (d) submitting? Are there gaps that need
   computer-use fallback?

4. **Dry-run semantics:** PDF dry-run never touches the file. Web dry-run
   can't modify the DOM without side effects (autofill events may trigger
   JS logic). How should dry-run work for web forms? Options:
   - Read-only: extract all fields, show proposed values, never write
   - Write-to-hidden-copy: not feasible in a real browser
   - Write then clear: too risky (JS side effects)
   Which approach, and what caveats does the SKILL.md need to document?

5. **Multi-step forms:** Many web intake forms are paginated (Next → Next →
   Submit). How should the skill handle forms where not all fields are
   visible at load time? Should it be limited to single-page forms in v1?

6. **Confirmation before submit:** The skill must never submit a form without
   explicit user approval. Where in the flow does the confirmation happen,
   and how is it implemented given that the agent is running a CLI/skill
   (not a UI)?

7. **Phase breakdown:** Given the complexity, recommend whether this should
   ship as one issue or be broken into sub-issues (e.g., Phase 1: read-only
   field extraction from a web form; Phase 2: fill + dry-run; Phase 3:
   confirmed submit with multi-step support). Provide a recommended phase
   boundary and rationale.

---

## Output format

Produce one complete specification section per issue in the format described
above. When you're done, also produce:

1. A **recommended implementation order** across all four issues with rationale
2. A **dependency graph** — which issues block others, which are independent
3. A **risk assessment** — which issues have the highest chance of requiring
   architectural changes to existing code, and what those changes might be
4. For issue #13 specifically: a **phase breakdown recommendation** if you
   conclude it should not ship as a single issue

The output of this session becomes the content of a new
`HANDOFF_TIER4_IMPL.md` file in the repo. Structure your output accordingly.
