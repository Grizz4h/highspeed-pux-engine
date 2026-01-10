#!/usr/bin/env python3
"""
Create Player ID Mapping

Creates a new mapping file with player_id as key.
Format: player_id -> {display_name, real_name, etc.}
"""

import json
from pathlib import Path

def create_id_mapping():
    """Create player_id -> info mapping."""
    mapping_file = Path("data/mapping_player_names.json")
    if not mapping_file.exists():
        print("❌ Mapping file not found")
        return

    with mapping_file.open("r", encoding="utf-8") as f:
        data = json.load(f)

    id_mapping = {}
    for entry in data:
        player_id = entry.get("player_id")
        if player_id:
            id_mapping[player_id] = {
                "display_name": entry.get("fake", ""),
                "real_name": entry.get("real", ""),
            }

    # Save new mapping
    id_mapping_file = Path("data/player_id_mapping.json")
    with id_mapping_file.open("w", encoding="utf-8") as f:
        json.dump(id_mapping, f, indent=2, ensure_ascii=False)

    print(f"✅ Created ID mapping with {len(id_mapping)} players")

if __name__ == "__main__":
    create_id_mapping()