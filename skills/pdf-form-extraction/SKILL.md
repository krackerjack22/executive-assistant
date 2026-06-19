---
name: pdf-form-extraction
description: Read a filled PDF form and extract its values as a candidate profile update. Triggers on "extract from this PDF", "read this intake form", "what's in this filled-out form".
---

# pdf-form-extraction

Extract field values from a filled AcroForm PDF and produce a candidate profile delta.

## Triggers

Use this skill when the user says things like:
- "extract from this PDF"
- "read this intake form"
- "what's in this filled-out form?"
- "pull the data from this completed PDF"
- "scan this form and tell me what it has"

## Preflight

Before any operation in this skill, run `python skills/pdf-form-extraction/extract.py --check-env` and parse the output.

- If `issues` is non-empty, stop. Explain the specific issue(s) and the listed `actionable` fix(es) to the user. Do not retry the operation until the user reports the issue resolved.
- If `warnings` is non-empty, mention them once in your response and proceed.
- If `platform.sandbox_indicators` is non-empty AND the user references a file/path that is not under `paths.profiles_dir` or another verified location, warn them: "I appear to be running in a sandboxed environment. The path `<X>` may not be accessible from here. If you are using Cowork, please confirm the parent folder is added to your project's connected folders."
- Do NOT assume you know the agent platform purely from your own context. Always combine your platform knowledge (system prompt + tool list) with the preflight report's machine facts before making routing decisions.

## File Path Handling

### Resolving the input PDF path

When the user provides a file (drag-drop, attachment, upload tool), resolve its path before calling the CLI:

1. **Check your tool result** — the upload/attach tool usually returns a file path in its output. Use that.
2. **Try common landing spots** — if the tool result is ambiguous, check in order:
   - The path literally stated by the user in their message
   - Any path returned by the MCP upload or file tool that was just used
   - `/tmp/` or the session temp directory (check with `ls /tmp/*.pdf` or equivalent)
3. **If still unresolved — ask before proceeding:**
   > "I received your PDF but I need the file path to process it. Could you share where it's saved? (e.g. `~/Desktop/intake_form.pdf`)"

Never guess or fabricate a path. A wrong path produces a silent exit-2 failure.

### Output path

Extraction results print to stdout by default (no file written). If the user asks to save the output:
- Use `--output <path>` and confirm the destination with the user if not obvious.
- If unspecified, tell the user the result is in the response and offer to save it.

## Workflow

1. **Detect AcroForm** — pdf_inspect.has_acroform() determines whether the PDF has fillable fields.
2. **Dump fields** — extract all field names, alt text, types, and current values.
3. **Spatial map** — pdfplumber produces a word-position map (useful for manual review and v1.5 overlay).
4. **Propose profile delta** — a candidate_delta JSON is returned for user review.
5. **User reviews** — the extraction does NOT write to any profile. The user manually reviews and applies any changes.

## CLI Reference

```bash
# Extract and print to stdout
python skills/pdf-form-extraction/extract.py --input /path/to/filled.pdf

# Extract with profile annotation
python skills/pdf-form-extraction/extract.py --input /path/to/filled.pdf --target-profile tyler_combs

# Write result to file
python skills/pdf-form-extraction/extract.py --input /path/to/filled.pdf --output extracted.json

# Check environment
python skills/pdf-form-extraction/extract.py --check-env [--human]
```

## Output format

```json
{
  "pdf_path": "/path/to/form.pdf",
  "has_acroform": true,
  "page_count": 3,
  "fields": [
    {"name": "patient_name", "alt": "Patient Name", "field_type": "/Tx", "value": "...", "confidence": "high"}
  ],
  "spatial_map": [...],
  "candidate_delta": {"profile_id": "tyler_combs", "proposed_updates": {...}},
  "target_profile_id": "tyler_combs"
}
```

## Notes

- **Extraction is read-only.** No profiles are modified automatically.
- AcroForm PDFs only in v1. OCR / flattened PDF support is v2.
- The candidate_delta is a starting point — always review before applying to a profile.
