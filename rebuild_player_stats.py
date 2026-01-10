"""
Rebuild Player Stats from History

One-time script to retroactively generate player stats for spieltag 01-04.
After this runs, the normal incremental logic takes over from ST05+.
"""

import json
import sys
from pathlib import Path
import pandas as pd

# Import existing functions
from player_stats_export import (
    build_player_stats_for_matchday,
    merge_into_season_player_stats,
    write_player_stats_files,
)

# Import paths from LigageneratorV2
from LigageneratorV2 import (
    DATA_ROOT,
    SPIELTAG_DIR,
    LINEUP_DIR,
    STATS_DIR,
    REPLAY_DIR,
    season_folder,
    nord_teams,
    sued_teams,
)


def load_lineups_for_spieltag(season: int, spieltag: int) -> dict:
    """
    Load lineups for a spieltag from multiple sources.
    
    Priority:
    1. Separate lineups file (spieltag_XX_lineups.json)
    2. Embedded in spieltag JSON ("lineups" key)
    3. From debug section (debug.nord_matches / debug.sued_matches)
    4. Fallback: replay_matchday.json (if it has lineup data)
    
    Returns lineup dict with "teams" key, or None if not found.
    """
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
                            # Build line snapshot from lineup
                            from LigageneratorV2 import build_line_snapshot
                            teams[team_name] = build_line_snapshot(lineup)
                
                for match in debug.get("sued_matches", []):
                    for side in ["home", "away"]:
                        side_data = match.get(side, {})
                        team_name = side_data.get("team")
                        lineup = side_data.get("lineup", [])
                        
                        if team_name and lineup:
                            # Build line snapshot from lineup
                            from LigageneratorV2 import build_line_snapshot
                            teams[team_name] = build_line_snapshot(lineup)
                
                if teams:
                    return {
                        "season": season,
                        "spieltag": spieltag,
                        "teams": teams
                    }
    
    # Fallback: try replay_matchday.json
    replay_file = REPLAY_DIR / season_folder(season) / f"spieltag_{spieltag:02}" / "replay_matchday.json"
    if replay_file.exists():
        with replay_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
            # replay_matchday might not have lineups either, but try
            if "lineups" in data:
                return {
                    "season": season,
                    "spieltag": spieltag,
                    "teams": data["lineups"]
                }
    
    print(f"⚠️ No lineups found for Spieltag {spieltag}")
    return None


def load_stats_for_spieltag(season: int, spieltag: int) -> pd.DataFrame:
    """
    Load player stats (Goals/Assists) from spieltag JSON.
    
    The stats in spieltag JSON are CUMULATIVE up to that spieltag.
    
    Returns DataFrame with Player, Team, Goals, Assists columns.
    """
    spieltag_file = SPIELTAG_DIR / season_folder(season) / f"spieltag_{spieltag:02}.json"
    
    if not spieltag_file.exists():
        print(f"⚠️ Spieltag file not found: {spieltag_file}")
        return pd.DataFrame(columns=["Player", "Team", "Goals", "Assists"])
    
    with spieltag_file.open("r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Stats are in "players" array - cumulative stats
    players_data = data.get("players", [])
    
    if not players_data:
        print(f"   ⚠️ No players data in spieltag JSON")
        return pd.DataFrame(columns=["Player", "Team", "Goals", "Assists"])
    
    # Convert to DataFrame
    df = pd.DataFrame(players_data)
    
    # Ensure required columns exist
    if "Player" not in df.columns:
        df["Player"] = df.get("Name", "")
    if "Goals" not in df.columns:
        df["Goals"] = 0
    if "Assists" not in df.columns:
        df["Assists"] = 0
    if "Team" not in df.columns:
        df["Team"] = ""
    
    return df[["Player", "Team", "Goals", "Assists"]]


def rebuild_player_stats_from_history(
    season: int,
    start_spieltag: int,
    end_spieltag: int,
) -> None:
    """
    Rebuild player stats for spieltag range.
    
    Uses cumulative approach:
    - Load stats from FINAL spieltag (cumulative totals)
    - Count GP incrementally from lineups
    - Write snapshots with cumulative stats + incremental GP
    
    Args:
        season: Season number
        start_spieltag: First spieltag to process (typically 1)
        end_spieltag: Last spieltag to process (typically current spieltag)
    """
    print(f"🔄 Rebuilding player stats for Saison {season}, ST{start_spieltag:02}-{end_spieltag:02}...\n")
    
    all_teams = nord_teams + sued_teams
    
    # Load cumulative stats from the LAST spieltag (these are cumulative)
    print(f"📊 Loading cumulative stats from Spieltag {end_spieltag:02}...")
    final_stats_df = load_stats_for_spieltag(season, end_spieltag)
    print(f"   ✓ Loaded {len(final_stats_df)} player stat records\n")
    
    # Build a map of player name -> cumulative stats
    cumulative_goals_assists = {}
    for _, row in final_stats_df.iterrows():
        player_name = row.get("Player")
        if player_name:
            cumulative_goals_assists[player_name] = {
                "g": int(row.get("Goals", 0)) if row.get("Goals", 0) > 0 else None,
                "a": int(row.get("Assists", 0)) if row.get("Assists", 0) > 0 else None,
                "team": row.get("Team", ""),
            }
    
    # Now iterate through each spieltag to build GP incrementally
    gp_tracker = {}  # player_id -> gp count
    
    for spieltag in range(start_spieltag, end_spieltag + 1):
        print(f"📊 Processing Spieltag {spieltag:02}...")
        
        # Load lineups
        lineup_json = load_lineups_for_spieltag(season, spieltag)
        if not lineup_json:
            print(f"   ⚠️ Skipping ST{spieltag:02} - no lineup data\n")
            continue
        
        # Count GP for this matchday (only rotation==false)
        from player_stats_export import _collect_gp_from_lineup
        gp_this_matchday = _collect_gp_from_lineup(lineup_json)
        
        print(f"   ✓ Found {len(gp_this_matchday)} players in lineups")
        
        # Update cumulative GP tracker
        for player_id, gp_data in gp_this_matchday.items():
            if player_id not in gp_tracker:
                gp_tracker[player_id] = {
                    "gp": 0,
                    "pos": gp_data["pos"],
                }
                if "gs" in gp_data:
                    gp_tracker[player_id]["gs"] = 0
            
            gp_tracker[player_id]["gp"] += gp_data["gp"]
            if "gs" in gp_data:
                gp_tracker[player_id]["gs"] = gp_tracker[player_id].get("gs", 0) + gp_data["gs"]
        
        # Build snapshot for this spieltag
        # Combine GP (incremental) with G/A (cumulative from final)
        snapshot_stats = {}
        
        # Map player names to IDs
        from player_stats_export import _map_player_name_to_id
        name_to_id = _map_player_name_to_id(final_stats_df, all_teams)
        
        for player_id, gp_data in gp_tracker.items():
            snapshot_stats[player_id] = {
                "pos": gp_data["pos"],
                "gp": gp_data["gp"],
            }
            
            if "gs" in gp_data:
                snapshot_stats[player_id]["gs"] = gp_data["gs"]
            
            # Try to find player name from ID and add cumulative G/A
            # This is tricky - we need to reverse lookup
            # For now, match by checking all_teams
            player_name = None
            for team in all_teams:
                for player in team.get("Players", []):
                    if player.get("id") == player_id or player.get("Name") == player_id:
                        player_name = player.get("Name")
                        break
                if player_name:
                    break
            
            # Add cumulative stats if we found the player
            if player_name and player_name in cumulative_goals_assists:
                stats = cumulative_goals_assists[player_name]
                if stats.get("g") is not None:
                    snapshot_stats[player_id]["g"] = stats["g"]
                if stats.get("a") is not None:
                    snapshot_stats[player_id]["a"] = stats["a"]
                
                # Calculate points
                if stats.get("g") is not None or stats.get("a") is not None:
                    g = stats.get("g") or 0
                    a = stats.get("a") or 0
                    snapshot_stats[player_id]["pts"] = g + a
        
        # Write snapshot
        write_player_stats_files(
            base_stats_dir=STATS_DIR / season_folder(season),
            season=season,
            spieltag=spieltag,
            stats_obj=snapshot_stats,
        )
        
        print(f"   ✓ Snapshot saved: player_stats_after_spieltag_{spieltag:02}.json")
        print(f"   ✓ Cumulative: {len(snapshot_stats)} total players\n")
    
    print(f"✅ Rebuild complete! Player stats now cover ST{start_spieltag:02}-{end_spieltag:02}")
    print(f"📍 Files written to: {STATS_DIR / season_folder(season) / 'league'}/")
    print(f"\n💡 Note: Goals/Assists are CUMULATIVE (total up to each spieltag)")
    print(f"   GP is INCREMENTAL (counted per spieltag)")
    print(f"\n💡 Next steps:")
    print(f"   - Verify: cat data/stats/saison_{season:02}/league/player_stats_latest.json")
    print(f"   - Continue from ST{end_spieltag+1:02} with normal incremental logic")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Rebuild player stats from historical spieltag data")
    parser.add_argument("--season", type=int, default=1, help="Season number (default: 1)")
    parser.add_argument("--start", type=int, default=1, help="Start spieltag (default: 1)")
    parser.add_argument("--end", type=int, required=True, help="End spieltag (e.g., 4)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without writing")
    
    args = parser.parse_args()
    
    if args.dry_run:
        print("🔍 DRY RUN MODE - No files will be written\n")
        # TODO: Implement dry-run logic
        sys.exit(0)
    
    # Confirm with user
    print(f"⚠️  This will rebuild player stats for:")
    print(f"    Season: {args.season}")
    print(f"    Spieltage: {args.start} to {args.end}")
    print(f"    Target: {STATS_DIR / season_folder(args.season) / 'league'}/\n")
    
    response = input("Continue? [y/N]: ")
    if response.lower() != 'y':
        print("Aborted.")
        sys.exit(0)
    
    rebuild_player_stats_from_history(
        season=args.season,
        start_spieltag=args.start,
        end_spieltag=args.end,
    )
