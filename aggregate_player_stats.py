"""
Aggregate player stats from match events.

This script reads all match JSON files for a season up to a certain spieltag,
aggregates goals and assists from the events, and outputs a DataFrame-like structure
that can be used by rebuild_player_stats.py.
"""

import json
import os
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any

# Set the data root
DATA_ROOT = Path("/opt/highspeed/data")
REPLAY_DIR = DATA_ROOT / "replays"

def load_match_events(season: int, spieltag: int) -> List[Dict[str, Any]]:
    """Load all events from all matches in a spieltag."""
    season_dir = REPLAY_DIR / f"saison_{season:02d}" / f"spieltag_{spieltag:02d}"
    events = []
    
    if not season_dir.exists():
        print(f"Spieltag directory not found: {season_dir}")
        return []
    
    for match_file in season_dir.glob("*.json"):
        if match_file.name == "replay_matchday.json" or match_file.name == "narrative_memory.json" or match_file.name == "narratives.json":
            continue
        
        try:
            with open(match_file, 'r', encoding='utf-8') as f:
                match_data = json.load(f)
            
            if "events" in match_data:
                events.extend(match_data["events"])
        except Exception as e:
            print(f"Error loading {match_file}: {e}")
    
    return events

def aggregate_stats_from_events(events: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    """Aggregate goals and assists from events."""
    player_stats = defaultdict(lambda: {"goals": 0, "assists": 0})
    
    for event in events:
        if event.get("type") == "goal" and event.get("result") == "goal":
            # Goal scorer
            scorer = event.get("player_main")
            if scorer:
                player_stats[scorer]["goals"] += 1
            
            # Assists (secondary player)
            assister = event.get("player_secondary")
            if assister:
                player_stats[assister]["assists"] += 1
    
    return dict(player_stats)

def get_cumulative_stats_up_to_spieltag(season: int, upto_spieltag: int) -> Dict[str, Dict[str, int]]:
    """Get cumulative stats up to a certain spieltag."""
    cumulative_stats = defaultdict(lambda: {"goals": 0, "assists": 0})
    
    for st in range(1, upto_spieltag + 1):
        print(f"Aggregating events from Spieltag {st}...")
        events = load_match_events(season, st)
        st_stats = aggregate_stats_from_events(events)
        
        for player, stats in st_stats.items():
            cumulative_stats[player]["goals"] += stats["goals"]
            cumulative_stats[player]["assists"] += stats["assists"]
    
    return dict(cumulative_stats)

def save_cumulative_stats(season: int, upto_spieltag: int, stats: Dict[str, Dict[str, int]]):
    """Save the cumulative stats to a JSON file in stats/ directory."""
    # Convert to the format expected by rebuild_player_stats.py
    players_data = []
    for player_name, player_stats in stats.items():
        players_data.append({
            "Player": player_name,
            "Team": "",  # We don't have team info here
            "Goals": player_stats["goals"],
            "Assists": player_stats["assists"]
        })
    
    output_file = Path("/opt/highspeed/data/stats") / f"saison_{season:02d}" / "league" / f"cumulative_stats_up_to_st{upto_spieltag:02d}.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({"players": players_data}, f, indent=2, ensure_ascii=False)
    
    print(f"Saved cumulative stats to {output_file}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Aggregate player stats from match events")
    parser.add_argument("--season", type=int, default=1, help="Season number")
    parser.add_argument("--upto", type=int, required=True, help="Up to which spieltag to aggregate")
    
    args = parser.parse_args()
    
    print(f"Aggregating stats for Season {args.season}, up to Spieltag {args.upto}...")
    cumulative_stats = get_cumulative_stats_up_to_spieltag(args.season, args.upto)
    save_cumulative_stats(args.season, args.upto, cumulative_stats)
    print("Done!")