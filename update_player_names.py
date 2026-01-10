#!/usr/bin/env python3
"""
Update Player Names Script

Tracks changes in mapping_player_names.json and updates all player names in relevant JSON files.

Usage:
    python update_player_names.py

The script will:
1. Load current mapping from data/mapping_player_names.json
2. Load previous mapping from data/.mapping_backup.json (if exists)
3. Find changed fake names
4. Update all relevant JSON files with the changes
5. Save current mapping as backup for next run
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Tuple

# Directories to search for JSON files containing player names
SEARCH_DIRS = [
    "spieltage",
    "lineups",
    "stats",
    "replays",
    "saves",
    "data/lineups",
    "data/playoffs",
    "data/replays",
    "data/saves",
    "data/schedules",
    "data/spieltage",
    "data/stats"
]

BACKUP_FILE = Path("data/.mapping_backup.json")

def load_mapping(file_path: Path) -> Dict[str, str]:
    """Load the player name mapping (real -> fake)."""
    if not file_path.exists():
        print(f"❌ Mapping file not found: {file_path}")
        return {}

    with file_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    real_to_fake = {}
    for entry in data:
        real = entry.get("real", "").strip()
        fake = entry.get("fake", "").strip()
        if real and fake:
            real_to_fake[real] = fake

    return real_to_fake

def save_mapping(file_path: Path, mapping: Dict[str, str]) -> None:
    """Save the mapping to file."""
    data = [{"real": real, "fake": fake} for real, fake in mapping.items()]
    with file_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def find_changed_fakes(current: Dict[str, str], previous: Dict[str, str]) -> Dict[str, str]:
    """Find changed fake names: old_fake -> new_fake"""
    changed = {}
    for real, new_fake in current.items():
        if real in previous and previous[real] != new_fake:
            old_fake = previous[real]
            changed[old_fake] = new_fake
    return changed

def find_json_files() -> List[Path]:
    """Find all JSON files in the search directories."""
    json_files = []
    for dir_name in SEARCH_DIRS:
        dir_path = Path(dir_name)
        if dir_path.exists():
            for json_file in dir_path.rglob("*.json"):
                json_files.append(json_file)
    return json_files

def update_names_in_file(file_path: Path, changes: Dict[str, str]) -> bool:
    """Update names in a single file."""
    if not changes:
        return False

    try:
        with file_path.open("r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"⚠️  Could not read {file_path}: {e}")
        return False

    original_content = content

    for old_fake, new_fake in changes.items():
        content = content.replace(f'"{old_fake}"', f'"{new_fake}"')  # JSON strings
        content = content.replace(f"'{old_fake}'", f"'{new_fake}'")  # If single quotes

    if content != original_content:
        try:
            with file_path.open("w", encoding="utf-8") as f:
                f.write(content)
            print(f"✅ Updated {file_path}")
            return True
        except Exception as e:
            print(f"⚠️  Could not write {file_path}: {e}")
            return False
    return False

def main():
    print("🚀 Starting player name update...")

    mapping_file = Path("data/mapping_player_names.json")
    current_mapping = load_mapping(mapping_file)
    if not current_mapping:
        return

    previous_mapping = load_mapping(BACKUP_FILE) if BACKUP_FILE.exists() else {}

    changed_fakes = find_changed_fakes(current_mapping, previous_mapping)

    if changed_fakes:
        print(f"📋 Found {len(changed_fakes)} changed fake names:")
        for old, new in changed_fakes.items():
            print(f"  {old} → {new}")
    else:
        print("📋 No changes detected in mapping.")

    json_files = find_json_files()
    print(f"🔍 Found {len(json_files)} JSON files to check")

    updated_count = 0
    for json_file in json_files:
        if update_names_in_file(json_file, changed_fakes):
            updated_count += 1

    print(f"🎉 Update complete! Updated {updated_count} files.")

    # Save current mapping as backup
    save_mapping(BACKUP_FILE, current_mapping)
    print(f"💾 Saved current mapping as backup to {BACKUP_FILE}")

if __name__ == "__main__":
    main()