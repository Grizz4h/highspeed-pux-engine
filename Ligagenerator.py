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
    if os.path.exists(filename) and os.path.getsize(filename) > 0:
        with open(filename, 'r') as f:
            return json.load(f)
    else:
        return None

# -------------------------------
# 🏒 2. TEAMS & KADER (BEISPIEL)
# ➔ Bitte mit deinen echten Kadern ersetzen
# -------------------------------

nord_teams = [
    {"Team": "Berlin EisBären", "Players": [
        {"Name": "Player A", "Offense": 85, "Defense": 75, "Speed": 72, "Chemistry": 70},
        {"Name": "Player B", "Offense": 80, "Defense": 73, "Speed": 70, "Chemistry": 68}
    ], "Momentum": 0},
    # ➡️ weitere Nord Teams
]

sued_teams = [
    {"Team": "Ingolstadt Indigo Panther", "Players": [
        {"Name": "Player G", "Offense": 82, "Defense": 74, "Speed": 71, "Chemistry": 69},
        {"Name": "Player H", "Offense": 78, "Defense": 72, "Speed": 70, "Chemistry": 68}
    ], "Momentum": 0},
    # ➡️ weitere Süd Teams
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

    def init_df(teams):
        df = pd.DataFrame(teams)
        df["Points"] = 0
        df["Goals For"] = 0
        df["Goals Against"] = 0
        return df

    nord_df = init_df(nord_teams)
    sued_df = init_df(sued_teams)

    def create_schedule(df):
        schedule = []
        for i in range(len(df)):
            for j in range(i+1, len(df)):
                schedule.append({"Home": df.loc[i, "Team"], "Away": df.loc[j, "Team"]})
        random.shuffle(schedule)
        return schedule

    nord_schedule = create_schedule(nord_df)
    sued_schedule = create_schedule(sued_df)

    # Spieler Stats initialisieren
    player_stats = []
    for team in nord_teams + sued_teams:
        for p in team["Players"]:
            player_stats.append({"Player": p["Name"], "Team": team["Team"], "Goals": 0, "Assists": 0, "Points": 0})
    player_stats_df = pd.DataFrame(player_stats)

    spieltag = 1
    playoffs = []

# -------------------------------
# ⚙️ 4. TEAMSTÄRKE-BERECHNUNG
# -------------------------------

def calculate_team_strength(team, is_home=False):
    offense = sum(p["Offense"] for p in team["Players"]) / len(team["Players"])
    defense = sum(p["Defense"] for p in team["Players"]) / len(team["Players"])
    speed = sum(p["Speed"] for p in team["Players"]) / len(team["Players"])
    chemistry = sum(p["Chemistry"] for p in team["Players"]) / len(team["Players"])

    base_strength = offense * 0.4 + defense * 0.3 + speed * 0.2 + chemistry * 0.1

    form = random.uniform(-5, 5)
    momentum = team.get("Momentum", 0)
    home_advantage = 3 if is_home else 0
    fan_support = random.uniform(-1, 2)

    total_strength = base_strength
    total_strength *= (1 + form / 100)
    total_strength *= (1 + momentum / 100)
    total_strength *= (1 + home_advantage / 100)
    total_strength *= (1 + fan_support / 100)

    return round(total_strength, 2)

# -------------------------------
# 🎮 5. SPIELTAG SIMULATION
# -------------------------------

def simulate_match(df, home_team, away_team):
    home_row = df[df["Team"] == home_team].iloc[0]
    away_row = df[df["Team"] == away_team].iloc[0]

    home_strength = calculate_team_strength(home_row, is_home=True)
    away_strength = calculate_team_strength(away_row, is_home=False)

    prob_home = home_strength / (home_strength + away_strength)
    home_score = max(0, int(random.gauss(prob_home * 5, 1)))
    away_score = max(0, int(random.gauss((1 - prob_home) * 5, 1)))

    # Tabelle updaten
    df.loc[df["Team"] == home_team, "Goals For"] += home_score
    df.loc[df["Team"] == home_team, "Goals Against"] += away_score
    df.loc[df["Team"] == away_team, "Goals For"] += away_score
    df.loc[df["Team"] == away_team, "Goals Against"] += home_score

    if home_score > away_score:
        df.loc[df["Team"] == home_team, "Points"] += 3
        home_row["Momentum"] += 1
        away_row["Momentum"] = max(away_row["Momentum"] - 1, 0)
    elif away_score > home_score:
        df.loc[df["Team"] == away_team, "Points"] += 3
        away_row["Momentum"] += 1
        home_row["Momentum"] = max(home_row["Momentum"] - 1, 0)
    else:
        df.loc[df["Team"] == home_team, "Points"] += 1
        df.loc[df["Team"] == away_team, "Points"] += 1

    # Spieler Stats
    for team_name, goals in [(home_team, home_score), (away_team, away_score)]:
        players = home_row["Players"] if team_name == home_team else away_row["Players"]
        for _ in range(goals):
            weighted = []
            for p in players:
                weighted += [p["Name"]] * (p["Offense"] // 5)
            scorer = random.choice(weighted)
            assist = random.choice(weighted)
            player_stats_df.loc[player_stats_df["Player"] == scorer, "Goals"] += 1
            player_stats_df.loc[player_stats_df["Player"] == assist, "Assists"] += 1

    return f"{home_team} {home_score} - {away_score} {away_team}"

# -------------------------------
# ▶️ 6. SPIELTAG ABLAUF
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

# Tabellen
print("\n=== Tabelle Nord ===")
print(nord_df[["Team", "Points", "Goals For", "Goals Against"]].sort_values(by=["Points", "Goals For"], ascending=False))
print("\n=== Tabelle Süd ===")
print(sued_df[["Team", "Points", "Goals For", "Goals Against"]].sort_values(by=["Points", "Goals For"], ascending=False))

# Top Scorer
print("\n=== Top Scorer ===")
player_stats_df["Points"] = player_stats_df["Goals"] + player_stats_df["Assists"]
print(player_stats_df.sort_values(by="Points", ascending=False))

spieltag += 1

# -------------------------------
# 💾 7. SAVE PROGRESS
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
