# Executive Assistant — MVP Contract (v1)

This is the build spec for the `executive-assistant` umbrella skill + its two child skills. Tightly scoped for a working first draft. Sonnet implements; Haiku does cosmetic/test follow-ups.

## Goals (v1)

1. **Personal-profile data layer** — multi-identity JSONs with relationship graph, address canonicalization, role resolution, and `same_as_profile` / `inherit_from_subscriber` inheritance.
2. **Skill A — `pdf-form-extraction`** — read filled AcroForm PDF → emit candidate profile JSON delta (does not overwrite without confirmation).
3. **Skill B — `form-autofill`** — read profile JSON + blank AcroForm PDF → write filled PDF.
4. **Umbrella `executive-assistant`** — orchestrates the two child skills.
5. **Zero PII in code.** All personal data lives in JSON files outside the code tree.
6. **Personal use only.** Code is parameterized but does not need plugin-marketplace polish.

## Non-goals (deferred to v1.5 / v2)

- Web form autofill (any browser-MCP integration)
- Spatial overlay for flattened PDFs (v1.5 — scaffold but do not implement)
- Image-only / OCR PDF support
- Bitwarden CLI integration (v2)
- LiteLLM / SQL Server integration
- Multi-machine sync orchestration

## Architecture

```
/Users/tylercombs/Dev/executive-assistant/
├── SKILL.md                         # umbrella; declares child skills
├── README.md
├── child-skills.md                  # index of child skills
├── config/
│   └── config.example.json          # template, NO PII
├── lib/                             # shared by both child skills
│   ├── __init__.py
│   ├── env.py                       # env-var resolution + path canonicalization
│   ├── profile_loader.py            # load + resolve same_as / inherit_from / external_persons
│   ├── address_resolver.py          # render addresses in any format
│   └── role_resolver.py             # walk relationship graph for "father" / "mother" / etc.
├── skills/
│   ├── pdf-form-extraction/
│   │   ├── SKILL.md
│   │   ├── extract.py               # CLI entry point
│   │   ├── pdf_inspect.py           # pypdf + pdfplumber helpers
│   │   └── references/
│   │       └── extraction_workflow.md
│   └── form-autofill/
│       ├── SKILL.md
│       ├── autofill.py              # CLI entry point
│       ├── acroform.py              # AcroForm fill via pypdf
│       ├── overlay.py               # SCAFFOLD ONLY in v1; raises NotImplemented for flattened PDFs
│       ├── field_mapper.py          # form-field-name → profile-field resolver
│       └── references/
│           └── role_examples.md
└── tests/
    ├── fixtures/                    # user drops test PDFs here
    └── test_*.py                    # pytest, see Test plan below
```

## Env vars + config

**Env vars (read in order, first non-empty wins):**

| Var | Purpose | Default if unset |
|---|---|---|
| `EXEC_ASSISTANT_PROFILES_DIR` | Path to profiles directory | `~/Assets_Library/Executive-Assistant/profiles` |
| `EXEC_ASSISTANT_CONFIG_PATH` | Path to config.json | `~/.config/executive-assistant/config.json` (optional file) |

**`lib/env.py` contract:**
```python
def profiles_dir() -> Path:
    """Returns resolved absolute Path. Raises FileNotFoundError with a clear message
    if neither env var nor default path exists."""

def config() -> dict:
    """Reads optional config.json. Returns {} if file missing. Never raises."""
```

**`config.example.json`** (template, NO PII, copy to actual config path manually):
```json
{
  "default_profile_id": "tyler_combs",
  "fill_options": {
    "flatten_after_fill": false,
    "preserve_original": true,
    "output_suffix": "_filled"
  },
  "bitwarden": { "enabled": false }
}
```

## Profile schema (canonical)

**Source of truth: the 5 JSON files already created.** Sonnet reads these as the schema reference. Do not redesign the schema. Key sections:
- `identity`, `relationships`, `fillable_roles_when_referenced`, `contact`, `addresses`, `employment`, `external_entities`, `external_persons`, `insurance`, `vault_references`, `source_extraction_notes`, `school` (children only)

**Inheritance markers to resolve at load time:**
- `addresses.{role}: { "same_as": "home" }` → in-profile alias
- `addresses.{role}: { "same_as_profile": "<profile_id>" }` → cross-profile alias
- `insurance.primary: { "inherit_from_subscriber": true, "subscriber_profile_id": "<id>" }` → cross-profile inheritance

**`profile_loader.py` contract:**
```python
def load_profile(profile_id: str) -> dict:
    """Loads a profile and fully resolves all same_as / same_as_profile / inherit_from_subscriber
    pointers. Returns a flat self-contained dict ready for the field_mapper.
    Raises FileNotFoundError if profile_id not in registry."""

def load_index() -> dict:
    """Loads profiles_index.json."""

def list_profiles() -> list[dict]:
    """Returns minimal {profile_id, legal_name, status} per profile."""
```

## Module specs

### `lib/role_resolver.py`
```python
def resolve(active_profile: dict, role_keyword: str, all_profiles: dict, role_map: dict) -> dict | None:
    """Given an active profile and a role keyword (e.g. 'father', 'mother', 'subscriber'),
    walk the lookup_chain from profiles_index.role_resolution_map and return the target profile
    or external_persons entry. Returns None if no match.
    
    Honors filters (e.g. {gender: 'Female'}) and tags (target_tag, external_persons_tag).
    Skips relationships tagged 'unverified' unless strict=False is passed."""
```

### `lib/address_resolver.py`
```python
ADDRESS_FORMATS = [
    "street_only",                   # "5910 Rockwood Ct"
    "city_st_zip_comma",             # "Lake Oswego, OR 97035"
    "city_st_zip_nocomma",           # "Lake Oswego OR 97035"
    "single_line",                   # "5910 Rockwood Ct, Lake Oswego, OR 97035"
    "parts_separated",               # dict: {street, city, state, zip}
]

def render(address: dict, fmt: str) -> str | dict: ...

def is_subject_address(field_label: str, index: dict) -> bool:
    """Consults index.address_role_keywords. Returns True if the label refers to the
    profile holder's address; False if it refers to a third-party entity."""
```

### `skills/form-autofill/field_mapper.py`
```python
def map_pdf_field(pdf_field_name: str, pdf_field_alt: str, resolved_profile: dict,
                  index: dict) -> tuple[str | None, str]:
    """Returns (value, source_explanation). Value is None if no match.
    Source explanation describes why this value was chosen (for the dry-run preview)."""
```

Synonym map lives in a `data/synonyms.json` file beside `field_mapper.py`. NO PII.

### `skills/form-autofill/acroform.py`
```python
def fill(template_pdf: Path, profile: dict, index: dict,
         output_pdf: Path, dry_run: bool = True) -> dict:
    """Fills an AcroForm PDF. If dry_run, returns a preview dict (field-by-field
    mapping + chosen value + source). If not dry_run, writes output_pdf and returns
    a summary dict."""
```

### `skills/form-autofill/overlay.py` (scaffold only in v1)
```python
def fill(template_pdf: Path, profile: dict, index: dict, output_pdf: Path,
         dry_run: bool = True) -> dict:
    """v1.5 — currently raises NotImplementedError('Spatial overlay scheduled for v1.5')."""
```

### `skills/pdf-form-extraction/extract.py`
```python
def extract(pdf_path: Path, target_profile_id: str | None = None) -> dict:
    """Returns a candidate profile-update dict. Does NOT write to disk.
    User reviews + commits manually (or via a second command). Includes a
    spatial_map and a confidence-flagged field list."""
```

## CLI spec

Both skills expose a CLI. Invocation pattern (via Anthropic skill convention, called from inside the skill folder):

```bash
# Extract
python skills/pdf-form-extraction/extract.py --input /path/to/filled.pdf \
    [--target-profile tyler_combs] [--output extracted.json]

# Autofill
python skills/form-autofill/autofill.py --template /path/to/blank.pdf \
    --profile fiona_combs [--output filled.pdf] [--dry-run]
```

**Dry-run is the DEFAULT.** Explicit `--commit` required to actually write filled output.

## SKILL.md outlines

### Umbrella `executive-assistant/SKILL.md`
- name: executive-assistant
- description: Family-profile-driven form workflow; routes between pdf-form-extraction and form-autofill child skills based on user intent.
- Lists child skills + how to invoke them.

### `skills/pdf-form-extraction/SKILL.md`
- description triggers on: "extract from this PDF", "read this intake form", "what's in this filled-out form"
- Workflow: detect AcroForm → dump fields → spatial map → propose profile delta

### `skills/form-autofill/SKILL.md`
- description triggers on: "fill out this PDF", "autofill this form for Fiona", "complete the intake form using Tyler's profile"
- Workflow: choose profile → load + resolve inheritance → AcroForm fill → dry-run preview → commit

## Test plan

**Fixtures dir:** `tests/fixtures/` — user drops 2-3 test PDFs in here.

**Required tests:**
1. `test_env.py` — env-var resolution, default fallback, error on missing dir
2. `test_profile_loader.py` — load each of the 5 profiles, verify inheritance resolved (Fiona's address = Tyler's, insurance subscriber resolved)
3. `test_role_resolver.py` — "father" on Fiona → Tyler; "mother" on Fiona → external_persons.Lynsee; "secondary_emergency_contact" on Charlotte → external_persons.Penny; "subscriber" on Fiona's insurance → Tyler
4. `test_address_resolver.py` — render each of 5 formats; subject-vs-third-party detection on sample labels
5. `test_field_mapper.py` — given a synthetic field-name list mimicking Tyler_Med_Data.pdf, verify correct values chosen
6. `test_acroform_roundtrip.py` — load Tyler's intake form (you'll need to add a blank version to fixtures or use a stripped copy), fill it with Tyler's profile, verify all populated fields match expected values
7. `test_dry_run.py` — dry-run output contains every fillable field with source explanation; no file written

## Preflight checks

Every CLI invocation runs preflight before any operation. Preflight is split into two layers with strict separation of concerns.

### Layer 1 — `lib/preflight.py` (machine-verifiable only)

Checks only what a subprocess can introspect about its own environment. **Does NOT attempt to identify the agent platform** (Claude Code vs Cowork vs Gemini vs future agents). That determination is not reliably available from inside a script and is the LLM agent's job, not the script's.

Checks performed:
- OS family via `platform.system()` (Darwin / Linux / Windows)
- Hostname + Python version (descriptive only)
- Sandbox-indicator probe: presence of `/sessions/` prefix or other known sandbox path patterns — reported as a fact, never used for routing logic inside the script
- Resolved `profiles_dir` via `env.profiles_dir()`, plus the source (env_var / default / fallback)
- Profiles dir readable AND `profiles_index.json` parseable AND profile count > 0 — this combination catches Google Drive "online-only" placeholder files (a stat-only check would pass; the parse forces a real read)
- Output directory writable (touch + remove a `.preflight_write_test` file, then cleanup)
- Required Python modules importable: `pypdf`, `pdfplumber`
- Optional Python modules: `reportlab` (v1.5), nothing for v1
- Optional binaries via `shutil.which()`: `pdftk`, `bw` (latter reported but not used in v1)

### Preflight output shape (stable contract)

```json
{
"schema_version": "1.0",
"ok": true,
"platform": {
"os_family": "Darwin",
"python_version": "3.11.5",
"hostname": "Tylers-MacBook-Pro",
"sandbox_indicators": [],
"_note": "sandbox_indicators is descriptive only; never used for routing decisions inside the script"
},
"paths": {
"profiles_dir": "<resolved abs path>",
  "profiles_dir_source": "env_var | default | fallback",
  "profiles_dir_readable": true,
  "profiles_index_parsed": true,
  "profiles_count": 5,
  "output_dir": "<resolved abs path>",
    "output_dir_writable": true
    },
    "tools": {
    "required": {"pypdf": "3.17.4", "pdfplumber": "0.11.9"},
    "optional": {"reportlab": null, "pdftk": "/opt/homebrew/bin/pdftk-java", "bw": null}
    },
    "issues": [],
    "warnings": [],
    "actionable": []
    }
    ```
    
    - `issues[]` — list of dicts `{code, message, fix}`. Any non-empty `issues` blocks the operation (CLI exits non-zero).
    - `warnings[]` — same shape; surfaced once, operation proceeds.
    - `actionable[]` — flat list of `fix` strings, deduped, for the LLM to relay to the user.
    
    ### Layer 2 — SKILL.md instructions to the agent
    
    Each child skill's SKILL.md MUST include this instruction block verbatim under a section titled `## Preflight`:
    
    > Before any operation in this skill, run `python <skill-dir>/preflight_entry.py --json` (or `python -m executive_assistant.preflight`) and parse the output.
    >
    > - If `issues` is non-empty, stop. Explain the specific issue(s) and the listed `actionable` fix(es) to the user. Do not retry the operation until the user reports the issue resolved.
    > - If `warnings` is non-empty, mention them once in your response and proceed.
    > - If `platform.sandbox_indicators` is non-empty AND the user references a file/path that is not under `paths.profiles_dir` or another verified location, warn them: "I appear to be running in a sandboxed environment. The path `<X>` may not be accessible from here. If you are using Cowork, please confirm the parent folder is added to your project's connected folders."
    > - Do NOT assume you know the agent platform purely from your own context. Always combine your platform knowledge (system prompt + tool list) with the preflight report's machine facts before making routing decisions.
    
    ### Preflight CLI
    
    Both skills accept `--check-env` (alias: `--preflight`), which runs preflight and exits without doing the main operation.
    
    ```bash
    python skills/form-autofill/autofill.py --check-env
    python skills/pdf-form-extraction/extract.py --check-env
    ```
    
    Output is JSON to stdout by default. `--human` flag produces a colorized table for terminal use.
    
    ### Exit codes
    
    | Code | Meaning |
    |---|---|
    | `0` | preflight passed (no issues; warnings allowed) |
    | `1` | preflight failed (one or more issues); operation did not proceed |
    | `2` | invalid arguments or internal error |
    
    ### Issue code registry (initial v1 set)
    
    `code` values in `issues[]` are stable identifiers the LLM can pattern-match on:
    
    | Code | Trigger | Fix template |
    |---|---|---|
    | `PROFILES_DIR_MISSING` | `env.profiles_dir()` resolves to a non-existent path | "Create `<path>` or set `EXEC_ASSISTANT_PROFILES_DIR` to your actual profiles directory." |
    | `PROFILES_DIR_UNREADABLE` | Resolved path exists but cannot be opened | "Check file permissions on `<path>`. In Cowork, ensure the parent folder is added to your project's connected folders." |
    | `PROFILES_INDEX_MISSING` | `profiles_index.json` not found in profiles_dir | "Place `profiles_index.json` in `<profiles_dir>`." |
    | `PROFILES_INDEX_UNPARSEABLE` | File found but JSON parse failed (likely Google Drive placeholder or corruption) | "If on Google Drive, mark the folder 'Available offline' so files are local. Otherwise inspect `<path>` for corruption." |
    | `OUTPUT_DIR_NOT_WRITABLE` | Output dir doesn't exist or write test failed | "Create `<path>` or pass `--output-dir <writable_path>`." |
    | `MISSING_REQUIRED_MODULE` | `pypdf` or `pdfplumber` not importable | "Install with `pip install <module>` in the Python interpreter at `<sys.executable>`." |
    
    Additional codes may be added in v1.5 / v2. Codes are never renamed; deprecated codes are kept and marked.

## Acceptance criteria (v1 done)

- [ ] All 7 tests above pass
- [ ] Filling Tyler_Med_Data.pdf (or a blank copy) with Tyler's profile reproduces the 33 populated values
- [ ] Filling the same form with Fiona's profile correctly pulls Tyler as subscriber and uses Tyler's address as home
- [ ] No PII anywhere in `/skills/`, `/lib/`, `/config/config.example.json`, or any `.py` file
- [ ] CLI returns non-zero on missing env var with a one-line actionable error
- [ ] Dry-run output is human-readable
- [ ] Running `--check-env` with a valid setup returns exit 0 and `"ok": true`
- [ ] Renaming `profiles_index.json` returns exit 1 with code `PROFILES_INDEX_MISSING`
- [ ] Setting `EXEC_ASSISTANT_PROFILES_DIR` to a non-existent path returns exit 1 with code `PROFILES_DIR_MISSING`
- [ ] Uninstalling `pypdf` returns exit 1 with code `MISSING_REQUIRED_MODULE` and a fix referencing the actual `sys.executable` path
- [ ] In a synthetic sandbox env (e.g., `HOME=/sessions/test`), `sandbox_indicators` includes `"/sessions/ path present"` and `ok` remains `true` (sandbox detection alone is never an issue)
- [ ] Preflight runs in < 500 ms on a warm filesystem
- [ ] Preflight is invoked automatically at the start of every fill/extract operation (not just `--check-env`)
- [ ] Both skill SKILL.md files contain the verbatim "Layer 2" instruction block



## Setup steps (user, before first run)

```bash
# 1. Place profile JSONs at canonical location
mkdir -p "$HOME/Assets_Library/Executive-Assistant"
ln -s "/Users/tylercombs/Library/CloudStorage/GoogleDrive-tylercombs@gmail.com/Shared drives/Combslink/Assets_Library/Executive-Assistant/profiles" \
      "$HOME/Assets_Library/Executive-Assistant/profiles"

# 2. (Or, alternatively, just copy the 5 JSONs into the Google Drive location and rely on the symlink)

# 3. Optional config
mkdir -p "$HOME/.config/executive-assistant"
cp /Users/tylercombs/Dev/executive-assistant/config/config.example.json \
   "$HOME/.config/executive-assistant/config.json"

# 4. Install Python deps (system Python 3.10+)
pip install pypdf pdfplumber reportlab pytest
```

## Out-of-scope reminders (do NOT add to v1)

- No web-form browser automation
- No `bw` calls
- No OCR
- No spatial-overlay implementation (only the scaffold stub)
- No LLM-side semantic disambiguation; use deterministic synonym map only
- No SQL Server, no LiteLLM
- No multi-machine sync logic

## Schema version

This contract describes profile schema v2.0.0. If schema changes are needed during build, bump to v2.0.1 (patch) for additive changes, v2.1.0 for non-breaking schema additions, v3.0.0 for breaking changes. Always update `schema_version` in every file.
