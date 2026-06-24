"""LLM-powered quality-assurance review of a form-fill proposal.

Sends the fill proposal and extracted form text to a Claude model and asks it
to flag contextual errors (wrong section, wrong person's data, etc.) that the
deterministic synonym mapper cannot detect on its own.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"
_API_TIMEOUT = 60
_FORM_TEXT_MAX_CHARS = 4000


def extract_form_text(pdf_path: Path) -> str:
    """Return all visible text from the PDF (section headers, labels, instructions).

    Used to give the LLM the visual/structural context that AcroForm field names
    alone don't capture (e.g. 'SIBLING INFORMATION' section header).
    """
    try:
        import pdfplumber
        pages: list[str] = []
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
        return "\n".join(pages)
    except Exception:
        return ""


def _profile_summary(profile: dict) -> str:
    """Build a minimal, non-PII subject description for the QA prompt."""
    identity = profile.get("identity") or {}
    name = identity.get("legal_name") or profile.get("profile_id", "Unknown")
    parts = [name]

    siblings = profile.get("siblings") or []
    if siblings:
        sib_lines = []
        for s in siblings:
            fn = s.get("first_name", "")
            ln = s.get("last_name", "")
            grade = s.get("grade_or_year", "")
            school = s.get("school_name", "")
            rel = s.get("relationship", "sibling")
            sib_lines.append(
                f"{fn} {ln} ({rel}, {grade}, {school})".strip(", ")
            )
        parts.append("siblings: " + "; ".join(sib_lines))

    ec = profile.get("emergency_contacts") or []
    if ec:
        ext_persons = profile.get("external_persons") or {}
        ec_names: list[str] = []
        for contact in ec[:2]:
            if contact.get("type") == "profile":
                ec_names.append(f"{contact.get('profile_id')} ({contact.get('relationship_label')})")
            elif contact.get("type") == "external_person":
                key = contact.get("external_person_key", "")
                person = ext_persons.get(key, {})
                ec_names.append(
                    f"{person.get('legal_name', key)} ({contact.get('relationship_label')})"
                )
        if ec_names:
            parts.append("emergency contacts: " + ", ".join(ec_names))

    return " | ".join(parts)


def _build_prompt(fields: list[dict], form_text: str, subject_summary: str) -> str:
    """Compose the QA review prompt."""
    filled = [
        f for f in fields
        if f.get("mapped_value") is not None and not f.get("skipped")
    ]
    fills_lines = "\n".join(
        f"  [{i + 1:03d}] {f['name']!r:45s} → {str(f.get('mapped_value', ''))!r}"
        for i, f in enumerate(filled)
    )

    form_text_excerpt = form_text[:_FORM_TEXT_MAX_CHARS]
    if len(form_text) > _FORM_TEXT_MAX_CHARS:
        form_text_excerpt += "\n[... truncated ...]"

    return f"""\
You are reviewing a PDF form fill for accuracy.

SUBJECT: {subject_summary}

FORM TEXT (extracted PDF text — includes section headers and instructions):
{form_text_excerpt}

FILLED FIELDS (numbered in form order):
{fills_lines}

Your task: identify only HIGH-CONFIDENCE contextual errors. Focus on:
1. Section mismatch — a field is inside a section asking for Person B's data, but it is
   filled with Person A (the subject's) data.
   Example: fields 87-101 are under a "SIBLING INFORMATION" header. If those fields are
   filled with the subject's own name/school/grade instead of a sibling's, that is an error.
2. Wrong-person data in parent/guardian or emergency-contact sections — sections asking for
   an adult's information filled with the student's data.

Do NOT flag:
- Missing / skipped fields (value=None is intentional).
- Minor formatting differences.
- Uncertain matches — only report when you are confident it is wrong.

Respond with ONLY a JSON object — no markdown, no preamble, no explanation outside the JSON:
{{
  "issues": [
    {{
      "field_name": "exact PDF field name string",
      "current_value": "what was filled in",
      "suggested_value": "what it should be, or null to leave blank",
      "reason": "one concise sentence",
      "confidence": "high"
    }}
  ]
}}

Return {{"issues": []}} if no high-confidence errors are found.
"""


def review_fills(
    fields: list[dict],
    pdf_path: Path,
    profile: dict,
    model: str = _DEFAULT_MODEL,
) -> list[dict]:
    """Call Claude to review the fill proposal for contextual errors.

    Args:
        fields: The ``fields`` list from the acroform.fill result dict.
        pdf_path: Path to the template PDF (used for text extraction).
        profile: The resolved profile dict for the subject.
        model: Claude model ID to use for the review.

    Returns:
        List of issue dicts, each with keys:
            field_name, current_value, suggested_value, reason, confidence.

    Raises:
        RuntimeError: if ANTHROPIC_API_KEY is not set or anthropic is not installed.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set. Export it to use --qa.\n"
            "  export ANTHROPIC_API_KEY=sk-ant-..."
        )

    try:
        import anthropic as _anthropic
    except ImportError:
        raise RuntimeError(
            "anthropic package not installed.\n"
            "  /usr/bin/python3 -m pip install anthropic"
        )

    form_text = extract_form_text(pdf_path)
    subject = _profile_summary(profile)
    prompt = _build_prompt(fields, form_text, subject)

    client = _anthropic.Anthropic(api_key=api_key, timeout=_API_TIMEOUT)
    message = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    return _parse_issues(raw)


def _parse_issues(raw: str) -> list[dict]:
    """Extract the issues list from the model's JSON response."""
    # Try direct parse first
    try:
        result = json.loads(raw)
        return result.get("issues", [])
    except json.JSONDecodeError:
        pass
    # Fall back to extracting the outermost JSON object
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start != -1 and end > start:
        try:
            result = json.loads(raw[start:end])
            return result.get("issues", [])
        except json.JSONDecodeError:
            pass
    return []
