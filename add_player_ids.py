#!/usr/bin/env python3
"""
Add Player IDs to mapping_player_names.json

This script adds stable player_id fields to the existing mapping.
Format: <team_code>_<4-digit-index> where team_code is derived from the real name or assigned.

Usage:
    python add_player_ids.py
"""

import json
from pathlib import Path
from typing import Dict, List

def load_mapping() -> List[Dict]:
    """Load the current mapping."""
    mapping_file = Path("data/mapping_player_names.json")
    if not mapping_file.exists():
        print("❌ Mapping file not found")
        return []

    with mapping_file.open("r", encoding="utf-8") as f:
        return json.load(f)

def load_team_mapping() -> Dict[str, str]:
    """Load team code mapping if available."""
    team_file = Path("data/team_mapping.json")
    if not team_file.exists():
        return {}

    try:
        with team_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
            # Assuming format: {"team_name": "team_code"}
            return {v: k for k, v in data.items()} if isinstance(data, dict) else {}
    except:
        return {}

def generate_player_id(index: int, team_code: str = "UNK") -> str:
    """Generate a player ID: TEAM_XXXX"""
    return f"{team_code}_{index:04d}"

def add_player_ids():
    """Add player_id to each mapping entry."""
    mapping = load_mapping()
    if not mapping:
        return

    team_mapping = load_team_mapping()

    # Track used IDs and team counters
    used_ids = set()
    team_counters = {}

    updated_mapping = []

    for i, entry in enumerate(mapping, 1):
        real_name = entry.get("real", "").strip()
        fake_name = entry.get("fake", "").strip()

        # Try to determine team_code from real_name or use generic
        team_code = "UNK"  # Default

        # Simple heuristic: look for known team patterns in real_name
        # This is basic - you might want to improve this
        if "Nova Delta" in real_name or "Panther" in real_name:
            team_code = "NDP"
        elif "Ice" in real_name and "Tigers" in real_name:
            team_code = "ICT"
        # Add more team mappings as needed

        # Get counter for this team
        if team_code not in team_counters:
            team_counters[team_code] = 0
        team_counters[team_code] += 1

        player_id = generate_player_id(team_counters[team_code], team_code)

        # Ensure uniqueness
        while player_id in used_ids:
            team_counters[team_code] += 1
            player_id = generate_player_id(team_counters[team_code], team_code)

        used_ids.add(player_id)

        # Add player_id to entry
        entry["player_id"] = player_id
        updated_mapping.append(entry)

        if i % 100 == 0:
            print(f"Processed {i} players...")

    # Save updated mapping
    mapping_file = Path("data/mapping_player_names.json")
    with mapping_file.open("w", encoding="utf-8") as f:
        json.dump(updated_mapping, f, indent=2, ensure_ascii=False)

    print(f"✅ Added player_ids to {len(updated_mapping)} players")
    print(f"📊 Team distribution: {team_counters}")

if __name__ == "__main__":
    add_player_ids()