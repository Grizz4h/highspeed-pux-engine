# ================================================
#  LIGA-SIMULATOR  –  Round-Robin + Play-offs
#  Version 4.4 – Bo7-Playoffs + Season-Checkpoint + relative Saisons
# ================================================
"""Simulation einer Eishockey-Liga (Nord/Süd-Conference).

Neu in 4.4 (kombiniert):
- Best-of-7 (First-to-4) Playoffs, pro KO-Runde nur 1× Enter (Runden-Batch).
- Saisonende schreibt History & speichert Startzustand der nächsten Saison (Auto-Next-Season).
- Relative Saisonzählung: `max_seasons` zählt ab Startzustand, egal welche Saisonnummer existiert.

Exports:
- Regular Season:  /spieltage/saison_X/spieltag_YY.json
- Playoffs (Serien): /playoffs/saison_X/runde_ZZ.json
"""

from __future__ import annotations

import json
import random
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd

# ------------------------------------------------
# 1  KONSTANTEN & PFADE
# ------------------------------------------------
SAVEFILE     = Path("saves/savegame.json")
SPIELTAG_DIR = Path("spieltage")
PLAYOFF_DIR  = Path("playoffs")

# Playoff-Serien-Parameter
SERIES_BEST_OF   = 7
WINS_TO_ADVANCE  = 4  # First-to-4

# ------------------------------------------------
# 2  TEAMS LADEN
# ------------------------------------------------
from realeTeams import nord_teams, sued_teams  # noqa: E402


# ------------------------------------------------
# 3  SPEICHERN / LADEN
# ------------------------------------------------

def _ensure_dirs() -> None:
    for p in (SAVEFILE.parent, SPIELTAG_DIR, PLAYOFF_DIR):
        p.mkdir(parents=True, exist_ok=True)


def get_next_season_number() -> int:
    """Nächste freie Saisonnummer aus Ordnerstruktur."""
    if not SPIELTAG_DIR.exists():
        return 1
    nums = [
        int(p.name.split("_")[1])
        for p in SPIELTAG_DIR.iterdir()
        if p.is_dir() and p.name.startswith("saison_") and p.name.split("_")[1].isdigit()
    ]
    return max(nums, default=0) + 1


def save_state(state: Dict[str, Any]) -> None:
    SAVEFILE.parent.mkdir(parents=True, exist_ok=True)
    with SAVEFILE.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def load_state() -> Dict[str, Any] | None:
    if SAVEFILE.exists() and SAVEFILE.stat().st_size > 0:
        with SAVEFILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    return None


# ------------------------------------------------
# 3b  EXPORT-HILFEN
# ------------------------------------------------

def _export_tables(nord_df: pd.DataFrame, sued_df: pd.DataFrame, stats: pd.DataFrame) -> Dict[str, Any]:
    stats["Points"] = stats["Goals"] + stats["Assists"]

    def _prep(df: pd.DataFrame) -> List[Dict[str, Any]]:
        d = df.copy()
        d.rename(columns={"Goals For": "GF", "Goals Against": "GA"}, inplace=True)
        d["GD"] = d["GF"] - d["GA"]
        return d.sort_values(["Points", "GF"], ascending=False)[["Team", "Points", "GF", "GA", "GD"]].to_dict("records")

    return {
        "tabelle_nord": _prep(nord_df),
        "tabelle_sued": _prep(sued_df),
        "top_scorer": stats.sort_values("Points", ascending=False)
            .head(20)[["Player", "Team", "Goals", "Assists", "Points"]]
            .to_dict("records"),
    }


def _save_json(folder: Path, name: str, payload: Dict[str, Any]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / name).open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print("📦 JSON gespeichert →", folder / name)


def save_spieltag_json(season: int, gameday: int, results: List[Dict[str, Any]],
                       nord: pd.DataFrame, sued: pd.DataFrame, stats: pd.DataFrame) -> None:
    """Regular-Season JSON (Kompatibilität erhalten)."""
    payload = {
        "timestamp": datetime.now().isoformat(),
        "saison": season,
        "spieltag": gameday,
        "results": results,
        **_export_tables(nord, sued, stats),
    }
    _save_json(SPIELTAG_DIR / f"saison_{season}", f"spieltag_{gameday:02}.json", payload)


# ------------------------------------------------
# 4  TERMINAL-AUSGABEN
# ------------------------------------------------

def _print_tables(nord: pd.DataFrame, sued: pd.DataFrame, stats: pd.DataFrame) -> None:
    def _prep(df: pd.DataFrame):
        t = df.copy()
        t["GD"] = t["Goals For"] - t["Goals Against"]
        return t.sort_values(["Points", "Goals For"], ascending=False)[
            ["Team", "Points", "Goals For", "Goals Against", "GD"]
        ]

    print("\n📊 Tabelle Nord")
    print(_prep(nord).to_string(index=False))

    print("\n📊 Tabelle Süd")
    print(_prep(sued).to_string(index=False))

    stats["Points"] = stats["Goals"] + stats["Assists"]
    top20 = stats.sort_values("Points", ascending=False).head(20)[
        ["Player", "Team", "Goals", "Assists", "Points"]
    ]
    print("\n⭐ Top-20 Scorer")
    print(top20.to_string(index=False))


# ------------------------------------------------
# 5  BERECHNUNGEN & SIMULATION (Regular Season)
# ------------------------------------------------

def calc_strength(row: pd.Series, home: bool = False) -> float:
    players = row["Players"]
    base = (
        sum(p["Offense"] for p in players) * 0.4 +
        sum(p["Defense"] for p in players) * 0.3 +
        sum(p["Speed"]   for p in players) * 0.2 +
        sum(p["Chemistry"] for p in players) * 0.1
    ) / len(players)
    total = base
    total *= 1 + random.uniform(-5, 5) / 100
    total *= 1 + row.get("Momentum", 0) / 100
    total *= 1 + (3 if home else 0) / 100
    total *= 1 + random.uniform(-1, 2) / 100
    return round(total, 2)


def create_schedule(teams: List[Dict[str, Any]]) -> List[Tuple[str, str]]:
    teams = teams.copy()
    if len(teams) % 2:
        teams.append({"Team": "BYE"})
    days, half = len(teams) - 1, len(teams) // 2
    sched = []
    for d in range(days * 2):
        day = []
        for i in range(half):
            a, b = teams[i]["Team"], teams[-i - 1]["Team"]
            day.append((a, b) if d % 2 == 0 else (b, a))
        sched.extend(day)
        teams.insert(1, teams.pop())
    return sched


def update_player_stats(team: str, goals: int, df: pd.DataFrame, stats: pd.DataFrame) -> None:
    roster = df.loc[df["Team"] == team, "Players"].iloc[0]
    roster = random.sample(roster, 18) if len(roster) > 18 else roster
    names = [p["Name"] for p in roster]
    weights = [max(1, p["Offense"] // 5) for p in roster]
    for _ in range(goals):
        scorer = random.choices(names, weights)[0]
        assister = random.choice([n for n in names if n != scorer])
        stats.loc[stats["Player"] == scorer, "Goals"] += 1
        stats.loc[stats["Player"] == assister, "Assists"] += 1


def simulate_match(df: pd.DataFrame, home: str, away: str,
                   stats: pd.DataFrame, conf: str) -> Tuple[str, Dict[str, Any]]:
    r_h, r_a = df[df["Team"] == home].iloc[0], df[df["Team"] == away].iloc[0]
    p_home = calc_strength(r_h, True) / (calc_strength(r_h, True) + calc_strength(r_a))
    g_home = max(0, int(random.gauss(p_home * 5, 1)))
    g_away = max(0, int(random.gauss((1 - p_home) * 5, 1)))
    # update standings
    df.loc[df["Team"] == home, ["Goals For", "Goals Against"]] += [g_home, g_away]
    df.loc[df["Team"] == away, ["Goals For", "Goals Against"]] += [g_away, g_home]
    if g_home > g_away:
        df.loc[df["Team"] == home, "Points"] += 3
    elif g_away > g_home:
        df.loc[df["Team"] == away, "Points"] += 3
    else:
        df.loc[df["Team"].isin([home, away]), "Points"] += 1
    update_player_stats(home, g_home, df, stats)
    update_player_stats(away, g_away, df, stats)
    res_str = f"{home} {g_home}:{g_away} {away}"
    res_json = {"home": home, "away": away, "g_home": g_home, "g_away": g_away, "conference": conf}
    return res_str, res_json


def init_stats() -> pd.DataFrame:
    return pd.DataFrame([
        {"Player": p["Name"], "Team": t["Team"], "Goals": 0, "Assists": 0}
        for t in nord_teams + sued_teams for p in t["Players"]
    ])


# ------------------------------------------------
# 6  PLAY-OFFS – Best-of-7 (First-to-4), Runden-Batch
# ------------------------------------------------

def _df_for_team(team: str, nord: pd.DataFrame, sued: pd.DataFrame) -> pd.DataFrame:
    return nord if team in set(nord["Team"]) else sued


def simulate_playoff_game(a: str, b: str,
                          nord: pd.DataFrame,
                          sued: pd.DataFrame,
                          stats: pd.DataFrame) -> Dict[str, Any]:
    """Ein einzelnes Playoff-Spiel (neutraler Home-Bias)."""
    dfA = _df_for_team(a, nord, sued)
    dfB = _df_for_team(b, nord, sued)

    pA = calc_strength(dfA[dfA["Team"] == a].iloc[0])
    pB = calc_strength(dfB[dfB["Team"] == b].iloc[0])
    prob = pA / (pA + pB)

    gA = max(0, int(random.gauss(prob * 5, 1)))
    gB = max(0, int(random.gauss((1 - prob) * 5, 1)))

    update_player_stats(a, gA, dfA, stats)
    update_player_stats(b, gB, dfB, stats)

    return {"home": a, "away": b, "g_home": gA, "g_away": gB}


def simulate_series_best_of(a: str, b: str,
                            nord: pd.DataFrame,
                            sued: pd.DataFrame,
                            stats: pd.DataFrame,
                            best_of: int = SERIES_BEST_OF,
                            wins_needed: int = WINS_TO_ADVANCE) -> Dict[str, Any]:
    """Simuliert eine Serie (Best-of-N) in einem Rutsch. Liefert alle Spiele + Winner."""
    wins_a = 0
    wins_b = 0
    games: List[Dict[str, Any]] = []

    # einfache Home-Rotation: A startet „home“ (Kosmetik für Output)
    for g in range(1, best_of + 1):
        home, away = (a, b) if g % 2 == 1 else (b, a)
        g_res = simulate_playoff_game(home, away, nord, sued, stats)
        games.append({"g": g, **g_res})

        if g_res["g_home"] > g_res["g_away"]:
            wins_a += 1 if home == a else 0
            wins_b += 1 if home == b else 0
        elif g_res["g_away"] > g_res["g_home"]:
            wins_a += 1 if away == a else 0
            wins_b += 1 if away == b else 0

        if wins_a >= wins_needed or wins_b >= wins_needed:
            break

    winner = a if wins_a > wins_b else b
    result_str = f"{a} {wins_a}-{wins_b} {b}"
    return {
        "a": a,
        "b": b,
        "best_of": best_of,
        "wins_to_advance": wins_needed,
        "games": games,
        "result": result_str,
        "winner": winner,
    }

def _initial_playoff_pairings(nord: pd.DataFrame, sued: pd.DataFrame) -> list[tuple[str, str]]:
    nord4 = nord.sort_values(["Points", "Goals For"], ascending=False).head(4)
    sued4 = sued.sort_values(["Points", "Goals For"], ascending=False).head(4)
    return [
        (nord4.iloc[0]["Team"], sued4.iloc[3]["Team"]),
        (nord4.iloc[1]["Team"], sued4.iloc[2]["Team"]),
        (nord4.iloc[2]["Team"], sued4.iloc[1]["Team"]),
        (nord4.iloc[3]["Team"], sued4.iloc[0]["Team"]),
    ]

def run_playoffs(season: int,
                 nord: pd.DataFrame,
                 sued: pd.DataFrame,
                 stats: pd.DataFrame,
                 *,
                 interactive: bool = True) -> str:
    """Play-offs rundenweise. Pro Runde nur *eine* Bestätigung (Enter).
    Rückgabewert: Champion-Teamname (str).
    """
    nord4 = nord.sort_values(["Points", "Goals For"], ascending=False).head(4)
    sued4 = sued.sort_values(["Points", "Goals For"], ascending=False).head(4)

    # Cross-Over 1vs4, 2vs3, 3vs2, 4vs1
    pairings = [
        (nord4.iloc[0]["Team"], sued4.iloc[3]["Team"]),
        (nord4.iloc[1]["Team"], sued4.iloc[2]["Team"]),
        (nord4.iloc[2]["Team"], sued4.iloc[1]["Team"]),
        (nord4.iloc[3]["Team"], sued4.iloc[0]["Team"]),
    ]

    rnd = 1
    while True:
        if interactive:
            input(f"➡️  Enter für Play-off-Runde {rnd} (Saison {season}, Best-of-{SERIES_BEST_OF}) …")

        print(f"\n=== PLAY-OFF RUNDE {rnd} (Saison {season}) – Best-of-{SERIES_BEST_OF} ===")
        round_series: List[Dict[str, Any]] = []
        winners: List[str] = []

        # komplette Runde simulieren
        for a, b in pairings:
            series = simulate_series_best_of(a, b, nord, sued, stats)
            round_series.append(series)
            winners.append(series["winner"])
            print(f"• Serie: {series['result']}  → Sieger: {series['winner']}")

        # JSON-Dump für diese Runde (mit Serien)
        _save_json(
            PLAYOFF_DIR / f"saison_{season}",
            f"runde_{rnd:02}.json",
            {
                "timestamp": datetime.now().isoformat(),
                "saison": season,
                "runde": rnd,
                "series": round_series,
                **_export_tables(nord, sued, stats),
            },
        )

        # 🔒 Autosave „aktueller Zustand“ + History unverändert lassen (History kommt erst am Saisonende)
        existing = load_state() or {}
        history = existing.get("history", [])
        save_state({
            "season": season,
            "spieltag": f"Playoff_Runde_{rnd}",
            "nord": nord.to_dict("records"),
            "sued": sued.to_dict("records"),
            "nsched": [],
            "ssched": [],
            "stats": stats.to_dict("records"),
            "history": history,
        })

        # Champion ermitteln?
        if len(winners) == 1:
            champion = winners[0]
            print(f"\n🏆  Champion Saison {season}: {champion}  🏆\n")
            return champion

        pairings = [(winners[i], winners[i + 1]) for i in range(0, len(winners), 2)]
        rnd += 1


# ------------------------------------------------
# 7  SAISON-LOOP + Auto-Next-Season
# ------------------------------------------------

def _init_frames() -> Tuple[pd.DataFrame, pd.DataFrame]:
    n = pd.DataFrame(nord_teams)
    s = pd.DataFrame(sued_teams)
    for d in (n, s):
        d[["Points", "Goals For", "Goals Against"]] = 0
    return n, s


def _init_new_season_state(season: int) -> Dict[str, Any]:
    """Erzeugt Startzustand für eine frische Saison (Spieltag 1)."""
    nord, sued = _init_frames()
    nsched = create_schedule(nord_teams)
    ssched = create_schedule(sued_teams)
    stats = init_stats()
    return {
        "season": season,
        "spieltag": 1,
        "nord": nord.to_dict("records"),
        "sued": sued.to_dict("records"),
        "nsched": nsched,
        "ssched": ssched,
        "stats": stats.to_dict("records"),
    }


def run_simulation(max_seasons: int | None = None, interactive: bool = True) -> None:
    """Simuliere `max_seasons` Saisons **relativ** ab jetzigem Zustand.
    Nach jeder Saison:
      - History-Eintrag (Saison, Champion, Timestamp)
      - Startzustand der nächsten Saison speichern (kein manuelles Löschen).
    """
    _ensure_dirs()

    state = load_state()
    if state:
        print(f"🔄  Savegame geladen – Saison {state['season']}, Spieltag {state['spieltag']}")
        season   = state["season"]
        spieltag = state["spieltag"]
        nord     = pd.DataFrame(state["nord"])
        sued     = pd.DataFrame(state["sued"])
        nsched   = state["nsched"]
        ssched   = state["ssched"]
        stats    = pd.DataFrame(state["stats"])
        history  = state.get("history", [])
    else:
        season   = get_next_season_number()
        spieltag = 1
        nord, sued = _init_frames()
        nsched  = create_schedule(nord_teams)
        ssched  = create_schedule(sued_teams)
        stats   = init_stats()
        history = []

    start_season   = season
    max_spieltage  = (len(nord_teams) - 1) * 2

    while (max_seasons is None) or ((season - start_season) < max_seasons):
        if interactive:
            input(f"➡️  Enter für Spieltag {spieltag} (Saison {season}) …")

        results_str: List[str] = []
        results_json: List[Dict[str, Any]] = []

        print("\n— Nord —")
        for m in nsched[:len(nord)//2]:
            s, j = simulate_match(nord, *m, stats, "Nord")
            print(s)
            results_str.append(s)
            results_json.append(j)
        nsched = nsched[len(nord)//2:]

        print("\n— Süd —")
        for m in ssched[:len(sued)//2]:
            s, j = simulate_match(sued, *m, stats, "Süd")
            print(s)
            results_str.append(s)
            results_json.append(j)
        ssched = ssched[len(sued)//2:]

        # Export JSON & Tabellen
        _print_tables(nord, sued, stats)
        save_spieltag_json(season, spieltag, results_json, nord, sued, stats)

        spieltag += 1

        # Autosave nach Spieltag
        save_state({
            "season": season,
            "spieltag": spieltag,  # schon +1
            "nord": nord.to_dict("records"),
            "sued": sued.to_dict("records"),
            "nsched": nsched,
            "ssched": ssched,
            "stats": stats.to_dict("records"),
            "history": history,
        })

        if spieltag > max_spieltage:
            print("\n🏁 Reguläre Saison beendet – Play-offs!")
            champion = run_playoffs(season, nord, sued, stats, interactive=interactive)

            # Saisonabschluss: History erweitern & nächsten Startzustand persistieren
            history_entry = {
                "season": season,
                "champion": champion,
                "finished_at": datetime.now().isoformat(),
            }
            history.append(history_entry)

            next_season_num = season + 1
            next_state = _init_new_season_state(next_season_num)
            next_state["history"] = history
            save_state(next_state)  # Start der nächsten Saison speichern

            print(f"🧭 Nächster Startpunkt gespeichert → Saison {next_season_num}, Spieltag 1")

            # für weiteren Lauf in DIESER Ausführung
            season   = next_state["season"]
            spieltag = next_state["spieltag"]
            nord     = pd.DataFrame(next_state["nord"])
            sued     = pd.DataFrame(next_state["sued"])
            nsched   = next_state["nsched"]
            ssched   = next_state["ssched"]
            stats    = pd.DataFrame(next_state["stats"])

            # Abbruch prüfen (relative Saisons)
            if (max_seasons is not None) and ((season - start_season) >= max_seasons):
                break


# ------------------------------------------------
# 8  SELF-TESTS
# ------------------------------------------------

def _self_tests() -> None:
    dummy = [{"Team": str(i)} for i in range(6)]
    assert len(create_schedule(dummy)) == 6 * 5, "Schedule wrong"
    fake_row = pd.Series({"Players": [{"Offense": 60, "Defense": 60, "Speed": 60, "Chemistry": 60} for _ in range(5)]})
    assert 0 < calc_strength(fake_row) < 100, "Strength out of range"
    print("✅ Self-Tests bestanden")
# ========= GUI-HELPER: EINEN SPIELTAG, PLAYOFFS, TABELLEN =====================

def read_tables_for_ui() -> dict:
    """Liest den aktuellen Save-Zustand und liefert Tabellen & Meta für die GUI."""
    state = load_state()
    if not state:
        # Frischer Startzustand, wenn nichts da ist
        season = get_next_season_number()
        base = _init_new_season_state(season)
        base["history"] = []
        save_state(base)
        state = base

    nord = pd.DataFrame(state["nord"])
    sued = pd.DataFrame(state["sued"])
    stats = pd.DataFrame(state["stats"])
    tables = _export_tables(nord, sued, stats)
    return {
        "season": state["season"],
        "spieltag": state["spieltag"],
        "nsched_len": len(state["nsched"]),
        "ssched_len": len(state["ssched"]),
        "tables": tables,
        "history": state.get("history", []),
    }


def step_regular_season_once() -> dict:
    """Simuliert GENAU EINEN Spieltag (ohne input). Gibt Kurzinfos zurück.
       Wenn Regular Season schon vorbei ist, passiert nichts.
    """
    state = load_state()
    if not state:
        # init
        season = get_next_season_number()
        state = _init_new_season_state(season)
        state["history"] = []
        save_state(state)

    season   = state["season"]
    spieltag = state["spieltag"]
    nord     = pd.DataFrame(state["nord"])
    sued     = pd.DataFrame(state["sued"])
    nsched   = state["nsched"]
    ssched   = state["ssched"]
    stats    = pd.DataFrame(state["stats"])

    max_spieltage = (len(nord_teams) - 1) * 2
    if spieltag > max_spieltage:
        # Regular Season beendet -> nichts tun
        return {"status": "season_over", "season": season, "spieltag": spieltag}

    results_json = []

    # NORD
    print("\n— Nord —")
    for m in nsched[:len(nord)//2]:
        s, j = simulate_match(nord, *m, stats, "Nord")
        print(s)
        results_json.append(j)
    nsched = nsched[len(nord)//2:]

    # SÜD
    print("\n— Süd —")
    for m in ssched[:len(sued)//2]:
        s, j = simulate_match(sued, *m, stats, "Süd")
        print(s)
        results_json.append(j)
    ssched = ssched[len(sued)//2:]

    # Export JSON & Tabellen
    _print_tables(nord, sued, stats)
    save_spieltag_json(season, spieltag, results_json, nord, sued, stats)

    # Autosave (+1 Spieltag)
    spieltag += 1
    save_state({
        "season": season,
        "spieltag": spieltag,
        "nord": nord.to_dict("records"),
        "sued": sued.to_dict("records"),
        "nsched": nsched,
        "ssched": ssched,
        "stats": stats.to_dict("records"),
        "history": state.get("history", []),
    })

    return {"status": "ok", "season": season, "spieltag": spieltag}


def simulate_full_playoffs_and_advance() -> dict:
    """Simuliert die GESAMTEN Playoffs (Bo7) und schließt die Saison ab:
       - schreibt History-Eintrag (Champion)
       - legt Startzustand der nächsten Saison ins Savefile
    """
    state = load_state()
    if not state:
        return {"status": "no_state"}

    season   = state["season"]
    nord     = pd.DataFrame(state["nord"])
    sued     = pd.DataFrame(state["sued"])
    stats    = pd.DataFrame(state["stats"])
    history  = state.get("history", [])

    champion = run_playoffs(season, nord, sued, stats, interactive=False)

    # Saisonabschluss
    history_entry = {"season": season, "champion": champion, "finished_at": datetime.now().isoformat()}
    history.append(history_entry)
    next_season_num = season + 1
    next_state = _init_new_season_state(next_season_num)
    next_state["history"] = history
    save_state(next_state)

    return {
        "status": "ok",
        "champion": champion,
        "next_season": next_season_num
    }
def step_playoffs_round_once() -> dict:
    """
    Simuliert GENAU EINE Playoff-Runde (Bo7-Serien in einem Rutsch).
    - Erzeugt runde_XX.json mit allen Serien
    - Schreibt Save-Progress:
        state["phase"] = "playoffs"
        state["playoff_round"] = N (1-basiert)
        state["playoff_alive"] = Reihenfolge der Sieger dieser Runde
    - Falls Champion ermittelt: History-Eintrag + Startzustand Saison+1
    Rückgabe:
      {"status": "ok", "round": int, "winners": [...]} oder
      {"status": "champion", "round": int, "champion": "...", "next_season": int} oder
      {"status": "regular_not_finished"} / {"status": "no_state"}
    """
    state = load_state()
    if not state:
        return {"status": "no_state"}

    # Tabellen/Stats in DataFrames
    nord = pd.DataFrame(state["nord"])
    sued = pd.DataFrame(state["sued"])
    stats = pd.DataFrame(state["stats"])
    history = state.get("history", [])

    # Regular Season schon vorbei?
    max_spieltage = (len(nord_teams) - 1) * 2
    if isinstance(state.get("spieltag"), int) and state["spieltag"] <= max_spieltage:
        return {"status": "regular_not_finished"}

    # Runde & Alive-Feld
    phase = state.get("phase")
    rnd = int(state.get("playoff_round", 1))
    alive: list[str] = state.get("playoff_alive", [])

    # Initiale Pairings ermitteln
    if rnd == 1 and not alive:
        pairings = _initial_playoff_pairings(nord, sued)
    else:
        # aus alive (Sieger der letzten Runde) neue Paarungen bilden
        if not alive or len(alive) < 2:
            return {"status": "invalid_playoff_state"}
        pairings = [(alive[i], alive[i + 1]) for i in range(0, len(alive), 2)]

    # komplette Runde simulieren (Bo7-Serien)
    round_series = []
    winners = []
    for a, b in pairings:
        series = simulate_series_best_of(a, b, nord, sued, stats)
        round_series.append(series)
        winners.append(series["winner"])
        print(f"• Serie: {series['result']}  → Sieger: {series['winner']}")

    # JSON-Dump runde_NN.json
    _save_json(
        PLAYOFF_DIR / f"saison_{state['season']}",
        f"runde_{rnd:02}.json",
        {
            "timestamp": datetime.now().isoformat(),
            "saison": state["season"],
            "runde": rnd,
            "series": round_series,
            **_export_tables(nord, sued, stats),
        },
    )

    # Champion?
    if len(winners) == 1:
        champion = winners[0]
        print(f"\n🏆  Champion Saison {state['season']}: {champion}  🏆\n")

        # History-Eintrag & Next-Season-Checkpoint
        history.append({
            "season": state["season"],
            "champion": champion,
            "finished_at": datetime.now().isoformat(),
        })
        next_season_num = state["season"] + 1
        next_state = _init_new_season_state(next_season_num)
        next_state["history"] = history
        save_state(next_state)

        return {"status": "champion", "round": rnd, "champion": champion, "next_season": next_season_num}

    # Fortschritt speichern (nächste Runde vorbereiten)
    save_state({
        "season": state["season"],
        "spieltag": f"Playoff_Runde_{rnd}",   # rein informativ
        "nord": nord.to_dict("records"),
        "sued": sued.to_dict("records"),
        "nsched": [], "ssched": [],
        "stats": stats.to_dict("records"),
        "history": history,
        "phase": "playoffs",
        "playoff_round": rnd + 1,
        "playoff_alive": winners,            # in dieser Reihenfolge geht es weiter
    })

    return {"status": "ok", "round": rnd, "winners": winners}


if __name__ == "__main__":
    _self_tests()
    print("\n⚡ Demo-Saison (interaktiv) startet —")
    run_simulation(max_seasons=1, interactive=True)
    print("\n🎉 Fertig. JSONs sind in den Verzeichnissen 'spieltage' und 'playoffs'.")
