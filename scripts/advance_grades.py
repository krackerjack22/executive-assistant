#!/usr/bin/env python3
"""
Advance grades in all profiles by one year.
Run this script once a year (e.g. over the summer) to increment school grades
for all profiles in the Assets_Library.
"""

import json
from pathlib import Path
from datetime import date

_GRADE_ORDER = [
    "kindergarten",
    "1st", "2nd", "3rd", "4th", "5th", "6th",
    "7th", "8th", "9th", "10th", "11th", "12th",
]

def advance_grade(value: str) -> str:
    if not value:
        return value
    lower = value.strip().lower()
    try:
        idx = _GRADE_ORDER.index(lower)
        return _GRADE_ORDER[idx + 1] if idx + 1 < len(_GRADE_ORDER) else "N/A"
    except ValueError:
        return value

def main():
    assets_dir = Path("/Users/tylercombs/Library/CloudStorage/GoogleDrive-tyler@ripplereturns.com/Shared drives/Combslink/Assets_Library/Executive-Assistant/profiles")
    if not assets_dir.exists():
        print(f"Error: Profiles dir not found: {assets_dir}")
        return

    today_str = date.today().isoformat()
    updated_count = 0

    for profile_file in assets_dir.glob("*.json"):
        if profile_file.name == "profiles_index.json":
            continue

        try:
            with open(profile_file, "r") as f:
                profile = json.load(f)
        except Exception as e:
            print(f"Error reading {profile_file.name}: {e}")
            continue

        changed = False

        # Advance self grade
        if "school" in profile and "grade_or_year" in profile["school"]:
            old_grade = profile["school"]["grade_or_year"]
            new_grade = advance_grade(old_grade)
            if old_grade != new_grade:
                profile["school"]["grade_or_year"] = new_grade
                print(f"[{profile_file.stem}] Self: {old_grade} -> {new_grade}")
                changed = True

        # Advance sibling grades
        if "siblings" in profile:
            for i, sib in enumerate(profile["siblings"]):
                if "grade_or_year" in sib:
                    old_grade = sib["grade_or_year"]
                    new_grade = advance_grade(old_grade)
                    if old_grade != new_grade:
                        sib["grade_or_year"] = new_grade
                        print(f"[{profile_file.stem}] Sibling {sib.get('first_name', i)}: {old_grade} -> {new_grade}")
                        changed = True

        if changed:
            profile["last_updated"] = today_str
            with open(profile_file, "w") as f:
                json.dump(profile, f, indent=2)
            updated_count += 1

    print(f"\nDone! Updated {updated_count} profiles.")

if __name__ == "__main__":
    main()
