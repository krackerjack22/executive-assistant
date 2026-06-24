# Tier 4 Implementation Spec (Issues #10–#13)

This document contains the implementation specifications for the Tier 4 features of the `executive-assistant` project, generated based on the planning session constraints.

## Resolved Issues

**Issue #10 (Synonyms learning)** and **Issue #12 (Bitwarden integration)** have already been implemented in the `main` branch:
- Issue #10 is addressed via `learning.py` and the `--resolve` loop in `autofill.py`.
- Issue #12 is addressed via `lib/vault.py` and the vault interception in `field_mapper.py`.

Therefore, no further planning or implementation is required for these issues.

---

## Issue #11 — [ENHANCEMENT]: OCR support for image-only / scanned PDFs

**Files affected:** 
- `skills/pdf-form-extraction/pdf_inspect.py`
- `skills/form-autofill/overlay.py`

**Problem:** PDFs that are scanned images (no embedded text layer) return empty word maps from `pdfplumber`. Currently, `overlay.py` crashes/aborts when it encounters this. We need a way to support these PDFs while maintaining low recurring costs and fitting the constraints of a personal CLI tool.

**Design decisions to resolve:**

1. **Detecting image-only pages:** `pdfplumber` returns an empty word map. We can cross-reference this by checking if the page contains images (`len(page.images) > 0`). If a page has images but no text, it is highly likely an image-only scanned page.
2. **OCR Approach Evaluation:**
   - *Native Agent Vision (Agent-in-the-loop):* Since this tool is designed to be run by AI agents (like Claude Code, Antigravity, OpenClaw), the script can export the PDF pages as images and prompt the executing agent to use its native vision capabilities to perform the OCR. This avoids requiring API keys if the native environment already supports vision.
   - *API-based (Gemini API fallback):* If the native agent lacks vision capabilities (or if a human is running it directly), the script can fall back to making a direct API call to a Gemini vision model (e.g., Flash 1.5), requiring `GEMINI_API_KEY`.
   - *User/manual OCR:* The classic fallback where the user manually OCRs the document in macOS Preview or Adobe Acrobat.
   *Decision:* We will implement an **Agent-First Interactive Workflow**.

3. **Preflight check:** The preflight will optionally check for `GEMINI_API_KEY`, but its absence won't fail the preflight since the Native Agent might be able to handle it natively.

4. **Confidence scores:** We will treat all extracted text from the Vision process as standard text and let the downstream `field_mapper.py` confidence logic handle matching confidence.

**Algorithm / approach:**

1. Modify `skills/form-autofill/overlay.py`.
2. When extracting words for a page via `pdfplumber`, if the result is empty but images are detected (`len(page.images) > 0`), flag the document as `needs_ocr`.
3. If `needs_ocr` is true:
   - If not running in an interactive terminal, abort with the Manual OCR error.
   - If interactive, prompt: `This PDF appears to be a scanned image. Proceed with [A]utomated OCR or [M]anual OCR?`
4. If `M` is selected, exit cleanly with instructions on how to manually OCR.
5. If `A` is selected:
   - Export the PDF pages as high-res images (via `pdfplumber` `.to_image().original` or `pdf2image`) to a temporary directory.
   - Print a prompt to stdout specifically addressed to the running agent:
     `[AGENT INSTRUCTION] Please use your vision capabilities to analyze the following images: <paths>. Provide a JSON array containing every word and its bounding box (x0, top, x1, bottom). Paste the JSON below, or type 'fallback' if you cannot do this.`
   - Wait for `stdin`.
   - If the agent provides the JSON, parse it into `words_by_page` and continue.
   - If the agent types `fallback` (or user presses Enter):
     - Check for `GEMINI_API_KEY`. If missing, abort with an error instructing the user to add it to the `.env` file within the repository root.
     - Make a direct API call to the Gemini Vision API with the images and prompt.
     - Parse the JSON response into `words_by_page` and continue normal `overlay.py` mapping.

**Edge cases and failure modes:**
- *Vision API format hallucination:* The agent or Gemini API might return invalid JSON. The code must catch `JSONDecodeError`, request a retry or fallback.
- *Coordinate scaling:* The vision model bounding boxes must be properly scaled back to the PDF's point coordinate system (which `pdfplumber` uses).

**Tests to add:**
- `test_overlay_detects_image_only_pdf()`: Provide a dummy PDF with an image but no text, assert it raises the specific OCR instruction error. (In `tests/test_overlay.py`)

**Dependencies:** None.

---

## Issue #13 — [FEATURE]: Web form autofill via browser-MCP integration

**Files affected:** 
- `skills/web-form-autofill/SKILL.md` (NEW)
- `skills/web-form-autofill/web_autofill.py` (NEW)
- `skills/web-form-autofill/dom_parser.py` (NEW)

**Problem:** The current autofill skill only works on PDFs. Many forms are web-based. We need to extend the system to fill web forms using the existing profile data and mapping logic.

**Design decisions to resolve:**

1. **Skill structure:** This should be a **new child skill** (`skills/web-form-autofill/`). While it reuses `field_mapper.py`, the CLI interface, DOM traversal, and MCP integration are fundamentally different from PDF byte manipulation.
2. **Field detection:** The agent should use MCP tools to read the DOM. Canonical field labels should be extracted by prioritizing: `aria-label` > `<label>` linked by `for` attribute > `placeholder` > surrounding visible text.
3. **Browser tool:** The `Claude_in_Chrome` MCP will be used.
   - *Reading:* Tools that extract the DOM or specific nodes.
   - *Writing:* Tools that set input values or select dropdown options.
   - *Submitting:* Click tools.
4. **Dry-run semantics:** For web forms, a dry-run will be **Read-only**. The skill will extract all fields from the live DOM, run them through `field_mapper.py`, and print the proposed mapping table to the CLI. It will *not* modify the DOM during a dry-run to avoid triggering JS side-effects.
5. **Multi-step forms:** Phase 1 will be limited to single-page forms. Multi-step forms require complex state management and navigation handling which is out of scope for the initial release.
6. **Confirmation before submit:** The skill will have a `--fill` flag which injects the values into the DOM but *does not submit*. The user must manually review the filled form in their browser and click the submit button themselves. This entirely eliminates the risk of accidental automated submissions.
7. **Phase breakdown:** 
   - **Phase 1 (This issue):** Single-page web form read-only extraction and dry-run CLI table, plus a `--fill` flag that injects values into the browser without submitting.

**Algorithm / approach:**

1. Create `skills/web-form-autofill/web_autofill.py` as the CLI entry point.
2. Connect to the browser via MCP to fetch the current active tab's DOM form inputs.
3. Parse the inputs (`dom_parser.py`) to extract canonical labels based on the priority list (`aria-label`, `<label>`, `placeholder`).
4. Pass each label to `lib.field_mapper.map_pdf_field()` (which works perfectly fine for web labels).
5. Output the standard human-readable table showing the proposed fill values.
6. If `--fill` is passed, iterate over the mapped fields and use MCP to inject the `mapped_value` into the corresponding DOM nodes.
7. Exit and instruct the user to review and submit the form in the browser.

**Edge cases and failure modes:**
- *React/SPA synthetic events:* Direct DOM value injection might not trigger React state updates. We may need to use MCP tools that simulate actual typing rather than just setting `.value`.
- *Hidden fields:* Ignore `type="hidden"` fields.

**Tests to add:**
- `test_dom_parser_prioritizes_aria_label()`: Ensure the canonical label logic works.
- `test_web_autofill_dry_run()`: Mock the MCP response and ensure the CLI table is generated.

**Dependencies:** Requires Chrome MCP setup and `field_mapper.py` (which is already done).

---

## Final Recommendations

1. **Recommended implementation order:** 
   - Issue #11 (trivial enhancement to `overlay.py` error handling)
   - Issue #13 (Phase 1)
2. **Dependency graph:** 
   - #11 is independent. 
   - #13 is independent but relies on the existing `field_mapper.py`.
3. **Risk assessment:** 
   - Issue #13 has moderate risk due to the unpredictability of web DOMs and SPA frameworks (React/Vue). Implementing the `--fill` step might require tweaking how MCP interacts with the page (e.g., simulated typing vs DOM value updates).
