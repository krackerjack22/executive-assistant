---
name: pdf-form-autofill
description: "Family-profile-driven form workflow; routes between pdf-form-extraction and pdf-form-autofill child skills based on user intent. Also orchestrates personal, household, and calendar tasks using its specialized child skills."
---

# pdf-form-autofill

Fill blank AcroForm PDFs from family profile data.

## Triggers

Use this skill when the user says things like:
- "fill out this PDF for me"
- "autofill this form for Fiona"
- "complete the intake form using Tyler's profile"
- "pre-populate this medical form"

## Preflight

Before any operation in this skill, run `python skills/pdf-form-extraction/extract.py --check-env --json` (or `python skills/form-autofill/autofill.py --check-env`) and parse the output.

- If `issues` is non-empty, stop. Explain the specific issue(s) and the listed `actionable` fix(es) to the user. Do not retry the operation until the user reports the issue resolved.
- If `warnings` is non-empty, mention them once in your response and proceed.
- If `platform.sandbox_indicators` is non-empty AND the user references a file/path that is not under `paths.profiles_dir` or another verified location, warn them: "I appear to be running in a sandboxed environment. The path `<X>` may not be accessible from here. If you are using Cowork, please confirm the parent folder is added to your project's connected folders."
- Do NOT assume you know the agent platform purely from your own context. Always combine your platform knowledge (system prompt + tool list) with the preflight report's machine facts before making routing decisions.

## File Path Handling

### Resolving the template PDF path

When the user provides a PDF to fill (drag-drop, attachment, upload tool), resolve its path before calling the CLI:

1. **Check your tool result** — the upload/attach tool usually returns a file path in its output. Use that.
2. **Try common landing spots** — if the tool result is ambiguous, check in order:
   - The path literally stated by the user in their message
   - Any path returned by the MCP upload or file tool that was just used
   - `/tmp/` or the session temp directory (check with `ls /tmp/*.pdf` or equivalent)
3. **If still unresolved — ask before proceeding:**
   > "I received your PDF but I need the file path to fill it. Could you share where it's saved? (e.g. `~/Desktop/intake_blank.pdf`)"

Never guess or fabricate a path. A wrong path produces a silent exit-2 failure.

### Output path (filled PDF)

- Dry-run (default): no file is written; the preview is shown in the response.
- On `--commit`:
  - If the user specified a save location → use `--output <path>`.
  - If not specified → default is `<template_stem>_filled.pdf` in the same folder as the template.
  - **If the template was uploaded to `/tmp/` or a session dir, do not save there.** Ask the user:
    > "Where would you like the filled PDF saved? (e.g. `~/Desktop/` or `~/Documents/`)"

## Workflow

1. **Choose profile** — ask which family member (default: tyler_combs).
2. **Run preflight** — `python skills/form-autofill/autofill.py --check-env`.
3. **Dry-run preview** — `python skills/form-autofill/autofill.py --template <path> --profile <id>`.
   - Show the field-by-field mapping table to the user.
   - Ask for confirmation before committing.
4. **Commit** — `python skills/form-autofill/autofill.py --template <path> --profile <id> --commit [--output <path>]`.

## Dry-Run Output Format

Each field in the preview is labeled with a confidence tier:

| Label     | Confidence | Meaning                                              | Action before commit        |
|-----------|------------|------------------------------------------------------|-----------------------------|
| CONFIDENT | high       | Exact synonym match, no alternatives                 | Safe to commit as-is        |
| CHECK     | medium     | Substring match OR exact match with 1 alternative    | Glance at the "via:" line   |
| ASK       | low        | Ambiguous — 2+ plausible candidates or weak match    | Resolve with user input      |
| MISSING   | none       | No profile data matched this field                   | Will be skipped or handled in interview mode |

Example dry-run output:
```
=== Autofill DRY_RUN  filled=13  skipped=1  low=0 ===

  CONFIDENT  [patient name]  = 'Tyler Combs'
             via: patient name → identity.legal_name
  CHECK      [insurance company]  = 'Regence BlueCross BlueShield'
             via: insurance company → insurance.primary.carrier_name
             ALT: 'Clearcut Capital' (employment.employer) score=0.50
  ASK        [phone email]  = '5035454177'
             via: phone → contact.primary_phone
             ALT: 'tylercombs@gmail.com' (contact.email) score=0.50
             NOTE: 2 plausible alternative(s) found; review before commit.
  MISSING    [blood type]  = (none)
             via: no match for field 'blood type' / alt ''

[DRY-RUN] Pass --commit to write the file.
```

If `low > 0` or missing fields exist, `--commit` will be refused unless a resolution mode is specified. Options:
- Pass `--commit-unsafe` to write anyway (still shows low fields in output)
- Pass `--resolve` to interactively fix low fields
- Pass `--missing-mode skip` to omit low/none fields and continue
- Pass `--missing-mode interview` to prompt the user interactively. 
  **CRITICAL**: When gathering user input during interview mode, if you are running as Claude Code, you must use the tool call `AskUserQuestion` to interact with the user.

## CLI Reference

```bash
# Dry-run (default — always safe)
python skills/form-autofill/autofill.py --template /path/to/blank.pdf --profile fiona_combs

# Commit (writes file; refused if any field is low confidence)
python skills/form-autofill/autofill.py --template /path/to/blank.pdf --profile fiona_combs --commit

# Commit even with low-confidence fields
python skills/form-autofill/autofill.py --template /path/to/blank.pdf --profile fiona_combs --commit-unsafe

# Interactive resolution of low-confidence fields
python skills/form-autofill/autofill.py --template /path/to/blank.pdf --profile fiona_combs --resolve

# Handle missing data modes (skip or interview)
python skills/form-autofill/autofill.py --template /path/to/blank.pdf --profile fiona_combs --missing-mode interview

# Check environment
python skills/form-autofill/autofill.py --check-env [--human]
```

## Profiles available

Run `python -c "import sys; sys.path.insert(0,'lib'); from lib import profile_loader; print([p['profile_id'] for p in profile_loader.list_profiles()])"` from the project root to list available profiles.

## Notes

- **Dry-run is the default.** `--commit` is required to write.
- Inheritance is resolved automatically: Fiona's address → Tyler's address, Fiona's insurance → Tyler's policy.
- `overlay.py` handles spatial fill for flattened PDFs containing text layers.
- **OCR Policy:** For scanned (image-only) PDFs, do NOT build or install custom OCR tools (like Tesseract). Fail gracefully and either prompt the user to manually OCR the PDF using their own software, or if you are a vision-capable agent, offer to use your native vision capabilities to read the form.
- **SSID fields:** Fields labeled "SSID", "SSIDRow", or "State Student ID" are mapped to `vault_references.ssn` and require Bitwarden to be unlocked. The vault is unlocked inline if running in a tty; otherwise run `bw unlock` first and export `BW_SESSION`.
- **Profile completeness:** If a profile has `status: skeleton_partial`, some fields may return MISSING confidence. Fill out missing profile values first, then re-run the autofill. Fields most commonly incomplete on child profiles: `identity.last_name`, `identity.date_of_birth`, and `addresses.home` (resolved via `same_as_profile` from the primary parent's profile).
