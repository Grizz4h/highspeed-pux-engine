# ================================================
#  LIGA-SIMULATOR  –  Round-Robin + Play-offs
# ================================================
import os, json, random
import pandas as pd

# ------------------------------------------------
# ⚙️ 1  SAVE / LOAD
# ------------------------------------------------
SAVEFILE = "saves/savegame.json"

def save_progress(payload: dict):
    os.makedirs(os.path.dirname(SAVEFILE), exist_ok=True)
    with open(SAVEFILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=4)

def load_progress():
    if os.path.exists(SAVEFILE) and os.path.getsize(SAVEFILE) > 0:
        with open(SAVEFILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

# ------------------------------------------------
# ⚙️ 1  Spieltag Ausgabe
# ------------------------------------------------

import json
import os

import os
import json
from datetime import datetime

def get_current_saison_number(base_path="spieltage"):
    if not os.path.exists(base_path):
        return 1
    existing = [d for d in os.listdir(base_path) if d.startswith("saison_")]
    if not existing:
        return 1
    nummern = [int(d.split("_")[1]) for d in existing if d.split("_")[1].isdigit()]
    return max(nummern)

def save_spieltag_data(spieltag, nord_df, sued_df, player_stats_df, saison_nummer):
    # 📁 Zielordner: spieltage/saison_X/
    ordner = f"spieltage/saison_{saison_nummer}"
    os.makedirs(ordner, exist_ok=True)

    # 📄 Dateiname: spieltag_XX.json
    dateiname = f"spieltag_{spieltag:02}.json"
    pfad = os.path.join(ordner, dateiname)

    # 🧮 Top 20 Scorer berechnen
    player_stats_df["Points"] = player_stats_df["Goals"] + player_stats_df["Assists"]
    top_scorer = player_stats_df.sort_values(by="Points", ascending=False).head(20)

    # 📦 Daten vorbereiten
    daten = {
        "timestamp": datetime.now().isoformat(),
        "spieltag": spieltag,
        "saison": saison_nummer,
        "tabelle_nord": nord_df.sort_values(by=["Points", "Goals For"], ascending=False).to_dict(orient="records"),
        "tabelle_sued": sued_df.sort_values(by=["Points", "Goals For"], ascending=False).to_dict(orient="records"),
        "top_scorer": top_scorer.to_dict(orient="records")
    }

    # 💾 Datei speichern
    with open(pfad, "w", encoding="utf-8") as f:
        json.dump(daten, f, indent=4, ensure_ascii=False)

    print(f"📄 Spieltag {spieltag} in Saison {saison_nummer} gespeichert unter: {pfad}")


# ------------------------------------------------
# 🏒 2  TEAMLISTEN (➡️ hier deine echten Teams einsetzen)
# ------------------------------------------------


from realeTeams import nord_teams, sued_teams




# ------------------------------------------------
# 📅 3  ROUND-ROBIN-SCHEDULE
# ------------------------------------------------
def create_round_robin_schedule(teams: list[dict]) -> list[tuple[str,str]]:
    """Ein vollständiger Hin- & Rückrundenplan."""
    teams = teams.copy()
    if len(teams) % 2:                # Bye-Slot für ungerade Anzahl
        teams.append({"Team": "BYE"})
    days = len(teams) - 1
    half = len(teams) // 2
    schedule = []

    for d in range(days * 2):         # doppelte Anzahl = Heim/Auswärts
        pairs = []
        for i in range(half):
            t1, t2 = teams[i]["Team"], teams[-i-1]["Team"]
            pairs.append((t1, t2) if d % 2 == 0 else (t2, t1))
        schedule.extend(pairs)
        teams.insert(1, teams.pop())  # Round-Robin Rotation
    return schedule

# ------------------------------------------------
# 🔢 4  TEAMSTÄRKE
# ------------------------------------------------
def calc_strength(team_row, home=False) -> float:
    players = team_row["Players"]
    if not players:
        return 50.0
    off  = sum(p["Offense"]   for p in players) / len(players)
    de   = sum(p["Defense"]   for p in players) / len(players)
    spd  = sum(p["Speed"]     for p in players) / len(players)
    chem = sum(p["Chemistry"] for p in players) / len(players)

    base = off*0.4 + de*0.3 + spd*0.2 + chem*0.1
    form = random.uniform(-5, 5)
    mom  = team_row.get("Momentum", 0)
    home_adv = 3 if home else 0
    fan  = random.uniform(-1, 2)

    total = base
    total *= (1 + form/100)
    total *= (1 + mom/100)
    total *= (1 + home_adv/100)
    total *= (1 + fan/100)
    return round(total, 2)

# ------------------------------------------------
# 💾 5  SAVEGAME INITIALISIEREN / LADEN
# ------------------------------------------------
data = load_progress()
if data:
    print("✅ Savegame geladen.\n")
    nord_df       = pd.DataFrame(data["nord_df"])
    sued_df       = pd.DataFrame(data["sued_df"])
    nord_schedule = data["nord_schedule"]
    sued_schedule = data["sued_schedule"]
    player_stats  = pd.DataFrame(data["player_stats"])
    spieltag      = data["spieltag"]
else:
    print("🎮 Neues Spiel gestartet.\n")
    # DataFrames
    nord_df = pd.DataFrame(nord_teams)
    sued_df = pd.DataFrame(sued_teams)
    for df in (nord_df, sued_df):
        df[["Points","Goals For","Goals Against"]] = 0

    # Schedules
    nord_schedule = create_round_robin_schedule(nord_teams)
    sued_schedule = create_round_robin_schedule(sued_teams)

    # Spieler-Statistik
    rows = []
    for t in nord_teams + sued_teams:
        for p in t["Players"]:
            rows.append({"Player": p["Name"], "Team": t["Team"],
                         "Goals": 0, "Assists": 0, "Points": 0})
    player_stats = pd.DataFrame(rows)
    spieltag = 1

    # 🧮 Spieler-Statistik-Tabelle initialisieren (nur wenn sie nicht existiert)

# ------------------------------------------------
# ▶️ 6  SPIEL-SIMULATION  (inkl. fairer Scorer-Stats)
# ------------------------------------------------
def update_player_stats(team_name, goals, df):
    roster_full = df.loc[df["Team"] == team_name, "Players"].iloc[0]
    # max 18 Schaden-Verteiler (12 F + 6 D) – fair bei Kadergrößen
    roster = random.sample(roster_full, 18) if len(roster_full) > 18 else roster_full

    names   = [p["Name"] for p in roster]
    weights = [max(1, p["Offense"]//5) for p in roster]  # Offense-Gewichtung

    for _ in range(goals):
        scorer   = random.choices(names, weights)[0]
        assister = random.choice([n for n in names if n != scorer])
        player_stats.loc[player_stats["Player"]==scorer,   "Goals"]   += 1
        player_stats.loc[player_stats["Player"]==assister, "Assists"] += 1

def simulate_match(df, home, away) -> str:
    row_h = df[df["Team"] == home].iloc[0]
    row_a = df[df["Team"] == away].iloc[0]

    s_h = calc_strength(row_h, home=True)
    s_a = calc_strength(row_a, home=False)
    p_h = s_h / (s_h + s_a)

    g_h = max(0, int(random.gauss(p_h*5, 1)))
    g_a = max(0, int(random.gauss((1-p_h)*5, 1)))

    # Tabelle updaten
    df.loc[df["Team"] == home, "Goals For"]     += g_h
    df.loc[df["Team"] == home, "Goals Against"] += g_a
    df.loc[df["Team"] == away, "Goals For"]     += g_a
    df.loc[df["Team"] == away, "Goals Against"] += g_h

    if   g_h > g_a: df.loc[df["Team"] == home, "Points"] += 3
    elif g_a > g_h: df.loc[df["Team"] == away, "Points"] += 3
    else:
        df.loc[df["Team"].isin([home, away]), "Points"] += 1

    # Spieler-Stats
    update_player_stats(home, g_h, df)
    update_player_stats(away, g_a, df)

    return f"{home} {g_h} : {g_a} {away}"

if 'player_stats_df' not in locals():
    all_players = []
    for team in nord_teams + sued_teams:
        for p in team["Players"]:
            all_players.append({
                "Player": p["Name"],
                "Team": team["Team"],
                "Goals": 0,
                "Assists": 0
            })
    player_stats_df = pd.DataFrame(all_players)

# ------------------------------------------------
# 🏆 7  PLAY-OFF-FUNKTION
# ------------------------------------------------
def simulate_playoff_match(teamA, teamB, nord_df, sued_df):
    dfA = nord_df if teamA in nord_df["Team"].values else sued_df
    dfB = nord_df if teamB in nord_df["Team"].values else sued_df

    rowA, rowB = dfA[dfA["Team"]==teamA].iloc[0], dfB[dfB["Team"]==teamB].iloc[0]
    sA, sB = calc_strength(rowA), calc_strength(rowB)
    pA = sA / (sA + sB)
    gA = max(0, int(random.gauss(pA*5, 1)))
    gB = max(0, int(random.gauss((1-pA)*5, 1)))

    update_player_stats(teamA, gA, dfA)
    update_player_stats(teamB, gB, dfB)

    print(f"{teamA} {gA} : {gB} {teamB}")
    return teamA if gA > gB else teamB

def run_playoffs(nord_df, sued_df):
    nord_top4 = nord_df.sort_values(["Points","Goals For"], ascending=False).head(4)
    sued_top4 = sued_df.sort_values(["Points","Goals For"], ascending=False).head(4)

    pairings = [
        (nord_top4.iloc[0]["Team"], sued_top4.iloc[3]["Team"]),
        (nord_top4.iloc[1]["Team"], sued_top4.iloc[2]["Team"]),
        (nord_top4.iloc[2]["Team"], sued_top4.iloc[1]["Team"]),
        (nord_top4.iloc[3]["Team"], sued_top4.iloc[0]["Team"])
    ]

    rnd = 1
    while True:
        print(f"\n=== PLAY-OFF RUNDE {rnd} ===")
        next_round = []

        for a,b in pairings:
            next_round.append(simulate_playoff_match(a, b, nord_df, sued_df))

        if len(next_round) == 1:
            print(f"\n🏆🏆🏆 Champion: {next_round[0]} 🏆🏆🏆")
            return next_round[0]

        # Neue Paarungen -> 1 vs 2, 3 vs 4, …
        pairings = [(next_round[i], next_round[i+1])
                    for i in range(0, len(next_round), 2)]
        rnd += 1

        # Save nach jeder Runde
        save_progress({
            "nord_df": nord_df.to_dict("records"),
            "sued_df": sued_df.to_dict("records"),
            "player_stats": player_stats.to_dict("records"),
            "spieltag": spieltag,
            "nord_schedule": nord_schedule,
            "sued_schedule": sued_schedule
        })

        input("\n👉  Enter für nächste Play-off-Runde …")

# ------------------------------------------------
# ================= HAUPTSCHLEIFE =================
# ------------------------------------------------

# Saison-Nummer ermitteln
saison_nummer = get_current_saison_number()


while True:

    if nord_schedule or sued_schedule:
        input(f"👉  Enter zum Simulieren von Spieltag {spieltag}…")

        print(f"\n=== Spieltag {spieltag} Ergebnisse Nord ===")
        for m in nord_schedule[:len(nord_df)//2]:
            print(simulate_match(nord_df, *m))
        nord_schedule = nord_schedule[len(nord_df)//2:]

        print(f"\n=== Spieltag {spieltag} Ergebnisse Süd ===")
        for m in sued_schedule[:len(sued_df)//2]:
            print(simulate_match(sued_df, *m))
        sued_schedule = sued_schedule[len(sued_df)//2:]

        # Tabellen
        print("\n=== Tabelle Nord ===")
        print(nord_df[["Team","Points","Goals For","Goals Against"]]
              .sort_values(["Points","Goals For"], ascending=False))

        print("\n=== Tabelle Süd ===")
        print(sued_df[["Team","Points","Goals For","Goals Against"]]
              .sort_values(["Points","Goals For"], ascending=False))

        # Top-Scorer
        player_stats["Points"] = player_stats["Goals"] + player_stats["Assists"]
        print("\n=== Top-20 Scorer ===")
        print(player_stats.sort_values("Points", ascending=False).head(20))

        # Fortschritt speichern
        save_progress({
            "nord_df": nord_df.to_dict("records"),
            "sued_df": sued_df.to_dict("records"),
            "player_stats": player_stats.to_dict("records"),
            "spieltag": spieltag + 1,
            "nord_schedule": nord_schedule,
            "sued_schedule": sued_schedule
        })

        # Spieltag-File speichern
        save_spieltag_data(spieltag, nord_df, sued_df, player_stats_df, saison_nummer)

        # Spieltag inkrementieren
        spieltag += 1

        # Bei Saisonende hochzählen
        if spieltag > 18:
            saison_nummer += 1
            spieltag = 1
            print(f"🔁 Neue Saison gestartet! Saison {saison_nummer}")


    else:
        print("\n🏆  Saison beendet – Play-offs starten!")
        run_playoffs(nord_df, sued_df)
        break   # Ende – bei Bedarf neu starten
