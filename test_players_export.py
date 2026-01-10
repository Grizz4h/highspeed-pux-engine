#!/usr/bin/env python3
"""
Test script to generate players.json for web export.
"""

import json
from pathlib import Path
from player_stats_export import export_players_for_web

def season_folder(season: int) -> str:
    """Helper function."""
    return f"saison_{season:02}"

def test_players_export():
    """Test the players.json export."""
    # Mock all_teams data (simplified)
    all_teams = [
        {
            "Name": "Nova Delta Panther",
            "Players": [
                {"Name": "Rilan Bawix"},
                {"Name": "Player Two"}
            ]
        },
        {
            "Name": "Test Team",
            "Players": [
                {"Name": "Test Player"}
            ]
        }
    ]
    
    # Test export
    base_stats_dir = Path("/opt/highspeed/data/stats/saison_01")
    
    # Load ID mapping from mapping_player_names.json
    mapping_file = Path("data/mapping_player_names.json")
    id_mapping = {}
    if mapping_file.exists():
        try:
            with mapping_file.open("r", encoding="utf-8") as f:
                name_data = json.load(f)
                # Convert to dict format
                for entry in name_data:
                    player_id = entry.get("player_id")
                    if player_id:
                        id_mapping[player_id] = {
                            "display_name": entry.get("fake", ""),
                            "real_name": entry.get("real", "")
                        }
        except Exception as e:
            print(f"⚠️ Could not load ID mapping: {e}")
    
    # Create reverse mapping: name -> player_id for lookup
    name_to_id = {}
    for pid, info in id_mapping.items():
        display_name = info.get("display_name", "")
        if display_name:
            name_to_id[display_name] = pid
    
    # Collect all players from teams
    players_data = []
    seen_ids = set()
    
    for team in all_teams:
        team_name = team.get("Name", "").strip()
        team_slug = team_name.lower().replace(" ", "-") if team_name else "unknown"
        
        for player in team.get("Players", []):
            player_name = player.get("Name", "").strip()
            if not player_name:
                continue
            
            # Get player_id from mapping or name
            player_id = name_to_id.get(player_name, player_name)
            
            # Skip duplicates
            if player_id in seen_ids:
                continue
            seen_ids.add(player_id)
            
            # Create slug from name
            player_slug = player_name.lower().replace(" ", "-").replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
            
            # Portrait path (placeholder - can be enhanced later)
            portrait_path = f"/images/players/{season_folder(1)}/{team_slug}/{player_slug}.png"
            
            player_entry = {
                "player_id": player_id,
                "name": player_name,
                "slug": player_slug,
                "team_slug": team_slug,
                "portrait": portrait_path
            }
            
            players_data.append(player_entry)
    
    # Sort by player_id for consistency
    players_data.sort(key=lambda x: x["player_id"])
    
    # Create public directory structure
    public_dir = base_stats_dir.parent / "public" / "data" / season_folder(1) / "league"
    public_dir.mkdir(parents=True, exist_ok=True)
    
    # Write players.json
    players_path = public_dir / "players.json"
    with players_path.open("w", encoding="utf-8") as f:
        json.dump(players_data, f, indent=2, ensure_ascii=False)
    
    print(f"🌐 Web players exported → {players_path}")

if __name__ == "__main__":
    test_players_export()