import os
import json
from pathlib import Path
from LigageneratorV2 import season_folder, LINEUP_DIR, nord_teams, sued_teams

# Setze das Data-Root für die Engine
os.environ['HIGHSPEED_DATA_ROOT'] = '/opt/highspeed/data'

season = 1
spieltag = 3
spieltag_path = Path('/opt/highspeed/data/spieltage/saison_01/spieltag_03.json')
lineup_dir = LINEUP_DIR / season_folder(season)
lineup_dir.mkdir(parents=True, exist_ok=True)
lineup_path = lineup_dir / f'spieltag_{spieltag:02}_lineups.json'

# Lade canonicales Spieltag-JSON
with spieltag_path.open('r', encoding='utf-8') as f:
    data = json.load(f)

# Teams laden
all_teams = {t['Team']: t for t in (nord_teams + sued_teams)}

# Baue Lineup-Struktur
lineups = {}
for game in data['games']:
    for team_name in [game['home'], game['away']]:
        team = all_teams[team_name]
        # Übernehme alle Spieler in die Standard-Positionen (vereinfachtes Schema)
        forwards = {'line1': [], 'line2': [], 'line3': [], 'line4': []}
        defense = {'pair1': [], 'pair2': [], 'pair3': []}
        goalie = None
        for p in team['Players']:
            entry = {'id': p['Name'], 'Name': p['Name'], 'Number': p['Number'], 'rotation': False}
            if p.get('Position') == 'G' and not goalie:
                goalie = entry
            elif p.get('Position') == 'D':
                for pair in ['pair1', 'pair2', 'pair3']:
                    if len(defense[pair]) < 2:
                        defense[pair].append(entry)
                        break
            else:
                for line in ['line1', 'line2', 'line3', 'line4']:
                    if len(forwards[line]) < 3:
                        forwards[line].append(entry)
                        break
        lineups[team_name] = {'forwards': forwards, 'defense': defense, 'goalie': goalie}

# Schreibe Lineup-File
with lineup_path.open('w', encoding='utf-8') as f:
    json.dump({'season': season, 'spieltag': spieltag, 'teams': lineups}, f, indent=2, ensure_ascii=False)

print('✅ Lineup für Spieltag 3 wurde erzeugt:', lineup_path)
