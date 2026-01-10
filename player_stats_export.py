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
    
    for team in all_teams:
        for player in team.get("Players", []):
            name = player.get("Name")
            # Try multiple ID fields
            pid = player.get("id") or player.get("ID") or player.get("Name")
            if name and pid:
                name_to_id[name] = pid
    
    return name_to_id


def build_player_stats_for_matchday(
    lineup_json: Dict[str, Any],
    player_stats_df: pd.DataFrame,
    all_teams: List[Dict[str, Any]],
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
    
    # Build stats map
    stats_map: Dict[str, Dict[str, Any]] = {}
    
    # First, add all players from lineups (ensures GP is always set)
    for player_id, gp_data in gp_map.items():
        stats_map[player_id] = {
            "pos": gp_data["pos"],
            "gp": gp_data["gp"],
        }
        if "gs" in gp_data:
            stats_map[player_id]["gs"] = gp_data["gs"]
    
    # Add goals/assists from player_stats_df
    for _, row in player_stats_df.iterrows():
        player_name = row.get("Player")
        if not player_name:
            continue
        
        player_id = name_to_id.get(player_name, player_name)
        
        goals = row.get("Goals", 0)
        assists = row.get("Assists", 0)
        
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
        stats_obj: Player stats mapping
    """
    payload = {
        "version": 1,
        "season": season,
        "as_of_spieltag": spieltag,
        "generated_at": datetime.now().isoformat(),
        "players": stats_obj,
    }
    
    league_folder = base_stats_dir / "league"
    league_folder.mkdir(parents=True, exist_ok=True)
    
    # Atomic write helper
    def atomic_write(target_path: Path, data: Dict[str, Any]) -> None:
        temp_path = target_path.with_suffix(".tmp")
        with temp_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        temp_path.rename(target_path)
    
    # Write both files
    latest_path = league_folder / "player_stats_latest.json"
    snapshot_path = league_folder / f"player_stats_after_spieltag_{spieltag:02}.json"
    
    atomic_write(latest_path, payload)
    atomic_write(snapshot_path, payload)
    
    print(f"📊 Player Stats gespeichert → {latest_path}")
    print(f"📊 Player Stats Snapshot → {snapshot_path}")


def load_existing_player_stats(stats_dir: Path, season: int) -> Dict[str, Dict[str, Any]]:
    """
    Load existing player_stats_latest.json if it exists.
    
    Returns:
        Existing player stats map, or empty dict if not found
    """
    latest_path = stats_dir / f"saison_{season:02}" / "league" / "player_stats_latest.json"
    
    if not latest_path.exists():
        return {}
    
    try:
        with latest_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("players", {})
    except Exception as e:
        print(f"⚠️ Could not load existing player stats: {e}")
        return {}


if __name__ == "__main__":
    # Test mode
    print("Player Stats Export Module - Test Mode")
    print("This module is meant to be imported by LigageneratorV2.py")
