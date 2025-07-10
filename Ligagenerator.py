import pandas as pd
import random
import json
import os

# -------------------------------
# ⚙️ 1. SAVE/LOAD FUNKTIONEN
# -------------------------------

def save_progress(filename, data):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

def load_progress(filename):
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            return json.load(f)
    else:
        return None

# -------------------------------
# 🏒 2. TEAMS & KADER (BEISPIEL)
# -------------------------------

nord_teams = [
    {"Team": "Berlin EisBären", "Players": [{"Name": "Player A", "Offense": 85}, {"Name": "Player B", "Offense": 78}]},
    {"Team": "Wolfsburg Voltsturm", "Players": [{"Name": "Player C", "Offense": 80}, {"Name": "Player D", "Offense": 75}]},
    {"Team": "Wolfsburg Voltsturm", "Players": [{"Name": "Player C", "Offense": 80}, {"Name": "Player D", "Offense": 75}]},
    {"Team": "Wolfsburg Voltsturm", "Players": [{"Name": "Player C", "Offense": 80}, {"Name": "Player D", "Offense": 75}]},
    {"Team": "Wolfsburg Voltsturm", "Players": [{"Name": "Player C", "Offense": 80}, {"Name": "Player D", "Offense": 75}]},
    {"Team": "Wolfsburg Voltsturm", "Players": [{"Name": "Player C", "Offense": 80}, {"Name": "Player D", "Offense": 75}]},
    {"Team": "Wolfsburg Voltsturm", "Players": [{"Name": "Player C", "Offense": 80}, {"Name": "Player D", "Offense": 75}]},
    # ➡️ Restliche Nord Teams hier einfügen...
]

sued_teams = [
    {"Team": "Ingolstadt Indigo Panther", "Players": [{"Name": "Player E", "Offense": 82}, {"Name": "Player F", "Offense": 76}]},
    {"Team": "München FluxBullen", "Players": [{"Name": "Player G", "Offense": 84}, {"Name": "Player H", "Offense": 79}]},
    {"Team": "München FluxBullen", "Players": [{"Name": "Player G", "Offense": 84}, {"Name": "Player H", "Offense": 79}]},
    {"Team": "München FluxBullen", "Players": [{"Name": "Player G", "Offense": 84}, {"Name": "Player H", "Offense": 79}]},
    {"Team": "München FluxBullen", "Players": [{"Name": "Player G", "Offense": 84}, {"Name": "Player H", "Offense": 79}]},
    {"Team": "München FluxBullen", "Players": [{"Name": "Player G", "Offense": 84}, {"Name": "Player H", "Offense": 79}]},
    {"Team": "München FluxBullen", "Players": [{"Name": "Player G", "Offense": 84}, {"Name": "Player H", "Offense": 79}]},
    {"Team": "München FluxBullen", "Players": [{"Name": "Player G", "Offense": 84}, {"Name": "Player H", "Offense": 79}]},
    # ➡️ Restliche Süd Teams hier einfügen...
]

# -------------------------------
# 📊 3. INITIALISIERUNG
# -------------------------------

savefile = 'saves/savegame.json'
progress = load_progress(savefile)

if progress:
    print("✅ Savegame geladen.\n")
    nord_df = pd.DataFrame(progress["nord_df"])
    sued_df = pd.DataFrame(progress["sued_df"])
    nord_schedule = progress["nord_schedule"]
    sued_schedule = progress["sued_schedule"]
    player_stats_df = pd.DataFrame(progress["player_stats"])
    spieltag = progress["spieltag"]
    playoffs = progress["playoffs"]
else:
    print("🎮 Neues Spiel gestartet.\n")
    # DataFrames initialisieren
    def init_df(teams):
        df = pd.DataFrame(teams)
        df["Points"] = 0
        df["Goals For"] = 0
        df["Goals Against"] = 0
        return df

    nord_df = init_df(nord_teams)
    sued_df = init_df(sued_teams)

    # Schedules erstellen
    def create_schedule(df):
        schedule = []
        for i in range(len(df)):
            for j in range(i+1, len(df)):
                schedule.append({"Home": df.loc[i, "Team"], "Away": df.loc[j, "Team"]})
        random.shuffle(schedule)
        return schedule

    nord_schedule = create_schedule(nord_df)
    sued_schedule = create_schedule(sued_df)

    # Spielerstats initialisieren
    player_stats = []
    for team in nord_teams + sued_teams:
        for p in team["Players"]:
            player_stats.append({"Player": p["Name"], "Team": team["Team"], "Goals": 0, "Assists": 0})
    player_stats_df = pd.DataFrame(player_stats)

    spieltag = 1
    playoffs = []

# -------------------------------
# 🎮 4. SIMULATE MATCH FUNCTION
# -------------------------------

def simulate_match(df, home_team, away_team):
    home_stats = df[df["Team"] == home_team].iloc[0]
    away_stats = df[df["Team"] == away_team].iloc[0]

    home_score = max(0, int(random.gauss(3, 1)))
    away_score = max(0, int(random.gauss(3, 1)))

    # Update Tabelle
    df.loc[df["Team"] == home_team, "Goals For"] += home_score
    df.loc[df["Team"] == home_team, "Goals Against"] += away_score
    df.loc[df["Team"] == away_team, "Goals For"] += away_score
    df.loc[df["Team"] == away_team, "Goals Against"] += home_score

    # Punktevergabe
    if home_score > away_score:
        df.loc[df["Team"] == home_team, "Points"] += 3
    elif away_score > home_score:
        df.loc[df["Team"] == away_team, "Points"] += 3
    else:
        df.loc[df["Team"] == home_team, "Points"] += 1
        df.loc[df["Team"] == away_team, "Points"] += 1

    # Spielerstats aktualisieren (Offense-gewichtete Verteilung)
    for team_name, score in [(home_team, home_score), (away_team, away_score)]:
        team_row = nord_df[nord_df["Team"] == team_name]
        if team_row.empty:
            team_row = sued_df[sued_df["Team"] == team_name]
        players = team_row.iloc[0]["Players"]
        for _ in range(score):
            weighted_players = []
            for p in players:
                weighted_players += [p["Name"]] * (p["Offense"] // 5)
            scorer = random.choice(weighted_players)
            assist = random.choice(weighted_players)
            player_stats_df.loc[player_stats_df["Player"] == scorer, "Goals"] += 1
            player_stats_df.loc[player_stats_df["Player"] == assist, "Assists"] += 1

    return f"{home_team} {home_score} - {away_score} {away_team}"

# -------------------------------
# ▶️ 5. SPIELTAG SIMULATION (1 pro Run)
# -------------------------------

input(f"👉 Enter zum Simulieren von Spieltag {spieltag}...")

print(f"\n=== Spieltag {spieltag} Ergebnisse Nord ===")
for match in nord_schedule[:len(nord_df)//2]:
    print(simulate_match(nord_df, match["Home"], match["Away"]))
nord_schedule = nord_schedule[len(nord_df)//2:]

print(f"\n=== Spieltag {spieltag} Ergebnisse Süd ===")
for match in sued_schedule[:len(sued_df)//2]:
    print(simulate_match(sued_df, match["Home"], match["Away"]))
sued_schedule = sued_schedule[len(sued_df)//2:]

# Tabellen anzeigen
print("\n=== Tabelle Nord ===")
print(nord_df.sort_values(by=["Points", "Goals For"], ascending=False)[["Team", "Points", "Goals For", "Goals Against"]])

print("\n=== Tabelle Süd ===")
print(sued_df.sort_values(by=["Points", "Goals For"], ascending=False)[["Team", "Points", "Goals For", "Goals Against"]])

# Spielerstats anzeigen
print("\n=== Top Scorer ===")
player_stats_df["Points"] = player_stats_df["Goals"] + player_stats_df["Assists"]
print(player_stats_df.sort_values(by="Points", ascending=False))

spieltag += 1

# -------------------------------
# 💾 6. SAVE PROGRESS
# -------------------------------

progress = {
    "nord_df": nord_df.to_dict(orient="records"),
    "sued_df": sued_df.to_dict(orient="records"),
    "nord_schedule": nord_schedule,
    "sued_schedule": sued_schedule,
    "player_stats": player_stats_df.to_dict(orient="records"),
    "spieltag": spieltag,
    "playoffs": playoffs
}

save_progress(savefile, progress)
print("\n✅ Fortschritt gespeichert.")
