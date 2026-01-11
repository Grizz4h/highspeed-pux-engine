import json
import random
from pathlib import Path

# Pfade
DATA_ROOT = Path("/opt/highspeed/data")
spieltag_path = DATA_ROOT / "spieltage/saison_01/spieltag_03.json"
reale_teams_path = Path("/opt/highspeed/pux-engine/realeTeams_live.py")

# Hilfsfunktion: Teams und Spieler laden (aus realeTeams_live.py)
def load_teams():
    import importlib.util
    spec = importlib.util.spec_from_file_location("realeTeams_live", str(reale_teams_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.nord_teams + mod.sued_teams

# Hilfsfunktion: Spieler für ein Team
def get_players_for_team(teams, team_name):
    for t in teams:
        if t["Team"] == team_name:
            return t["Players"]
    return []

# Lade Spieltag
with spieltag_path.open("r", encoding="utf-8") as f:
    data = json.load(f)

teams = load_teams()
random.seed(103)  # Fester Seed für Determinismus

top_scorer = []
events = []

for game in data["games"]:
    home_players = get_players_for_team(teams, game["home"])
    away_players = get_players_for_team(teams, game["away"])
    # Dummy-Logik: Zufällige Spieler als Torschützen/Assists
    for i in range(game["g_home"]):
        scorer = random.choice(home_players)
        assist = random.choice([p for p in home_players if p != scorer]) if len(home_players) > 1 else scorer
        top_scorer.append({
            "Player": scorer["Name"],
            "Team": game["home"],
            "Number": scorer["Number"],
            "Goals": 1,
            "Assists": 0 if assist == scorer else 1
        })
        events.append({
            "team": game["home"],
            "scorer": scorer["Name"],
            "assist": assist["Name"] if assist != scorer else None
        })
    for i in range(game["g_away"]):
        scorer = random.choice(away_players)
        assist = random.choice([p for p in away_players if p != scorer]) if len(away_players) > 1 else scorer
        top_scorer.append({
            "Player": scorer["Name"],
            "Team": game["away"],
            "Number": scorer["Number"],
            "Goals": 1,
            "Assists": 0 if assist == scorer else 1
        })
        events.append({
            "team": game["away"],
            "scorer": scorer["Name"],
            "assist": assist["Name"] if assist != scorer else None
        })

# Aggregiere Top-Scorer nach Spieler
from collections import defaultdict
agg = defaultdict(lambda: {"Goals": 0, "Assists": 0, "Player": None, "Team": None, "Number": None})
for entry in top_scorer:
    key = (entry["Player"], entry["Team"], entry["Number"])
    agg[key]["Player"] = entry["Player"]
    agg[key]["Team"] = entry["Team"]
    agg[key]["Number"] = entry["Number"]
    agg[key]["Goals"] += entry["Goals"]
    agg[key]["Assists"] += entry["Assists"]

data["top_scorer"] = list(agg.values())
data["events"] = events

with spieltag_path.open("w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("spieltag_03.json wurde mit deterministischen Torschützen und Events befüllt.")
