"""
Player Stats Export Module

Generates aggregated player statistics JSON files:
- player_stats_latest.json (always current)
- player_stats_after_spieltag_XX.json (snapshots)

Sources:
- GP: Derived from lineup JSONs (only rotation==false)
- Goals/Assists/Points: From existing player stats DataFrame
- Goalie stats: From existing data when available
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd


def load_lineups_for_spieltag(season: int, spieltag: int) -> Optional[Dict[str, Any]]:
    """
    Load lineups for a spieltag from multiple sources.
    
    Priority:
    1. Separate lineups file (spieltag_XX_lineups.json)
    2. Embedded in spieltag JSON ("lineups" key)
    3. From debug section (debug.nord_matches / debug.sued_matches)
    4. Fallback: replay_matchday.json (if it has lineup data)
    
    Returns lineup dict with "teams" key, or None if not found.
    """
    # Import here to avoid circular imports
    from LigageneratorV2 import (
        DATA_ROOT, SPIELTAG_DIR, LINEUP_DIR, REPLAY_DIR, season_folder, build_line_snapshot
    )
    
    # Try separate lineups file first
    lineup_file = LINEUP_DIR / season_folder(season) / f"spieltag_{spieltag:02}_lineups.json"
    if lineup_file.exists():
        with lineup_file.open("r", encoding="utf-8") as f:
            return json.load(f)
    
    # Try spieltag JSON (embedded lineups or debug section)
    spieltag_file = SPIELTAG_DIR / season_folder(season) / f"spieltag_{spieltag:02}.json"
    if spieltag_file.exists():
        with spieltag_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
            
            # Check for direct lineups key
            if "lineups" in data:
                return {
                    "season": season,
                    "spieltag": spieltag,
                    "teams": data["lineups"]
                }
            
            # Check debug section (old format)
            debug = data.get("debug", {})
            if debug and ("nord_matches" in debug or "sued_matches" in debug):
                # Extract lineups from debug.nord_matches and debug.sued_matches
                teams = {}
                
                for match in debug.get("nord_matches", []):
                    for side in ["home", "away"]:
                        side_data = match.get(side, {})
                        team_name = side_data.get("team")
                        lineup = side_data.get("lineup", [])
                        
                        if team_name and lineup:
                            teams[team_name] = build_line_snapshot(lineup)
                
                for match in debug.get("sued_matches", []):
                    for side in ["home", "away"]:
                        side_data = match.get(side, {})
                        team_name = side_data.get("team")
                        lineup = side_data.get("lineup", [])
                        
                        if team_name and lineup:
                            teams[team_name] = build_line_snapshot(lineup)
                
                if teams:
                    return {
                        "season": season,
                        "spieltag": spieltag,
                        "teams": teams
                    }
    
    # Fallback: replay_matchday.json
    replay_file = REPLAY_DIR / season_folder(season) / f"spieltag_{spieltag:02}" / "replay_matchday.json"
    if replay_file.exists():
        with replay_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
            
            # Try to extract lineups from replay data
            # This is a fallback and might not work perfectly
            if "games" in data:
                # We could try to reconstruct lineups from replay data
                # But for now, return None
                pass
    
    return None


def _collect_gp_from_lineup(lineup_json: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Count games played from lineup JSON.
    
    Returns:
        Dict mapping player_id -> {"gp": int, "gs": int (goalies only), "pos": str}
    """
    gp_map: Dict[str, Dict[str, Any]] = {}
    
    teams = lineup_json.get("teams", {})
    
    for team_name, team_data in teams.items():
        # Forwards
        fwd_data = team_data.get("forwards", {})
        for line_key in ["line1", "line2", "line3", "line4"]:
            for player in fwd_data.get(line_key, []):
                # Only count if not rotation
                if not player.get("rotation", False):
                    pid = player["id"]
                    if pid not in gp_map:
                        gp_map[pid] = {"gp": 0, "pos": "F"}
                    gp_map[pid]["gp"] += 1
        
        # Defense
        def_data = team_data.get("defense", {})
        for pair_key in ["pair1", "pair2", "pair3"]:
            for player in def_data.get(pair_key, []):
                # Only count if not rotation
                if not player.get("rotation", False):
                    pid = player["id"]
                    if pid not in gp_map:
                        gp_map[pid] = {"gp": 0, "pos": "D"}
                    gp_map[pid]["gp"] += 1
        
        # Goalie (single object, always starter)
        goalie = team_data.get("goalie")
        if goalie and isinstance(goalie, dict):
            pid = goalie["id"]
            if pid not in gp_map:
                gp_map[pid] = {"gp": 0, "gs": 0, "pos": "G"}
            gp_map[pid]["gp"] += 1
            gp_map[pid]["gs"] = gp_map[pid].get("gs", 0) + 1
    
    return gp_map


def _map_player_name_to_id(player_stats_df: pd.DataFrame, all_teams: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    Map player names to canonical IDs.
    
    Args:
        player_stats_df: DataFrame with Player column (names)
        all_teams: List of team dicts with Players array
    
    Returns:
        Dict mapping player_name -> player_id
    """
    name_to_id: Dict[str, str] = {}

    # 1) IDs aus mapping_player_names.json (Fake-Name und Real-Name → player_id)
    mapping_file = Path("data/mapping_player_names.json")
    if mapping_file.exists():
        try:
            with mapping_file.open("r", encoding="utf-8") as f:
                mapping_data = json.load(f)
            for entry in mapping_data:
                pid = entry.get("player_id")
                if not pid:
                    continue
                fake = entry.get("fake")
                real = entry.get("real")
                if fake:
                    name_to_id[fake] = pid
                if real:
                    name_to_id[real] = pid
        except Exception as e:
            print(f"⚠️ Konnte mapping_player_names.json nicht laden: {e}")

    # 2) Fallback: IDs aus den Team-Rostern (falls vorhanden)
    for team in all_teams:
        for player in team.get("Players", []):
            name = player.get("Name")
            pid = player.get("id") or player.get("ID") or player.get("Name")
            if name and pid and name not in name_to_id:
                name_to_id[name] = pid

    return name_to_id


def build_player_stats_for_matchday(
    lineup_json: Dict[str, Any],
    player_stats_df: pd.DataFrame,
    all_teams: List[Dict[str, Any]],
    previous_stats: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Build player stats deltas for a single matchday.
    
    Args:
        lineup_json: Lineup data with teams->forwards/defense/goalie
        player_stats_df: DataFrame with Goals/Assists per player
        all_teams: List of all teams with player rosters (for ID mapping)
    
    Returns:
        Dict mapping player_id -> stats dict
    """
    # Get GP from lineups
    gp_map = _collect_gp_from_lineup(lineup_json)
    
    # Map names to IDs
    name_to_id = _map_player_name_to_id(player_stats_df, all_teams)
    
    # Create reverse mapping for names
    id_to_name = {}

    # Aus mapping_player_names.json (bevorzugt Fake-Name)
    mapping_file = Path("data/mapping_player_names.json")
    mapping_ids = set()
    if mapping_file.exists():
        try:
            with mapping_file.open("r", encoding="utf-8") as f:
                mapping_data = json.load(f)
            for entry in mapping_data:
                pid = entry.get("player_id")
                fake = entry.get("fake")
                real = entry.get("real")
                if pid:
                    mapping_ids.add(pid)
                    if fake:
                        id_to_name[pid] = fake
                    elif real:
                        id_to_name[pid] = real
        except Exception as e:
            print(f"⚠️ Konnte mapping_player_names.json nicht laden (id_to_name): {e}")

    # Fallback: aus den Team-Rostern
    for team in all_teams:
        for player in team.get("Players", []):
            pid = player.get("id") or player.get("ID") or player.get("Name")
            name = player.get("Name")
            if pid and name and pid not in id_to_name:
                id_to_name[pid] = name
    
    # Build stats map
    stats_map: Dict[str, Dict[str, Any]] = {}
    
    # First, add all players from lineups (ensures GP is always set)
    for player_name, gp_data in gp_map.items():
        canonical_id = name_to_id.get(player_name)
        # Wenn kein Mapping existiert, überspringen (verhindert Namen als ID)
        if not canonical_id:
            continue
        # Optional: Nur IDs akzeptieren, die in der Mapping-Datei stehen
        if mapping_ids and canonical_id not in mapping_ids:
            continue

        stats_map[canonical_id] = {
            "pos": gp_data["pos"],
            "gp": gp_data["gp"],
        }
        if "gs" in gp_data:
            stats_map[canonical_id]["gs"] = gp_data["gs"]
        
        # Add name if available
        if canonical_id in id_to_name:
            stats_map[canonical_id]["name"] = id_to_name[canonical_id]
    
    # Add goals/assists from player_stats_df
    for _, row in player_stats_df.iterrows():
        player_name = row.get("Player")
        if not player_name:
            continue
        
        player_id = name_to_id.get(player_name)
        if not player_id:
            continue
        if mapping_ids and player_id not in mapping_ids:
            continue
        
        goals = row.get("Goals", 0)
        assists = row.get("Assists", 0)
        
        # Calculate deltas if previous_stats available
        if previous_stats:
            prev_g = previous_stats.get(player_id, {}).get("g", 0)
            prev_a = previous_stats.get(player_id, {}).get("a", 0)
            goals = max(0, goals - prev_g)
            assists = max(0, assists - prev_a)
        
        # Only add if player exists in lineup (has GP)
        if player_id in stats_map:
            if goals > 0:
                stats_map[player_id]["g"] = int(goals)
            if assists > 0:
                stats_map[player_id]["a"] = int(assists)
            
            # Calculate points if we have both
            if goals > 0 or assists > 0:
                stats_map[player_id]["pts"] = int(goals + assists)
    
    return stats_map


def merge_into_season_player_stats(
    existing_stats: Dict[str, Dict[str, Any]],
    matchday_deltas: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """
    Merge matchday stats into season-wide stats.
    
    This is cumulative - GP increments, G/A/PTS are totals.
    
    Args:
        existing_stats: Current season stats (player_id -> stats)
        matchday_deltas: Stats from this matchday
    
    Returns:
        Updated season stats
    """
    result = dict(existing_stats)
    
    for player_id, delta in matchday_deltas.items():
        if player_id not in result:
            result[player_id] = delta.copy()
        else:
            # Merge stats
            current = result[player_id]
            
            # GP is additive
            current["gp"] = current.get("gp", 0) + delta.get("gp", 0)
            
            # GS for goalies
            if "gs" in delta:
                current["gs"] = current.get("gs", 0) + delta.get("gs", 0)
            
            # G/A/PTS are cumulative
            for stat_key in ["g", "a", "pts"]:
                if stat_key in delta:
                    current[stat_key] = current.get(stat_key, 0) + delta.get(stat_key, 0)
            
            # Position should stay the same, but ensure it's set
            if "pos" in delta:
                current["pos"] = delta["pos"]
    
    return result


def write_player_stats_files(
    base_stats_dir: Path,
    season: int,
    spieltag: int,
    stats_obj: Dict[str, Dict[str, Any]],
    all_teams: List[Dict[str, Any]],
    only_snapshot: bool = False,
    only_latest: bool = False,
) -> None:
    """
    Write player stats to JSON files (atomic writes).
    
    Writes:
    - player_stats_latest.json
    - player_stats_after_spieltag_XX.json
    
    Args:
        base_stats_dir: Base directory (e.g., STATS_DIR / season_folder)
        season: Season number
        spieltag: Matchday number
        stats_obj: Player stats mapping (player_id -> stats)
    """
    # Convert to list format with player_id field
    players_list = []
    for player_id, stats in stats_obj.items():
        player_entry = dict(stats)  # Copy stats
        player_entry["player_id"] = player_id
        players_list.append(player_entry)
    
    payload = {
        "version": 1,
        "season": season,
        "as_of_spieltag": spieltag,
        "generated_at": datetime.now().isoformat(),
        "players": players_list,
    }
    
    league_folder = base_stats_dir / "league"
    league_folder.mkdir(parents=True, exist_ok=True)
    
    # Atomic write helper
    def atomic_write(target_path: Path, data: Dict[str, Any]) -> None:
        temp_path = target_path.with_suffix(".tmp")
        with temp_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        temp_path.rename(target_path)
    
    # Write only the requested files
    latest_path = league_folder / "player_stats_latest.json"
    snapshot_path = league_folder / f"player_stats_after_spieltag_{spieltag:02}.json"

    if only_snapshot:
        atomic_write(snapshot_path, payload)
        print(f"📊 Player Stats Snapshot → {snapshot_path}")
    elif only_latest:
        atomic_write(latest_path, payload)
        print(f"📊 Player Stats gespeichert → {latest_path}")
    else:
        atomic_write(latest_path, payload)
        atomic_write(snapshot_path, payload)
        print(f"📊 Player Stats gespeichert → {latest_path}")
        print(f"📊 Player Stats Snapshot → {snapshot_path}")

    # Export players.json for web
    export_players_for_web(base_stats_dir, season, spieltag, all_teams)


def load_existing_player_stats(stats_dir: Path, season: int) -> Dict[str, Dict[str, Any]]:
    """
    Load existing player_stats_latest.json if it exists.
    
    Returns:
        Existing player stats map (player_id -> stats), or empty dict if not found
    """
    latest_path = stats_dir / f"saison_{season:02}" / "league" / "player_stats_latest.json"
    
    if not latest_path.exists():
        return {}
    
    try:
        with latest_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        
        players_list = data.get("players", [])
        
        # Convert list to dict keyed by player_id
        stats_dict = {}
        for player in players_list:
            player_id = player.get("player_id")
            if player_id:
                # Remove player_id from the stats dict since it's the key
                stats = dict(player)
                del stats["player_id"]
                stats_dict[player_id] = stats
        
        return stats_dict
    except Exception as e:
        print(f"⚠️ Could not load existing player stats: {e}")
        return {}


def export_players_for_web(
    base_stats_dir: Path,
    season: int,
    spieltag: int,
    all_teams: List[Dict[str, Any]],
) -> None:
    """
    Export players.json for web consumption.
    
    Creates /public/data/saison_XX/league/players.json with display data.
    This file contains player_id, name, slug, team_slug, portrait path.
    
    Args:
        base_stats_dir: Base directory (e.g., STATS_DIR / season_folder)
        season: Season number
        spieltag: Matchday number (for reference)
        all_teams: List of all teams with player rosters
    """
    from LigageneratorV2 import season_folder
    
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
        real_name = info.get("real_name", "")
        if display_name:
            name_to_id[display_name] = pid
        if real_name:
            name_to_id[real_name] = pid
    
    # Collect all players from teams
    players_data = []
    seen_ids = set()
    
    for team in all_teams:
        # Team-Namen aus Engine-Struktur: Feld heißt "Team"
        team_name = team.get("Team", "").strip()
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
            portrait_path = f"/images/players/{season_folder(season)}/{team_slug}/{player_slug}.png"
            
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
    public_dir = base_stats_dir.parent / "public" / "data" / season_folder(season) / "league"
    public_dir.mkdir(parents=True, exist_ok=True)
    
    # Write players.json
    players_path = public_dir / "players.json"
    with players_path.open("w", encoding="utf-8") as f:
        json.dump(players_data, f, indent=2, ensure_ascii=False)
    
    print(f"🌐 Web players exported → {players_path}")


if __name__ == "__main__":
    # Test mode
    print("Player Stats Export Module - Test Mode")
    print("This module is meant to be imported by LigageneratorV2.py")
