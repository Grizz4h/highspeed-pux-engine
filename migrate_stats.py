#!/usr/bin/env python3
"""
Migrate existing player stats to new format with player_id field.

This script converts existing player_stats_latest.json and snapshots
from the old format (player_id as key) to the new format (player_id as field in list).
"""

import json
from pathlib import Path
from typing import Dict, Any

def load_id_mapping() -> Dict[str, Dict[str, str]]:
    """Load player ID mapping from mapping_player_names.json."""
    mapping_file = Path("data/mapping_player_names.json")
    if not mapping_file.exists():
        print("❌ Player name mapping not found")
        return {}

    with mapping_file.open("r", encoding="utf-8") as f:
        name_data = json.load(f)

    # Convert to dict format
    id_mapping = {}
    for entry in name_data:
        player_id = entry.get("player_id")
        if player_id:
            id_mapping[player_id] = {
                "display_name": entry.get("fake", ""),
                "real_name": entry.get("real", "")
            }

    return id_mapping

def migrate_stats_file(stats_file: Path, id_mapping: Dict[str, Dict[str, str]]) -> bool:
    """Migrate a single stats file to new format."""
    if not stats_file.exists():
        return False

    try:
        with stats_file.open("r", encoding="utf-8") as f:
            data = json.load(f)

        players = data.get("players", [])
        changed = False

        # Create reverse mapping: display_name -> player_id
        name_to_id = {}
        for pid, info in id_mapping.items():
            display_name = info.get("display_name", "")
            if display_name:
                name_to_id[display_name] = pid

        for player in players:
            current_id = player.get("player_id", "")
            
            # If player_id is a name (not a proper ID like UNK_XXXX), try to map it
            if current_id and not current_id.startswith(("UNK_", "NDP_", "ICT_")):
                # This is likely a name being used as ID
                if current_id in name_to_id:
                    new_id = name_to_id[current_id]
                    player["player_id"] = new_id
                    changed = True
                    print(f"  Updated ID: {current_id} → {new_id}")
            
            # Add name field if missing
            if "name" not in player and current_id in id_mapping:
                player["name"] = id_mapping[current_id].get("display_name", "")
                changed = True

        if changed:
            # Save migrated data
            with stats_file.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            print(f"✅ Migrated {stats_file.name}")
            return True
        else:
            print(f"ℹ️  {stats_file.name} already up to date")
            return False

    except Exception as e:
        print(f"❌ Error migrating {stats_file}: {e}")
        return False

def migrate_all_stats():
    """Migrate all player stats files."""
    print("🚀 Starting stats migration...")

    id_mapping = load_id_mapping()
    if not id_mapping:
        return

    # Find all stats files in both locations
    search_paths = [
        Path("stats"),  # Local
        Path("/opt/highspeed/data/stats")  # Data repo
    ]
    
    migrated_count = 0

    for stats_dir in search_paths:
        if stats_dir.exists():
            for json_file in stats_dir.rglob("*.json"):
                if "player_stats" in json_file.name:
                    if migrate_stats_file(json_file, id_mapping):
                        migrated_count += 1

    print(f"🎉 Migration complete! Migrated {migrated_count} files.")

if __name__ == "__main__":
    migrate_all_stats()