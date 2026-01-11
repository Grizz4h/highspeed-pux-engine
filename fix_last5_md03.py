import os
import json
from pathlib import Path
from LigageneratorV2 import season_folder, SPIELTAG_DIR, STATS_DIR

# Setze das Data-Root für die Engine
os.environ['HIGHSPEED_DATA_ROOT'] = '/opt/highspeed/data'

season = 1
spieltag = 3

# Lade last5 aus after_spieltag_02.json
after_02_path = STATS_DIR / season_folder(season) / 'league' / 'after_spieltag_02.json'
last5_per_team = {}
if after_02_path.exists():
    with open(after_02_path, 'r', encoding='utf-8') as f:
        after_02 = json.load(f)
    for team in after_02['teams']:
        last5_per_team[team['team']] = team.get('last5', [])
else:
    # Fallback: aus after_01 oder leer
    after_01_path = STATS_DIR / season_folder(season) / 'league' / 'after_spieltag_01.json'
    if after_01_path.exists():
        with open(after_01_path, 'r', encoding='utf-8') as f:
            after_01 = json.load(f)
        for team in after_01['teams']:
            last5_per_team[team['team']] = team.get('last5', [])
    else:
        # Initial leer
        pass

# Füge Ergebnisse von MD3 hinzu
spieltag_path = SPIELTAG_DIR / season_folder(season) / f'spieltag_{spieltag:02}.json'
with open(spieltag_path, 'r', encoding='utf-8') as f:
    data = json.load(f)
for game in data.get('results', []):
    home = game['home']
    away = game['away']
    g_home = game['g_home']
    g_away = game['g_away']
    if g_home > g_away:
        result_home = 'W'
        result_away = 'L'
    elif g_away > g_home:
        result_home = 'L'
        result_away = 'W'
    else:
        result_home = 'T'
        result_away = 'T'
    if home not in last5_per_team:
        last5_per_team[home] = []
    if away not in last5_per_team:
        last5_per_team[away] = []
    last5_per_team[home].append(result_home)
    last5_per_team[away].append(result_away)

# Lade latest.json und aktualisiere last5
latest_path = STATS_DIR / season_folder(season) / 'league' / 'latest.json'
with open(latest_path, 'r', encoding='utf-8') as f:
    latest = json.load(f)

for team in latest['teams']:
    team_name = team['Team']
    team['last5'] = last5_per_team.get(team_name, [])

# Speichere latest.json zurück
with open(latest_path, 'w', encoding='utf-8') as f:
    json.dump(latest, f, indent=2, ensure_ascii=False)

# Erstelle after_spieltag_03.json mit gleichem Inhalt wie latest
after_03_path = STATS_DIR / season_folder(season) / 'league' / 'after_spieltag_03.json'
with open(after_03_path, 'w', encoding='utf-8') as f:
    json.dump(latest, f, indent=2, ensure_ascii=False)

print('✅ last5 in after_spieltag_03.json und latest.json wurde sauber aufbauend auf MD1-2 korrigiert.')
