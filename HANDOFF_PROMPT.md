# Handoff prompt — paste into a new Sonnet chat

Copy everything below the `---` line into a fresh chat (Sonnet model recommended; Haiku for cosmetic follow-ups only). Before pasting, complete the **user setup steps** at the bottom.

---

You are continuing a project from a planning session that occurred in Opus. The architecture is locked. Your job is implementation only — do not redesign.

## Project context

I am building a personal **executive-assistant** umbrella skill with two child skills (`pdf-form-extraction` and `form-autofill`). The data layer (5 family-profile JSONs + a registry) is already built and verified. You are building the code.

## Read these files first (in order)

1. `/Users/tylercombs/Dev/executive-assistant/MVP_CONTRACT.md` — full build spec, including directory layout, module signatures, env-var contract, test plan, and acceptance criteria. **Read this carefully and follow it exactly.**
2. The 5 profile JSONs at `$EXEC_ASSISTANT_PROFILES_DIR` (defaults to `~/Assets_Library/Executive-Assistant/profiles`):
   - `profiles_index.json` (registry + role_resolution_map + address_role_keywords)
   - `tyler_combs.json`, `madeline_miller.json`, `fiona_combs.json`, `charlotte_combs.json`, `isaac_baron.json`
3. The original test PDF I'll provide in `tests/fixtures/Tyler_Med_Data.pdf` (or a blank copy of it for round-trip testing). I will add 2 more test PDFs to `tests/fixtures/` before you run tests.

## What to build

### Note on order of operations during build

Sonnet should build `lib/preflight.py` **second**, immediately after `lib/env.py`. Every subsequent module depends on the environment being verified; building preflight early surfaces path/install issues before they cascade through other modules.

### Build order list

1. `lib/env.py`
2. `lib/preflight.py` ← inserted
3. `lib/profile_loader.py`
4. `lib/address_resolver.py`
5. `lib/role_resolver.py`
6. `skills/form-autofill/field_mapper.py` + `data/synonyms.json`
7. `skills/form-autofill/acroform.py`
8. `skills/form-autofill/autofill.py` (CLI, wires `--check-env`)
9. `skills/form-autofill/overlay.py` (scaffold)
10. `skills/form-autofill/SKILL.md` (includes Layer 2 block)
11. `skills/pdf-form-extraction/pdf_inspect.py`
12. `skills/pdf-form-extraction/extract.py` (CLI, wires `--check-env`)
13. `skills/pdf-form-extraction/SKILL.md` (includes Layer 2 block)
14. `SKILL.md` (umbrella), `child-skills.md`, `README.md`
15. `config/config.example.json`
16. All tests under `tests/` including new preflight tests

## Critical constraints

- **Zero PII in any `.py` file, `.md` file, or `config.example.json`.** All personal data lives in JSON files outside the code tree, loaded at runtime.
- **Env-var driven paths.** Code must never hardcode `/Users/tylercombs/...`. Read `EXEC_ASSISTANT_PROFILES_DIR`, fall back to `~/Assets_Library/Executive-Assistant/profiles`.
- **Dry-run is default.** Autofill CLI requires explicit `--commit` to write files.
- **Respect `unverified` tagged relationships.** The role_resolver should skip them unless explicitly passed `strict=False`.
- **No web form support, no OCR, no Bitwarden in v1.** These are explicitly out of scope.
- **No redesign.** If anything in the contract seems wrong, flag it and ask before changing.

## Tools you have

- `pypdf` (already installed)
- `pdfplumber` (already installed)
- `reportlab` (install if missing for v1.5; not needed for v1)
- `pytest` (install if missing)
- `pdftk` (installed locally via Homebrew; use as sidecar if helpful)

## Acceptance

Use the contract's "Acceptance criteria" checklist. When all boxes check, you're done with v1. Report the test output and any deviations from the contract.

## When you finish v1

Produce a brief one-page status report listing:
- What was built
- All tests passing (or which ones failed and why)
- Any contract deviations and rationale
- v1.5 starting points (spatial overlay) — files to extend, not rewrite

---

## User setup steps (complete before starting the new chat)

1. **Save the contract file** to `/Users/tylercombs/Dev/executive-assistant/MVP_CONTRACT.md`. (Currently in your Cowork outputs folder.)
2. **Save this handoff prompt** wherever convenient.
3. **Move the 5 profile JSONs** from `/Users/tylercombs/Documents/Claude/Projects/Executive Assistant/profiles/` to the Google Drive location:
   ```
   /Users/tylercombs/Library/CloudStorage/GoogleDrive-tylercombs@gmail.com/Shared drives/Combslink/Assets_Library/Executive-Assistant/profiles/
   ```
4. **Create the symlink** for the canonical access path:
   ```bash
   mkdir -p "$HOME/Assets_Library/Executive-Assistant"
   ln -s "/Users/tylercombs/Library/CloudStorage/GoogleDrive-tylercombs@gmail.com/Shared drives/Combslink/Assets_Library/Executive-Assistant/profiles" \
         "$HOME/Assets_Library/Executive-Assistant/profiles"
   ls -la "$HOME/Assets_Library/Executive-Assistant/profiles"   # confirm files visible
   ```
5. **Mount `/Users/tylercombs/Dev/executive-assistant/` as a workspace folder** in the new Cowork chat (so Sonnet can write the skill code directly).
6. **Place test PDFs** in `/Users/tylercombs/Dev/executive-assistant/tests/fixtures/`. Include at least `Tyler_Med_Data.pdf` (or a blank copy). Add 2 more if you have them.
7. Paste the prompt above (everything between the `---` lines) into the new chat.
