import os
import json
import pandas as pd
from pathlib import Path
from LigageneratorV2 import season_folder, SPIELTAG_DIR, STATS_DIR, SAVEFILE, nord_teams, sued_teams, _export_tables, _save_json

# Setze das Data-Root für die Engine
os.environ['HIGHSPEED_DATA_ROOT'] = '/opt/highspeed/data'

season = 1
spieltag = 3
spieltag_path = SPIELTAG_DIR / season_folder(season) / f'spieltag_{spieltag:02}.json'

# Lade canonicales Spieltag-JSON
with open(spieltag_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

# Lade Savegame für aktuelle Tabellen
with open(SAVEFILE, 'r', encoding='utf-8') as f:
    state = json.load(f)

nord = pd.DataFrame(state['nord'])
sued = pd.DataFrame(state['sued'])
stats_df = pd.DataFrame(state['stats'])

# Baue das richtige Engine-Format für spieltag_03.json
results = []
# Conferences für MD03: 5 Nord, 5 Süd (wie in anderen Spieltagen)
conferences = ["Nord", "Nord", "Nord", "Nord", "Nord", "Süd", "Süd", "Süd", "Süd", "Süd"]
for i, game in enumerate(data.get('results', data.get('games', []))):
    conference = conferences[i] if i < len(conferences) else "Süd"
    results.append({
        'home': game['home'],
        'away': game['away'],
        'g_home': game['g_home'],
        'g_away': game['g_away'],
        'conference': conference,
        'overtime': game.get('overtime', False),
        'shootout': game.get('shootout', False),
    })

payload = {
    'timestamp': '2026-01-11T00:00:00',  # Dummy-Timestamp
    'saison': season,
    'spieltag': spieltag,
    'results': results,
    'debug': data.get('debug', {}),
    'lineups': data.get('lineups', {}),
    **_export_tables(nord, sued, stats_df),
}

# Überschreibe spieltag_03.json mit richtigem Format
_save_json(SPIELTAG_DIR / season_folder(season), f'spieltag_{spieltag:02}.json', payload)

# Erstelle after_spieltag_03.json und latest.json in stats/
teams = []
for team in payload['tabelle_nord'] + payload['tabelle_sued']:
    team_dict = dict(team)
    team_name = team['Team']
    nord_row = nord[nord['Team'] == team_name]
    if not nord_row.empty:
        team_dict['last5'] = nord_row['last5'].iloc[0] if 'last5' in nord_row.columns else []
    else:
        sued_row = sued[sued['Team'] == team_name]
        if not sued_row.empty:
            team_dict['last5'] = sued_row['last5'].iloc[0] if 'last5' in sued_row.columns else []
        else:
            team_dict['last5'] = []
    teams.append(team_dict)

after_payload = {
    'season': season,
    'upto_matchday': spieltag,
    'generated_at': '2026-01-11T00:00:00',
    'teams': teams,
}

_save_json(STATS_DIR / season_folder(season) / 'league', f'after_spieltag_{spieltag:02}.json', after_payload)
_save_json(STATS_DIR / season_folder(season) / 'league', 'latest.json', after_payload)

print('✅ Alle Engine-Outputs für Spieltag 3 wurden korrigiert und nachgeliefert.')
