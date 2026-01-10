#!/usr/bin/env python3
"""
Regenerate players.json with real team data.
"""

import json
import sys
import os
from pathlib import Path

# Add the engine directory to path so we can import
sys.path.insert(0, '/opt/highspeed/pux-engine')

def season_folder(season: int) -> str:
    """Helper function to avoid import issues."""
    return f"saison_{season:02}"

def export_players_for_web_standalone(base_stats_dir: Path, season: int, spieltag: int, all_teams, team_mapping):
    """Standalone version of export_players_for_web."""
    # Load ID mapping from mapping_player_names.json
    mapping_file = Path("/opt/highspeed/pux-engine/data/mapping_player_names.json")
    name_data = []
    if mapping_file.exists():
        try:
            with mapping_file.open("r", encoding="utf-8") as f:
                name_data = json.load(f)
        except Exception as e:
            print(f"⚠️ Could not load name mapping: {e}")
    
    # Convert to dict format and find existing IDs
    id_mapping = {}
    existing_ids = set()
    for entry in name_data:
        player_id = entry.get("player_id")
        if player_id:
            id_mapping[player_id] = {
                "display_name": entry.get("fake", ""),
                "real_name": entry.get("real", "")
            }
            existing_ids.add(player_id)
    
    # Find next available ID
    def get_next_id():
        i = 1
        while f"UNK_{i:04d}" in existing_ids:
            i += 1
        return f"UNK_{i:04d}"
    
    # Create reverse mapping: display_name -> player_id for lookup
    name_to_id = {}
    for pid, info in id_mapping.items():
        display_name = info.get("display_name", "")
        real_name = info.get("real_name", "")
        if display_name:
            name_to_id[display_name] = pid
        if real_name:
            name_to_id[real_name] = pid
    
    # Collect all players from teams
    players_data = []
    seen_ids = set()
    
    for team in all_teams:
        team_code = team.get("Code", "")
        team_name = team.get("Name", "").strip()
        team_slug = team_name.lower().replace(" ", "-") if team_name else "unknown"
        
        for player in team.get("Players", []):
            player_name = player.get("Name", "").strip()
            if not player_name:
                continue
            
            # Get player_id from mapping or generate new one
            player_id = name_to_id.get(player_name)
            display_name = player_name  # Default to real name
            
            if not player_id:
                # Check if we have mapping data for this player
                for entry in name_data:
                    if entry.get("real") == player_name:
                        player_id = entry.get("player_id")
                        display_name = entry.get("fake", player_name)
                        break
                
                if not player_id:
                    # Generate new ID and add to mapping
                    player_id = get_next_id()
                    existing_ids.add(player_id)
                    
                    # Add to name_data
                    name_data.append({
                        "real": player_name,
                        "fake": player_name,  # For new players, fake = real
                        "player_id": player_id
                    })
                    display_name = player_name
            else:
                # Get the display name from mapping
                for entry in name_data:
                    if entry.get("player_id") == player_id:
                        display_name = entry.get("fake", player_name)
                        break
            
            # Create slug from display name
            player_slug = display_name.lower().replace(" ", "-").replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
            
            # Portrait path
            portrait_path = f"/images/players/{season_folder(season)}/{team_slug}/{player_slug}.png"
            
            player_entry = {
                "player_id": player_id,
                "name": display_name,  # Fake name for display
                "real_name": player_name,  # Real name for reference
                "slug": player_slug,
                "team_slug": team_slug,
                "portrait": portrait_path
            }
            
            players_data.append(player_entry)
    
    # Sort by player_id for consistency
    players_data.sort(key=lambda x: x["player_id"])
    
    # Save updated mapping_player_names.json if new players were added
    if len(name_data) > len(id_mapping):
        with mapping_file.open("w", encoding="utf-8") as f:
            json.dump(name_data, f, indent=2, ensure_ascii=False)
        print(f"💾 Updated mapping_player_names.json with {len(name_data) - len(id_mapping)} new players")
    
    # Create public directory structure
    public_dir = base_stats_dir.parent / "public" / "data" / season_folder(season) / "league"
    public_dir.mkdir(parents=True, exist_ok=True)
    
    # Write players.json
    players_path = public_dir / "players.json"
    with players_path.open("w", encoding="utf-8") as f:
        json.dump(players_data, f, indent=2, ensure_ascii=False)
    
    print(f"🌐 Web players exported → {players_path} ({len(players_data)} players)")

def regenerate_players_json():
    """Regenerate players.json with real data."""
    try:
        # Load team mapping for proper team names
        team_mapping_file = Path("/opt/highspeed/pux-engine/data/team_mapping.json")
        team_mapping = {}
        if team_mapping_file.exists():
            try:
                with team_mapping_file.open("r", encoding="utf-8") as f:
                    mapping_data = json.load(f)
                    for entry in mapping_data:
                        real_code = entry.get("real_code", "").strip()
                        highspeed_name = entry.get("highspeed_name", "").strip()
                        if real_code and highspeed_name:
                            team_mapping[real_code] = highspeed_name
            except Exception as e:
                print(f"⚠️ Could not load team mapping: {e}")
        
        # Load real teams from all_players_baseline.json
        teams_file = Path("/opt/highspeed/pux-engine/data/all_players_baseline.json")
        if not teams_file.exists():
            print("❌ Teams data not found")
            return

        with teams_file.open("r", encoding="utf-8") as f:
            teams_data = json.load(f)

        # Group players by team
        teams_dict = {}
        for player in teams_data:
            team_code = player.get("team_code") or player.get("team_name") or "FREE"  # Use team_name as fallback
            player_name = player.get("name_real", "").strip()

            if team_code not in teams_dict:
                # Get proper team name from mapping, fallback to team_code
                team_name = team_mapping.get(team_code, team_code if team_code != "FREE" else "Free Agents")
                teams_dict[team_code] = {
                    "Code": team_code,
                    "Name": team_name,
                    "Players": []
                }

            if player_name and player_name not in [p["Name"] for p in teams_dict[team_code]["Players"]]:
                teams_dict[team_code]["Players"].append({"Name": player_name})

        all_teams = list(teams_dict.values())
        print(f"📋 Loaded {len(all_teams)} teams with players")

        # Export players.json
        base_stats_dir = Path("/opt/highspeed/data/stats/saison_01")
        export_players_for_web_standalone(base_stats_dir, 1, 4, all_teams, team_mapping)  # spieltag 4 as current

        print("✅ players.json regenerated with real data")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    regenerate_players_json()