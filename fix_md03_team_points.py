import os
import json
import pandas as pd
from pathlib import Path
from LigageneratorV2 import season_folder, SPIELTAG_DIR, SAVEFILE, nord_teams, sued_teams

# Setze das Data-Root für die Engine
os.environ['HIGHSPEED_DATA_ROOT'] = '/opt/highspeed/data'

season = 1
spieltag = 3
spieltag_path = SPIELTAG_DIR / season_folder(season) / f'spieltag_{spieltag:02}.json'

# Lade canonicales Spieltag-JSON
with open(spieltag_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

# Team-DataFrames laden
nord = pd.DataFrame(nord_teams)
sued = pd.DataFrame(sued_teams)

# Punkte aus Savegame laden (bisherige Punkte)
with open(SAVEFILE, 'r', encoding='utf-8') as f:
    state = json.load(f)

if 'nord' in state and 'sued' in state:
    nord = pd.DataFrame(state['nord'])
    sued = pd.DataFrame(state['sued'])

# Punktevergabe nach Engine-Logik
for game in data['games']:
    home = game['home']
    away = game['away']
    g_home = game['g_home']
    g_away = game['g_away']
    ot = game.get('overtime', False)
    so = game.get('shootout', False)
    # Punktevergabe: 3/2/1/0
    if g_home > g_away:
        if ot or so:
            home_pts, away_pts = 2, 1
        else:
            home_pts, away_pts = 3, 0
    elif g_away > g_home:
        if ot or so:
            home_pts, away_pts = 1, 2
        else:
            home_pts, away_pts = 0, 3
    else:
        # Unentschieden gibt es im Eishockey nicht, aber falls doch:
        home_pts, away_pts = 1, 1
    # Punkte addieren
    for df, team, pts in [(nord, home, home_pts), (nord, away, away_pts), (sued, home, home_pts), (sued, away, away_pts)]:
        if team in df['Team'].values:
            df.loc[df['Team'] == team, 'Points'] = df.loc[df['Team'] == team, 'Points'].fillna(0) + pts

# Schreibe aktualisierte Team-Frames ins Savegame
state['nord'] = nord.to_dict(orient='records')
state['sued'] = sued.to_dict(orient='records')
with open(SAVEFILE, 'w', encoding='utf-8') as f:
    json.dump(state, f, indent=2, ensure_ascii=False)

print('✅ Team-Punkte für Spieltag 3 wurden nachgetragen.')
