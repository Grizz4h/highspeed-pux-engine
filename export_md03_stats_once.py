import os
import json
import pandas as pd
from LigageneratorV2 import season_folder, LINEUP_DIR, STATS_DIR, nord_teams, sued_teams
import player_stats_export

# Setze das Data-Root für die Engine
os.environ['HIGHSPEED_DATA_ROOT'] = '/opt/highspeed/data'

season = 1
spieltag = 3

# Lade das Lineup für Spieltag 3
lineup_path = LINEUP_DIR / season_folder(season) / f'spieltag_{spieltag:02}_lineups.json'
with open(lineup_path, 'r', encoding='utf-8') as f:
    lineup_json = json.load(f)

# Leeres DataFrame für Stats (Goals/Assists irrelevant für GP)
stats_df = pd.DataFrame([])
all_teams = nord_teams + sued_teams

# Baue die Matchday-Stats (nur GP)
matchday_stats = player_stats_export.build_player_stats_for_matchday(lineup_json, stats_df, all_teams)

# Lade bestehende Saison-Stats und merge
existing_stats = player_stats_export.load_existing_player_stats(STATS_DIR, season)
updated_stats = player_stats_export.merge_into_season_player_stats(existing_stats, matchday_stats)

# Schreibe die Stats-Files (player_stats_after_spieltag_03.json, player_stats_latest.json)
player_stats_export.write_player_stats_files(
    STATS_DIR / season_folder(season),
    season,
    spieltag,
    updated_stats,
    all_teams
)

print('✅ Spielerstatistiken für Spieltag 3 wurden einmalig exportiert.')
