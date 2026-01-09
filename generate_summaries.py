"""
generate_summaries.py

Lädt Replay-JSONs und generiert Zwei-Zeilen-Narratives pro Spiel,
basierend auf narrative_engine.py mit anti-repeat memory.
"""

import json
from pathlib import Path
from typing import Dict, List, Any

from narrative_engine import build_narratives_for_matchday

import os

env_root = os.environ.get("HIGHSPEED_DATA_ROOT")
if not env_root:
    raise RuntimeError("HIGHSPEED_DATA_ROOT ist nicht gesetzt.")
DATA_ROOT = Path(env_root)

DATA_DIR = DATA_ROOT
REPLAY_DIR = DATA_DIR / "replays"
STATS_DIR = DATA_DIR / "stats"

def load_spieltag_json(replay_file: Path) -> Dict[str, Any]:
    with replay_file.open("r", encoding="utf-8") as f:
        return json.load(f)

def load_latest_json(season: int) -> Dict[str, Any]:
    latest_path = STATS_DIR / f"saison_{season:02d}" / "league" / "latest.json"
    if not latest_path.exists():
        # Fallback: create minimal latest_json
        return {"teams": {}}
    with latest_path.open("r", encoding="utf-8") as f:
        return json.load(f)

def main():
    # Finde alle replay_matchday.json
    for season_dir in REPLAY_DIR.iterdir():
        if season_dir.is_dir() and season_dir.name.startswith("saison_"):
            season_str = season_dir.name.split("_")[1]
            season = int(season_str)
            latest_json = load_latest_json(season)
            
            for spieltag_dir in season_dir.iterdir():
                if spieltag_dir.is_dir() and spieltag_dir.name.startswith("spieltag_"):
                    spieltag_str = spieltag_dir.name.split("_")[1]
                    spieltag = int(spieltag_str)
                    
                    replay_file = spieltag_dir / "replay_matchday.json"
                    if replay_file.exists():
                        spieltag_json = load_spieltag_json(replay_file)
                        
                        # Use new narrative engine
                        memory_path = spieltag_dir / "narrative_memory.json"
                        narratives = build_narratives_for_matchday(
                            spieltag_json, latest_json, season, spieltag, memory_path
                        )
                        
                        narrative_file = spieltag_dir / "narratives.json"
                        with narrative_file.open("w", encoding="utf-8") as f:
                            json.dump(narratives, f, indent=2, ensure_ascii=False)
                        print(f"✅ Narratives für {season_dir.name}/{spieltag_dir.name} generiert.")

if __name__ == "__main__":
    main()