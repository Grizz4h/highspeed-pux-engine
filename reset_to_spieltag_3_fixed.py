import os
import json
from pathlib import Path

# Setze Data-Root
os.environ['HIGHSPEED_DATA_ROOT'] = '/opt/highspeed/data'

from LigageneratorV2 import load_state, save_state, DATA_ROOT, STATS_DIR, season_folder
from realeTeams_live import nord_teams, sued_teams
import pandas as pd

season = 1
spieltag_reset = 3

# Lade after_spieltag_03.json
after_03_path = STATS_DIR / season_folder(season) / "league" / "after_spieltag_03.json"
if not after_03_path.exists():
    print("❌ after_spieltag_03.json nicht gefunden!")
    exit(1)

with after_03_path.open("r", encoding="utf-8") as f:
    after_03 = json.load(f)

# Lade player_stats_after_spieltag_03.json
player_03_path = STATS_DIR / season_folder(season) / "league" / "player_stats_after_spieltag_03.json"
player_stats = {}
if player_03_path.exists():
    with player_03_path.open("r", encoding="utf-8") as f:
        player_data = json.load(f)
        player_stats = {p["player_id"]: p for p in player_data.get("players", [])}

# Lade aktuellen State
state = load_state()
if not state:
    print("❌ Kein State gefunden!")
    exit(1)

# Erstelle DataFrames aus realeTeams
nord_df = pd.DataFrame(nord_teams)
sued_df = pd.DataFrame(sued_teams)

# Übertrage Punkte etc. aus after_03
for team in after_03["teams"]:
    team_name = team["Team"]
    if team_name in nord_df["Team"].values:
        nord_df.loc[nord_df["Team"] == team_name, ["Points", "Goals For", "Goals Against", "last5"]] = [
            team.get("Points", 0),
            team.get("GF", 0),
            team.get("GA", 0),
            team.get("last5", [])
        ]
    elif team_name in sued_df["Team"].values:
        sued_df.loc[sued_df["Team"] == team_name, ["Points", "Goals For", "Goals Against", "last5"]] = [
            team.get("Points", 0),
            team.get("GF", 0),
            team.get("GA", 0),
            team.get("last5", [])
        ]

# State zurücksetzen
state["spieltag"] = spieltag_reset
state["nord"] = nord_df.to_dict("records")
state["sued"] = sued_df.to_dict("records")
# state["stats"] nicht ändern, behalte die bestehende

save_state(state)
print("✅ State auf Spieltag 3 zurückgesetzt.")

# Lösche Spieltag 4 Daten
paths_to_delete = [
    DATA_ROOT / "spieltage" / season_folder(season) / "spieltag_04.json",
    DATA_ROOT / "replays" / season_folder(season) / "spieltag_04",
    STATS_DIR / season_folder(season) / "league" / "after_spieltag_04.json",
    STATS_DIR / season_folder(season) / "league" / "latest.json",
    STATS_DIR / season_folder(season) / "league" / "player_stats_after_spieltag_04.json",
    STATS_DIR / season_folder(season) / "league" / "player_stats_latest.json",
]

for p in paths_to_delete:
    if p.exists():
        if p.is_dir():
            import shutil
            shutil.rmtree(p)
            print(f"🗑️  Ordner gelöscht: {p}")
        else:
            p.unlink()
            print(f"🗑️  Datei gelöscht: {p}")

# Setze latest.json auf after_03
latest_path = STATS_DIR / season_folder(season) / "league" / "latest.json"
with latest_path.open("w", encoding="utf-8") as f:
    json.dump(after_03, f, indent=2, ensure_ascii=False)
print("✅ latest.json auf Spieltag 3 gesetzt.")

# Setze player_stats_latest.json
if player_stats:
    player_latest_path = STATS_DIR / season_folder(season) / "league" / "player_stats_latest.json"
    payload = {
        "version": 1,
        "season": season,
        "as_of_spieltag": spieltag_reset,
        "generated_at": after_03.get("generated_at", "2026-01-15T00:00:00"),
        "players": list(player_stats.values()),
    }
    with player_latest_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print("✅ player_stats_latest.json auf Spieltag 3 gesetzt.")

print("🎉 Stats erfolgreich auf Spieltag 3 zurückgedreht!")