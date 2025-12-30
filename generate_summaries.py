"""
generate_summaries.py

Lädt Replay-JSONs und generiert Zwei-Satz-Zusammenfassungen pro Spiel,
basierend auf summary_templates.json.
"""

import json
import random
from pathlib import Path
from typing import Dict, List, Any

DATA_DIR = Path("data")
REPLAY_DIR = DATA_DIR / "replays"
TEMPLATES_FILE = Path("summary_templates.json")

def load_templates() -> Dict[str, List[str]]:
    if not TEMPLATES_FILE.exists():
        raise FileNotFoundError(f"{TEMPLATES_FILE} nicht gefunden.")
    with TEMPLATES_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)

def generate_summary(events: List[Dict[str, Any]], g_home: int, g_away: int, overtime: bool, shootout: bool, templates: Dict[str, List[str]]) -> str:
    if not events:
        return f"Spiel endet {g_home}:{g_away}."

    # Sammle Goals
    goals = [e for e in events if e.get("type") == "goal"]
    if not goals:
        return f"Spiel endet {g_home}:{g_away}."

    # Wähle zufällig ein Goal
    goal = random.choice(goals)
    scorer = goal.get("scorer", "Unbekannt")
    score = f"{g_home}:{g_away}" if g_home > g_away else f"{g_away}:{g_home}"

    goal_sentence = random.choice(templates["goal_templates"]).format(scorer=scorer, score=score)

    # Assist, wenn vorhanden
    assist = goal.get("assist")
    if assist:
        assist_sentence = random.choice(templates["assist_templates"]).format(assist=assist)
        first_sentence = f"{goal_sentence} {assist_sentence}"
    else:
        first_sentence = goal_sentence

    # Zweiter Satz: Ergebnis
    result = f"{g_home}:{g_away}"
    if shootout:
        summary = random.choice(templates["so_templates"]).format(result=result)
    elif overtime:
        summary = random.choice(templates["ot_templates"]).format(result=result)
    else:
        summary = random.choice(templates["summary_templates"]).format(result=result)

    return f"{first_sentence} {summary}"

def process_replay_file(replay_file: Path, templates: Dict[str, List[str]]) -> Dict[str, str]:
    with replay_file.open("r", encoding="utf-8") as f:
        data = json.load(f)

    summaries = {}
    for game in data.get("games", []):
        game_id = game["game_id"]
        events = game.get("events", [])
        g_home = game["g_home"]
        g_away = game["g_away"]
        overtime = game.get("overtime", False)
        shootout = game.get("shootout", False)

        summary = generate_summary(events, g_home, g_away, overtime, shootout, templates)
        summaries[game_id] = summary

    return summaries

def main():
    templates = load_templates()

    # Finde alle replay_matchday.json
    for season_dir in REPLAY_DIR.iterdir():
        if season_dir.is_dir():
            season = season_dir.name
            for spieltag_dir in season_dir.iterdir():
                if spieltag_dir.is_dir() and spieltag_dir.name.startswith("spieltag_"):
                    replay_file = spieltag_dir / "replay_matchday.json"
                    if replay_file.exists():
                        summaries = process_replay_file(replay_file, templates)
                        summary_file = spieltag_dir / "summaries.json"
                        with summary_file.open("w", encoding="utf-8") as f:
                            json.dump(summaries, f, indent=2, ensure_ascii=False)
                        print(f"✅ Summaries für {season}/{spieltag_dir.name} generiert.")

if __name__ == "__main__":
    main()