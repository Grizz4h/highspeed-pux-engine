"""
generate_summaries.py

Lädt Replay-JSONs und generiert Zwei-Zeilen-Narratives pro Spiel,
basierend auf narrative_library.json.
"""

import json
from pathlib import Path
from typing import Dict, List, Any

from narrative import render_two_line_narrative

import os

env_root = os.environ.get("HIGHSPEED_DATA_ROOT")
if not env_root:
    raise RuntimeError("HIGHSPEED_DATA_ROOT ist nicht gesetzt.")
DATA_ROOT = Path(env_root)

DATA_DIR = DATA_ROOT
REPLAY_DIR = DATA_DIR / "replays"
LIBRARY_FILE = Path("narrative_library.json")

def load_library() -> Dict[str, Any]:
    if not LIBRARY_FILE.exists():
        raise FileNotFoundError(f"{LIBRARY_FILE} nicht gefunden.")
    with LIBRARY_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)

def process_replay_file(replay_file: Path, library: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    with replay_file.open("r", encoding="utf-8") as f:
        data = json.load(f)

    narratives = {}
    for game in data.get("games", []):
        game_id = game["game_id"]
        seed_key = game_id
        narrative = render_two_line_narrative(game, library, seed_key)
        narratives[game_id] = narrative

    return narratives

def main():
    library = load_library()

    # Finde alle replay_matchday.json
    for season_dir in REPLAY_DIR.iterdir():
        if season_dir.is_dir():
            season = season_dir.name
            for spieltag_dir in season_dir.iterdir():
                if spieltag_dir.is_dir() and spieltag_dir.name.startswith("spieltag_"):
                    replay_file = spieltag_dir / "replay_matchday.json"
                    if replay_file.exists():
                        narratives = process_replay_file(replay_file, library)
                        narrative_file = spieltag_dir / "narratives.json"
                        with narrative_file.open("w", encoding="utf-8") as f:
                            json.dump(narratives, f, indent=2, ensure_ascii=False)
                        print(f"✅ Narratives für {season}/{spieltag_dir.name} generiert.")

if __name__ == "__main__":
    main()