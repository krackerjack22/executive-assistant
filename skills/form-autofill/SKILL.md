---
name: form-autofill
description: Fill out a PDF form using a family member's profile. Triggers on "fill out this PDF", "autofill this form for Fiona", "complete the intake form using Tyler's profile".
---

# form-autofill

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

## Workflow

1. **Choose profile** — ask which family member (default: tyler_combs).
2. **Run preflight** — `python skills/form-autofill/autofill.py --check-env`.
3. **Dry-run preview** — `python skills/form-autofill/autofill.py --template <path> --profile <id>`.
   - Show the field-by-field mapping table to the user.
   - Ask for confirmation before committing.
4. **Commit** — `python skills/form-autofill/autofill.py --template <path> --profile <id> --commit [--output <path>]`.

## CLI Reference

```bash
# Dry-run (default — always safe)
python skills/form-autofill/autofill.py --template /path/to/blank.pdf --profile fiona_combs

# Commit (writes file)
python skills/form-autofill/autofill.py --template /path/to/blank.pdf --profile fiona_combs --commit

# Check environment
python skills/form-autofill/autofill.py --check-env [--human]
```

## Profiles available

Run `python -c "import sys; sys.path.insert(0,'lib'); from lib import profile_loader; print([p['profile_id'] for p in profile_loader.list_profiles()])"` from the project root to list available profiles.

## Notes

- **Dry-run is the default.** `--commit` is required to write.
- Inheritance is resolved automatically: Fiona's address → Tyler's address, Fiona's insurance → Tyler's policy.
- `overlay.py` (spatial fill for flattened PDFs) is a v1.5 stub — not yet implemented.
