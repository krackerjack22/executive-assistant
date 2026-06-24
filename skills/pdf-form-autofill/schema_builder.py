"""LLM-powered schema mapping for entirely new fields."""

from __future__ import annotations

import json
import os
from pathlib import Path

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"
_API_TIMEOUT = 60

def _build_prompt(unmapped_fields: list[dict], profile_keys: list[str]) -> str:
    fields_lines = []
    for i, f in enumerate(unmapped_fields, 1):
        fields_lines.append(f"{i}. PDF Field: '{f['name']}' (User Answer: {f['value']!r})")
        
    fields_str = "\n".join(fields_lines)
    keys_str = ", ".join(profile_keys[:50]) # just show top-level structure to give an idea

    return f"""\
You are an intelligent data-structuring assistant.
A user is filling out a PDF form, but some fields do not exist in their current profile schema.
They have provided answers for these fields. We need to add these fields to their profile JSON.

Here is the top-level structure of their current profile (for context):
{keys_str}

Here are the entirely new fields from the PDF, along with the answers the user provided:
{fields_str}

Your task is to generate a sensible, normalized JSON "dot-path" where each of these answers should be saved in the profile.
If multiple fields are related (e.g. 'SchoolName' and 'YearsAttended'), group them under a common nested path (e.g. 'education.previous_schools.0.name' and 'education.previous_schools.0.years_attended').
Use standard snake_case naming for the keys in the dot paths. Do not use random characters. Try to group custom or entirely novel sections under a `custom_sections` root if they don't easily fit into existing top-level keys.

Respond with ONLY a JSON object mapping the exact PDF field name to your suggested dot-path. No markdown block formatting, no explanation outside the JSON:
{{
  "SchoolName": "education.previous_schools.0.name",
  "YearsAttended": "education.previous_schools.0.years_attended"
}}
"""

def generate_schema_mapping(
    unmapped_fields: list[dict],
    profile: dict,
    model: str = _DEFAULT_MODEL,
) -> dict[str, str]:
    """Call Claude to suggest dot-paths for unmapped fields."""
    if not unmapped_fields:
        return {}

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("\n[SchemaBuilder] ANTHROPIC_API_KEY not set. Cannot auto-generate schemas.")
        return {}

    try:
        import anthropic as _anthropic
    except ImportError:
        print("\n[SchemaBuilder] anthropic package not installed. Cannot auto-generate schemas.")
        return {}

    profile_keys = list(profile.keys())
    prompt = _build_prompt(unmapped_fields, profile_keys)

    print("\n[SchemaBuilder] Asking LLM to structure unmapped fields...")
    client = _anthropic.Anthropic(api_key=api_key, timeout=_API_TIMEOUT)
    try:
        message = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        print(f"\n[SchemaBuilder] LLM error: {e}")
        return {}

    raw = message.content[0].text.strip()
    
    # Try parsing
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(raw[start:end])
            except json.JSONDecodeError:
                pass
    print(f"\n[SchemaBuilder] Could not parse LLM output: {raw}")
    return {}
