#!/usr/bin/env python3
"""
Ensure player IDs are stable and persisted.
"""

import json
from pathlib import Path

def ensure_stable_ids():
    """Ensure all players have stable IDs."""
    mapping_file = Path("data/mapping_player_names.json")
    if not mapping_file.exists():
        print("❌ No player name mapping found")
        return
    
    with mapping_file.open("r", encoding="utf-8") as f:
        name_data = json.load(f)
    
    # Extract IDs
    ids = []
    for entry in name_data:
        player_id = entry.get("player_id")
        if player_id:
            ids.append(player_id)
    
    # Check for duplicates
    unique_ids = set(ids)
    
    if len(ids) != len(unique_ids):
        print("❌ Duplicate player IDs found!")
        duplicates = [id for id in ids if ids.count(id) > 1]
        print(f"Duplicates: {duplicates}")
        return
    
    print(f"✅ All {len(ids)} player IDs are unique and stable")
    
    # Check that all IDs follow the expected format
    invalid_ids = []
    for pid in ids:
        if not (pid.startswith("UNK_") and len(pid) == 8 and pid[4:].isdigit() and len(pid[4:]) == 4):
            invalid_ids.append(pid)
    
    if invalid_ids:
        print(f"⚠️ {len(invalid_ids)} IDs don't follow UNK_XXXX format: {invalid_ids[:5]}...")
    else:
        print("✅ All IDs follow the UNK_XXXX format")

if __name__ == "__main__":
    ensure_stable_ids()