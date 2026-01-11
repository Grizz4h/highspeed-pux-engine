import json
from pathlib import Path

DATA_ROOT = Path("/opt/highspeed/data")
spieltag_path = DATA_ROOT / "spieltage/saison_01/spieltag_03.json"
reale_teams_path = Path("/opt/highspeed/pux-engine/realeTeams_live.py")

# Teams laden
def load_teams():
    import importlib.util
    spec = importlib.util.spec_from_file_location("realeTeams_live", str(reale_teams_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.nord_teams + mod.sued_teams

def get_team_names(teams):
    return set(t["Team"] for t in teams)

def get_player_numbers(teams):
    return {(t["Team"], p["Name"], p["Number"]) for t in teams for p in t["Players"]}

with spieltag_path.open("r", encoding="utf-8") as f:
    data = json.load(f)

teams = load_teams()
team_names = get_team_names(teams)
player_numbers = get_player_numbers(teams)

# Check 1: Alle Spiele haben gültige Teams
games_ok = all(g["home"] in team_names and g["away"] in team_names for g in data["games"])

# Check 2: Alle Top-Scorer sind Spieler aus dem richtigen Team
scorer_ok = True
for s in data["top_scorer"]:
    if (s["Team"], s["Player"], s["Number"]) not in player_numbers:
        print(f"Fehler: Top-Scorer {s['Player']} ({s['Team']}, #{s['Number']}) nicht im Team!")
        scorer_ok = False

# Check 3: Events nur mit Spielern aus dem jeweiligen Team
for ev in data["events"]:
    if "scorer" in ev and ev["scorer"]:
        found = any((ev["team"], ev["scorer"], p["Number"]) in player_numbers for t in teams if t["Team"] == ev["team"] for p in t["Players"] if p["Name"] == ev["scorer"])
        if not found:
            print(f"Fehler: Event-Scorer {ev['scorer']} nicht im Team {ev['team']}")
            scorer_ok = False
    if "assist" in ev and ev["assist"]:
        found = any((ev["team"], ev["assist"], p["Number"]) in player_numbers for t in teams if t["Team"] == ev["team"] for p in t["Players"] if p["Name"] == ev["assist"])
        if not found:
            print(f"Fehler: Event-Assist {ev['assist']} nicht im Team {ev['team']}")
            scorer_ok = False

if games_ok and scorer_ok:
    print("Konsistenz-Check bestanden: Alle Teams, Spieler und Events sind korrekt zugeordnet.")
else:
    print("Konsistenz-Check FEHLER: Siehe Details oben.")
