# -*- coding: utf-8 -*-
"""DEL‑Style Eishockey‑Liga‑Simulation
-------------------------------------------------
• Zwei Conferences (Nord/Süd) mit Double‑Round‑Robin & anschließenden Play‑offs
• Live‑Scorer‑Tabelle (Goals / Assists / Points)
• Fortschritt wird automatisch in `saves/savegame.json` gesichert

👉 Füge deine Team‑Daten in die Listen `nord_teams` und `sued_teams` ein — Struktur siehe unten. 👈
"""

import os
import json
import random
import pandas as pd

# 1 — SAVE / LOAD -------------------------------------------------------------

def save_progress(filename: str, data: dict) -> None:
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_progress(filename: str):
    if os.path.exists(filename) and os.path.getsize(filename) > 0:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


# 2 — TEAMS (Beispiel‑Gerüst) -------------------------------------------------

nord_teams = [
    # {
    #     "Team": "Berlin EisBären",
    #     "Players": [
    #         {"Name": "Max Mustermann", "Offense": 60, "Defense": 70, "Speed": 65, "Chemistry": 68},
    #         ...
    #     ],
    #     "Momentum": 0  # wird automatisch angepasst
    # },
]

sued_teams = [
    # …
]


# 3 — ROUND‑ROBIN‑SCHEDULE ----------------------------------------------------

def create_round_robin_schedule(teams: list[dict]) -> list[tuple[str, str]]:
    """Erstellt einen doppelten Round‑Robin‑Plan (Hin‑ & Rückspiel)."""
    t = teams.copy()
    if len(t) % 2:
        t.append({"Team": "BYE"})  # Dummy‑Team für ungerade Anzahl
    days = len(t) - 1
    half = len(t) // 2
    schedule: list[tuple[str, str]] = []
    for day in range(days * 2):
        pairs = []
        for i in range(half):
            home, away = t[i]["Team"], t[-i - 1]["Team"]
            pairs.append((home, away) if day % 2 == 0 else (away, home))
        schedule.extend(pairs)
        t.insert(1, t.pop())  # Rotation
    return [p for p in schedule if "BYE" not in p]


# 4 — TEAM‑STÄRKE -------------------------------------------------------------

def calculate_team_strength(team_row: pd.Series, *, is_home: bool = False) -> float:
    players = team_row["Players"]
    if not players:
        return 50.0
    offense = sum(p["Offense"] for p in players) / len(players)
    defense = sum(p["Defense"] for p in players) / len(players)
    speed = sum(p["Speed"] for p in players) / len(players)
    chemistry = sum(p["Chemistry"] for p in players) / len(players)

    base = offense * 0.4 + defense * 0.3 + speed * 0.2 + chemistry * 0.1

    # Dynamische Modifier
    form = random.uniform(-5, 5)            # Tagesform ±5 %
    momentum = team_row.get("Momentum", 0)  # Lauf aus vorherigen Spielen
    home_adv = 3 if is_home else 0          # Heimvorteil
    fan_support = random.uniform(-1, 2)     # Tribünen‑Boost

    total = base
    for bonus in (form, momentum, home_adv, fan_support):
        total *= 1 + bonus / 100
    return total


# 5 — SPIEL‑SIMULATION --------------------------------------------------------

def simulate_match(df: pd.DataFrame, home_team: str, away_team: str, player_stats: pd.DataFrame) -> str:
    home_row = df.loc[df["Team"] == home_team].iloc[0]
    away_row = df.loc[df["Team"] == away_team].iloc[0]

    s_home = calculate_team_strength(home_row, is_home=True)
    s_away = calculate_team_strength(away_row)

    p_home = s_home / (s_home + s_away)
    g_home = max(0, int(random.gauss(p_home * 5, 1)))
    g_away = max(0, int(random.gauss((1 - p_home) * 5, 1)))

    # Tabelle aktualisieren
    df.loc[df["Team"] == home_team, ["Goals For", "Goals Against"]] += [g_home, g_away]
    df.loc[df["Team"] == away_team, ["Goals For", "Goals Against"]] += [g_away, g_home]

    if g_home > g_away:
        df.loc[df["Team"] == home_team, "Points"] += 3
    elif g_home < g_away:
        df.loc[df["Team"] == away_team, "Points"] += 3
    else:
        df.loc[df["Team"].isin([home_team, away_team]), "Points"] += 1

    # Spieler‑Stats
    for team_name, goals in ((home_team, g_home), (away_team, g_away)):
        roster = df.loc[df["Team"] == team_name, "Players"].iloc[0]
        names = [p["Name"] for p in roster]
        weights = [max(1, p["Offense"] // 5) for p in roster]
        for _ in range(goals):
            scorer = random.choices(names, weights)[0]
            assister = random.choice([n for n in names if n != scorer])
            player_stats.loc[player_stats["Player"] == scorer, "Goals"] += 1
            player_stats.loc[player_stats["Player"] == assister, "Assists"] += 1

    return f"{home_team} {g_home} : {g_away} {away_team}"


# 6 — PLAY‑OFFS ---------------------------------------------------------------

def simulate_playoff_round(pairings: list[tuple[str, str]], nord_df: pd.DataFrame, sued_df: pd.DataFrame) -> list[str]:
    """Spielt eine komplette Runde (Best‑of‑One) und gibt die Sieger zurück."""
    winners: list[str] = []
    for a, b in pairings:
        df_a = nord_df if (nord_df["Team"] == a).any() else sued_df
        df_b = nord_df if (nord_df["Team"] == b).any() else sued_df
        row_a = df_a.loc[df_a["Team"] == a].iloc[0]
        row_b = df_b.loc[df_b["Team"] == b].iloc[0]
        s_a, s_b = calculate_team_strength(row_a), calculate_team_strength(row_b)
        p_a = s_a / (s_a + s_b)
        g_a = max(0, int(random.gauss(p_a * 5, 1)))
        g_b = max(0, int(random.gauss((1 - p_a) * 5, 1)))
        print(f"{a} {g_a} : {g_b} {b}")
        winners.append(a if g_a > g_b else b)
    return winners


def run_playoffs(nord_df: pd.DataFrame, sued_df: pd.DataFrame) -> str:
    """Ermittelt den Champion. Nach jeder Runde muss Enter gedrückt werden."""
    nord_top = nord_df.sort_values(["Points", "Goals For"], ascending=False).head(4)["Team"].tolist()
    sued_top = sued_df.sort_values(["Points", "Goals For"], ascending=False).head(4)["Team"].tolist()

    pairings = [
        (nord_top[0], sued_top[3]),
        (nord_top[1], sued_top[2]),
        (nord_top[2], sued_top[1]),
        (nord_top[3], sued_top[0]),
    ]
    round_no = 1

    while len(pairings) > 1:
        print(f"\n=== PLAY‑OFF RUNDE {round_no} ===")
        winners = simulate_playoff_round(pairings, nord_df, sued_df)
        input("👉 Enter für nächste Play‑off‑Runde…")  # Pausen‑Abfrage
        pairings = [(winners[i], winners[i + 1]) for i in range(0, len(winners), 2)]
        round_no += 1

    print("\n=== FINALE ===")
    champion = simulate_playoff_round(pairings, nord_df, sued_df)[0]
    print(f"\n🏆🏆🏆 Champion: {champion} 🏆🏆🏆\n")
    return champion


# 7 — INITIALISIERUNG ---------------------------------------------------------

def initialise_game():
    if not nord_teams or not sued_teams:
        raise ValueError("Bitte füge Team‑Daten in nord_teams und sued_teams ein.")

    nord_df, sued_df = pd.DataFrame(nord_teams), pd.DataFrame(sued_teams)
    for df in (nord_df, sued_df):
        df["Points"], df["Goals For"], df["Goals Against"] = 0, 0, 0

    nord_schedule = create_round_robin_schedule(nord_teams)
    sued_schedule = create_round_robin_schedule
