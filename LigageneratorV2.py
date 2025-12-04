from __future__ import annotations

import json
import random
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional

import pandas as pd

# ------------------------------------------------
# Helper: DataFrame -> records ohne NaN
# ------------------------------------------------
def _df_to_records_clean(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Wandelt ein DataFrame in eine List[Dict] um und ersetzt dabei alle NaN/NA durch None,
    damit json.dump gültiges JSON (null) statt NaN schreibt.
    """
    clean = df.where(pd.notna(df), None)
    return clean.to_dict("records")


# ------------------------------------------------
# 1  PFADE
# ------------------------------------------------
SAVEFILE     = Path("saves/savegame.json")
SPIELTAG_DIR = Path("spieltage")
PLAYOFF_DIR  = Path("playoffs")
REPLAY_DIR   = Path("replays")  # <<< NEU: Ordner für Replay-JSONs

# ------------------------------------------------
# 2  TEAMS LADEN
# ------------------------------------------------
from realeTeams_live import nord_teams, sued_teams  # deine Datei mit Teams/Spielern

# ------------------------------------------------
# 3  SAVE/LOAD & INIT
# ------------------------------------------------
def _ensure_dirs() -> None:
    for p in (SAVEFILE.parent, SPIELTAG_DIR, PLAYOFF_DIR, REPLAY_DIR):
        p.mkdir(parents=True, exist_ok=True)

def get_next_season_number() -> int:
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

def load_state() -> Optional[Dict[str, Any]]:
    if SAVEFILE.exists() and SAVEFILE.stat().st_size > 0:
        with SAVEFILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    return None

def _init_frames() -> Tuple[pd.DataFrame, pd.DataFrame]:
    n = pd.DataFrame(nord_teams)
    s = pd.DataFrame(sued_teams)
    for d in (n, s):
        d[["Points","Goals For","Goals Against"]] = 0
    return n, s

def _init_new_season_state(season: int) -> Dict[str, Any]:
    nord, sued = _init_frames()

    # Standard-Schedule
    nsched = create_schedule(nord_teams)
    ssched = create_schedule(sued_teams)

    # Story-Constraints anwenden:
    # - Wir rufen es für beide Conferences auf.
    # - In der Conference, in der die Nova-Delta Panther + Augsburg Ferox NICHT existieren,
    #   passiert einfach nichts.
    nsched = _apply_story_constraints_to_schedule(nsched, nord_teams)
    ssched = _apply_story_constraints_to_schedule(ssched, sued_teams)

    stats = init_stats()
    return {
        "season": season,
        "spieltag": 1,
        "nord": _df_to_records_clean(nord),
        "sued": _df_to_records_clean(sued),
        "nsched": nsched,
        "ssched": ssched,
        "stats": _df_to_records_clean(stats),
        "history": [],
        "phase": "regular",
    }

# ------------------------------------------------
# 4  EXPORT-HILFEN
# ------------------------------------------------
def _export_tables(nord_df: pd.DataFrame, sued_df: pd.DataFrame, stats: pd.DataFrame) -> Dict[str, Any]:
    stats = stats.copy()
    stats["Points"] = stats["Goals"] + stats["Assists"]

    # Fallbacks für alte Savefiles: Spalten ggf. nachziehen
    if "Number" not in stats.columns:
        stats["Number"] = None
    if "PositionGroup" not in stats.columns:
        stats["PositionGroup"] = None

    def _prep(df: pd.DataFrame) -> List[Dict[str, Any]]:
        d = df.copy()
        d.rename(columns={"Goals For": "GF", "Goals Against": "GA"}, inplace=True)
        d["GD"] = d["GF"] - d["GA"]
        return d.sort_values(["Points", "GF"], ascending=False)[
            ["Team", "Points", "GF", "GA", "GD"]
        ].to_dict("records")

    # Top-Scorer-Liste bauen und NaN -> None cleanen
    top = stats.sort_values("Points", ascending=False).head(20)[
        ["Player", "Team", "Number", "PositionGroup", "Goals", "Assists", "Points"]
    ]

    return {
        "tabelle_nord": _prep(nord_df),
        "tabelle_sued": _prep(sued_df),
        "top_scorer": _df_to_records_clean(top),
    }


def _save_json(folder: Path, name: str, payload: Dict[str, Any]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / name).open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print("📦 JSON gespeichert →", folder / name)

def save_spieltag_json(
    season: int,
    gameday: int,
    results: List[Dict[str, Any]],
    nord: pd.DataFrame,
    sued: pd.DataFrame,
    stats: pd.DataFrame,
    *,
    debug: Optional[Dict[str, Any]] = None,  # <<< DEBUG-Hook
) -> None:
    payload: Dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "saison": season,
        "spieltag": gameday,
        "results": results,
        **_export_tables(nord, sued, stats),
    }
    if debug is not None:
        payload["debug"] = debug  # komplette Debug-Struktur pro Spieltag
    _save_json(SPIELTAG_DIR / f"saison_{season}", f"spieltag_{gameday:02}.json", payload)

# ------------------------------------------------
# 4b REPLAY-EXPORT (NEU)
# ------------------------------------------------
def save_replay_json(
    season: int,
    gameday: int,
    replay_matches: List[Dict[str, Any]],
) -> None:
    """
    Speichert:
      - pro Match eine Replay-Datei mit Events
      - ein replay_matchday.json mit Übersicht
    """
    base_folder = REPLAY_DIR / f"saison_{season}" / f"spieltag_{gameday:02}"
    base_folder.mkdir(parents=True, exist_ok=True)

    matchday_payload: Dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "season": season,
        "matchday": gameday,
        "games": [],
    }

    for idx, m in enumerate(replay_matches):
        home = m["home"]
        away = m["away"]
        g_home = m["g_home"]
        g_away = m["g_away"]
        conference = m.get("conference")

        # Einfacher Game-ID-Generator für jetzt:
        game_id = m.get("game_id") or f"{home}-{away}"

        game_payload = {
            "season": season,
            "matchday": gameday,
            "game_id": game_id,
            "conference": conference,
            "home": {
                "id": home,
                "name": home,
                "score": g_home,
            },
            "away": {
                "id": away,
                "name": away,
                "score": g_away,
            },
            "events": m.get("events", []),
        }

        _save_json(base_folder, f"{game_id}.json", game_payload)

        matchday_payload["games"].append({
            "game_id": game_id,
            "featured": False,  # später können wir Topspiele markieren
            "conference": conference,
            "home": home,
            "away": away,
            "g_home": g_home,
            "g_away": g_away,
        })

    _save_json(base_folder, "replay_matchday.json", matchday_payload)

# ------------------------------------------------
# 5  TERMINAL-AUSGABEN
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
    s = stats.copy()
    s["Points"] = s["Goals"] + s["Assists"]
    top20 = s.sort_values("Points", ascending=False).head(20)[
        ["Player", "Team", "Goals", "Assists", "Points"]
    ]
    print("\n⭐ Top-20 Scorer")
    print(top20.to_string(index=False))

# ------------------------------------------------
# 6  SIMULATIONSGRUNDSÄTZE + LINEUPS
# ------------------------------------------------

def _weighted_pick_by_gp(players: List[Dict[str, Any]], count: int, jitter_factor: float = 0.3) -> List[Dict[str, Any]]:
    """
    Wählt 'count' Spieler aus:
    - Basis = GamesPlayed
    - plus etwas Randomness (±30%), damit nicht immer starr dieselben spielen.
    """
    if not players or count <= 0:
        return []

    scored: List[Tuple[float, Dict[str, Any]]] = []
    for p in players:
        gp_raw = p.get("GamesPlayed") or 0
        try:
            gp = int(gp_raw)
        except (TypeError, ValueError):
            gp = 0
        noise = random.uniform(-jitter_factor * max(gp, 1), jitter_factor * max(gp, 1))
        score = gp + noise
        scored.append((score, p))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored[:count]]


def build_lineup(
    players: List[Dict[str, Any]],
    team_name: str = "UNKNOWN",
    n_def: int = 7,
    n_fwd: int = 12,
    n_goalies: int = 1,
) -> List[Dict[str, Any]]:
    """
    Baut ein Lineup pro Spiel:
      - 7 Defender
      - 12 Forwards
      - 1 Goalie
    Wenn zu wenig Spieler einer Gruppe vorhanden sind, nehmen wir so viele wie möglich.
    """
    if not players:
        return []

    ds = [p for p in players if str(p.get("PositionGroup", "")).upper() == "D"]
    fs = [p for p in players if str(p.get("PositionGroup", "")).upper() == "F"]
    gs = [p for p in players if str(p.get("PositionGroup", "")).upper() == "G"]

    lineup: List[Dict[str, Any]] = []
    lineup.extend(_weighted_pick_by_gp(ds, min(n_def, len(ds))))
    lineup.extend(_weighted_pick_by_gp(fs, min(n_fwd, len(fs))))

    if gs:
        lineup.extend(_weighted_pick_by_gp(gs, min(n_goalies, len(gs))))
    else:
        # Fallback, falls aus irgendeinem Grund kein Goalie markiert ist
        print("[WARN] Team ohne Goalies im Roster – kein G im Lineup.")
    
    # Sicherheitsnetz: Keine Duplikate
    seen_ids = set()
    unique_lineup: List[Dict[str, Any]] = []
    for p in lineup:
        key = (p.get("NameReal"), p.get("Number"))
        if key not in seen_ids:
            seen_ids.add(key)
            unique_lineup.append(p)

    # --- Debug-Check --------------------------------------
    d_count = sum(1 for p in unique_lineup if p.get("PositionGroup") == "D")
    f_count = sum(1 for p in unique_lineup if p.get("PositionGroup") == "F")
    g_count = sum(1 for p in unique_lineup if p.get("PositionGroup") == "G")

    if (d_count != n_def) or (f_count != n_fwd) or (g_count != n_goalies):
        print(f"\n[DEBUG][Lineup Warnung] Team: {team_name}")
        print(f"   → {d_count}D / {f_count}F / {g_count}G  (Soll: {n_def}D / {n_fwd}F / {n_goalies}G)")
        if d_count < n_def:
            print("   -> FEHLENDE Verteidiger:", n_def - d_count)
        if f_count < n_fwd:
            print("   -> FEHLENDE Stürmer:", n_fwd - f_count)
        if g_count < n_goalies:
            print("   -> KEIN GOALIE verfügbar!")

    # -------------------------------------------------------

    return unique_lineup

def _get_lineup_for_team(df: pd.DataFrame, team_name: str) -> List[Dict[str, Any]]:
    """
    Holt das Lineup eines Teams:
      - wenn df["Lineup"] existiert und Liste → das
      - sonst df["Players"]
    """
    mask = df["Team"] == team_name
    if not mask.any():
        print(f"[WARN] _get_lineup_for_team: Team '{team_name}' nicht in df gefunden")
        return []

    row = df.loc[mask].iloc[0]
    if "Lineup" in row and isinstance(row["Lineup"], list) and row["Lineup"]:
        return row["Lineup"]
    return row["Players"]

def prepare_lineups_for_matches(df: pd.DataFrame, matches: List[Tuple[str, str]]) -> None:
    """
    Für alle Teams, die an diesem Spieltag in 'matches' beteiligt sind,
    wird eine Lineup-Liste (7D/12F/1G) gebaut und in df["Lineup"] abgelegt.
    """
    teams_today = set()
    for home, away in matches:
        teams_today.add(home)
        teams_today.add(away)

    # sicherstellen, dass es die Spalte "Lineup" gibt
    if "Lineup" not in df.columns:
        df["Lineup"] = None

    for team_name in teams_today:
        mask = df["Team"] == team_name
        if not mask.any():
            print(f"[WARN] prepare_lineups_for_matches: Team '{team_name}' nicht in df gefunden")
            continue

        idx_list = df.index[mask].tolist()
        if not idx_list:
            print(f"[WARN] prepare_lineups_for_matches: Kein Index für Team '{team_name}' gefunden")
            continue

        idx = idx_list[0]  # genau eine Zeile pro Team
        players = df.at[idx, "Players"]
        lineup = build_lineup(players, team_name=team_name)
        df.at[idx, "Lineup"] = lineup

# -----------------------------------------------------
# DEBUG-Helfer: Tabellenansicht & Stärkevergleich & JSON-Payload
# -----------------------------------------------------

def _build_lineup_table(df: pd.DataFrame, matches: List[Tuple[str, str]]) -> pd.DataFrame:
    """
    Erzeugt eine flache Tabelle:
      Team | Rolle (Home/Away) | Gegner | Name | Pos | GP | OVR
    für alle Lineups eines Spieltags.
    """
    rows: List[Dict[str, Any]] = []
    for home, away in matches:
        for team_name, role, opponent in [(home, "Home", away), (away, "Away", home)]:
            lineup = _get_lineup_for_team(df, team_name)
            for p in lineup:
                rows.append({
                    "Team": team_name,
                    "Rolle": role,
                    "Gegner": opponent,
                    "Name": p.get("NameReal") or p.get("Name"),
                    "Pos": p.get("PositionGroup") or p.get("PositionRaw"),
                    "GP": p.get("GamesPlayed"),
                    "OVR": p.get("Overall"),
                })
    if not rows:
        return pd.DataFrame(columns=["Team", "Rolle", "Gegner", "Name", "Pos", "GP", "OVR"])
    df_out = pd.DataFrame(rows)
    # Sortierung: nach Team, Rolle, OVR runter
    df_out = df_out.sort_values(["Team", "Rolle", "OVR"], ascending=[True, True, False])
    return df_out

def _build_strength_panel(df: pd.DataFrame, matches: List[Tuple[str, str]]) -> pd.DataFrame:
    """
    Stärkevergleich-Panel:
      Home | Away | Home_OVR | Away_OVR | Diff
    basiert auf Durchschnitt der Overall-Ratings im Lineup.
    """
    rows: List[Dict[str, Any]] = []
    for home, away in matches:
        lu_home = _get_lineup_for_team(df, home)
        lu_away = _get_lineup_for_team(df, away)

        def avg_ovr(lineup: List[Dict[str, Any]]) -> float:
            vals = [p.get("Overall") for p in lineup if isinstance(p.get("Overall"), (int, float))]
            if not vals:
                return 0.0
            return round(sum(vals) / len(vals), 1)

        home_ovr = avg_ovr(lu_home)
        away_ovr = avg_ovr(lu_away)

        rows.append({
            "Home": home,
            "Away": away,
            "Home_OVR": home_ovr,
            "Away_OVR": away_ovr,
            "Diff": round(home_ovr - away_ovr, 1),
        })

    if not rows:
        return pd.DataFrame(columns=["Home", "Away", "Home_OVR", "Away_OVR", "Diff"])
    return pd.DataFrame(rows)

def _build_debug_matches_payload(df: pd.DataFrame, matches: List[Tuple[str, str]]) -> List[Dict[str, Any]]:
    """
    JSON-Debug-Struktur pro Match:
      - Home/Away
      - Lineups (komplett)
      - Durchschnitts-OVR
    """
    debug_matches: List[Dict[str, Any]] = []

    for home, away in matches:
        lu_home = _get_lineup_for_team(df, home)
        lu_away = _get_lineup_for_team(df, away)

        def avg_ovr(lineup: List[Dict[str, Any]]) -> float:
            vals = [p.get("Overall") for p in lineup if isinstance(p.get("Overall"), (int, float))]
            if not vals:
                return 0.0
            return round(sum(vals) / len(vals) / 1.0, 1)

        debug_matches.append({
            "home": {
                "team": home,
                "avg_overall": avg_ovr(lu_home),
                "lineup": lu_home,
            },
            "away": {
                "team": away,
                "avg_overall": avg_ovr(lu_away),
                "lineup": lu_away,
            },
        })

    return debug_matches


def calc_strength(row: pd.Series, home: bool = False) -> float:
    # WICHTIG: Wenn es ein Lineup gibt, benutzen wir das. Sonst das komplette Roster.
    players = row.get("Lineup")
    if not isinstance(players, list) or not players:
        players = row["Players"]

    base = (
        sum(p["Offense"]   for p in players) * 0.4 +
        sum(p["Defense"]   for p in players) * 0.3 +
        sum(p["Speed"]     for p in players) * 0.2 +
        sum(p["Chemistry"] for p in players) * 0.1
    ) / len(players)

    total = base
    # Tagesform / Randomness
    total *= 1 + random.uniform(-5, 5) / 100
    # Momentum (falls du das später nutzt)
    total *= 1 + row.get("Momentum", 0) / 100
    # Heimvorteil
    total *= 1 + (3 if home else 0) / 100
    # kleine Zusatz-Streuung
    total *= 1 + random.uniform(-1, 2) / 100
    return round(total, 2)


# ------------------------------------------------
# 6b  STORY-CONSTRAINT-HELPER für Spielplan
# ------------------------------------------------

def _find_team_name_by_keywords(teams: List[Dict[str, Any]], keywords: List[str]) -> Optional[str]:
    """
    Sucht in der Teamliste nach einem Teamnamen, der alle Keywords (case-insensitive)
    im String enthält. Damit sind wir robuster gegen Schreibweisen wie
    'NOVADELTA Panther', 'Nova-Delta-Panther', 'Augsburg Ferox', etc.
    """
    kws = [k.lower() for k in keywords]
    for t in teams:
        name = str(t.get("Team", ""))
        low = name.lower()
        if all(k in low for k in kws):
            return name
    return None


def _apply_story_constraints_to_schedule(
    sched: List[Tuple[str, str]],
    teams: List[Dict[str, Any]],
) -> List[Tuple[str, str]]:
    """
    Erzwingt für NOVADELTA Panther:
      - erstes Saisonspiel = Heimspiel
      - drittes Saisonspiel (2. Heimspiel) = Heimspiel gegen Augsburg Ferox

    Falls die Teams nicht gefunden werden, bleibt der Spielplan unverändert.
    """
    nova = _find_team_name_by_keywords(teams, ["nova", "panther"])
    augs = _find_team_name_by_keywords(teams, ["augs", "ferox"])

    if not nova:
        return sched  # Team nicht in dieser Conference → nichts erzwingen
    # Augsburg darf theoretisch in der anderen Conference liegen; dann können wir nur
    # "erstes Spiel Heim" garantieren, aber nicht den Gegner.
    # Deshalb kein harter Abort, wenn augs == None.

    # 1) Erstes Spiel der Nova-Delta-Panther = Heimspiel
    indices = [i for i, (h, a) in enumerate(sched) if h == nova or a == nova]
    if not indices:
        return sched  # irgendwas stimmt fundamental nicht

    first_idx = indices[0]
    if sched[first_idx][0] != nova:
        # wir suchen das erste Spiel, in dem NOVADELTA bereits Heimteam ist
        home_indices = [i for i in indices if sched[i][0] == nova]
        if home_indices:
            swap_idx = home_indices[0]
            sched[first_idx], sched[swap_idx] = sched[swap_idx], sched[first_idx]

    # 2) Drittes Spiel der Nova-Delta-Panther = Heim vs Augsburg-Ferox
    #    (nur, wenn Augsburg auch in dieser Teams-Liste existiert)
    if not augs:
        return sched

    # Indizes nach möglicher Verschiebung neu berechnen
    indices = [i for i, (h, a) in enumerate(sched) if h == nova or a == nova]
    if len(indices) < 3:
        # Zu wenig Spiele in diesem Block, um ein "3. Spiel" zu erzwingen
        return sched

    third_idx = indices[2]

    # Index des Spiels NOVADELTA (Home) vs Augsburg
    target_idx: Optional[int] = None
    for i, (h, a) in enumerate(sched):
        if h == nova and a == augs:
            target_idx = i
            break

    if target_idx is None:
        # es gibt kein Heimspiel NOVADELTA vs Augsburg in diesem Schedule-Array
        # (z. B. weil Conference anders getrennt ist)
        return sched

    # Wir wollen, dass genau an Position 'third_idx' das Spiel (nova, augs) liegt
    if target_idx != third_idx:
        sched[target_idx], sched[third_idx] = sched[third_idx], sched[target_idx]

    return sched

def _find_team_name_by_keywords(teams: List[Dict[str, Any]], keywords: List[str]) -> Optional[str]:
    """
    Sucht in der Teamliste nach einem Teamnamen, in dem ALLE Keywords (case-insensitive) vorkommen.
    Beispiel: keywords=["nova","panther"] matcht "Nova-Delta Panther".
    """
    kws = [k.lower() for k in keywords]
    for t in teams:
        name = str(t.get("Team", ""))
        low = name.lower()
        if all(k in low for k in kws):
            return name
    return None


def _apply_story_constraints_to_schedule(
    sched: List[Tuple[str, str]],
    teams: List[Dict[str, Any]],
) -> List[Tuple[str, str]]:
    """
    Erzwingt für EINEN Conference-Spielplan (Nord ODER Süd) die Story-Regeln für die Nova-Delta Panther:

      1. 1. Spiel der Nova-Delta Panther = Heimspiel.
      2. 2. Spiel der Nova-Delta Panther = Auswärtsspiel (wenn sinnvoll machbar).
      3. 3. Spiel der Nova-Delta Panther = Heimspiel GEGEN Augsburg Ferox (wenn beide im selben Conference-Teams-Array sind).

    WICHTIG:
      - Wir permutieren nur EXISTIERENDE Spiele (Swap von ganzen Paarungen).
      - Round-Robin-Struktur bleibt intakt.
      - Wenn Nova/Augsburg in dieser Conference nicht existieren, macht die Funktion nichts.
    """
    # Teamnamen anhand Keywords suchen
    nova = _find_team_name_by_keywords(teams, ["nova", "panther"])
    augs = _find_team_name_by_keywords(teams, ["augs", "ferox"])

    # Wenn Nova-Delta in dieser Conference gar nicht existiert: nichts tun
    if not nova:
        return sched

    # "half" = Anzahl Spiele pro Spieltag in dieser Conference
    if len(teams) % 2 == 0:
        half = len(teams) // 2
    else:
        # Falls BYE verwendet wird, wäre hier theoretisch +1, aber da Nova nie BYE spielt,
        # reicht die einfache Berechnung.
        half = (len(teams) + 1) // 2

    def recompute_nd_games() -> List[Dict[str, Any]]:
        nd_games: List[Dict[str, Any]] = []
        for idx, (h, a) in enumerate(sched):
            if h == nova or a == nova:
                day = idx // half  # 0-basierter Spieltag
                nd_games.append({
                    "idx": idx,
                    "day": day,
                    "home": (h == nova),
                    "opp": a if h == nova else h,
                })
        nd_games.sort(key=lambda x: x["day"])
        return nd_games

    nd_games = recompute_nd_games()
    if len(nd_games) == 0:
        return sched

    # --------------------------------------------------------
    # Schritt 1: 3. Spiel = Heim vs Augsburg (falls möglich)
    # --------------------------------------------------------
    if len(nd_games) >= 3 and augs:
        nd_games = recompute_nd_games()

        # Finde ein Spiel Nova HEIM gegen Augsburg
        aug_home_game = None
        for g in nd_games:
            if g["home"] and g["opp"] == augs:
                aug_home_game = g
                break

        if aug_home_game is not None:
            # 3. Spiel (chronologisch nach Spieltag)
            third = nd_games[2]  # index 2 = 3. Spiel
            if third["idx"] != aug_home_game["idx"]:
                i1 = third["idx"]
                i2 = aug_home_game["idx"]
                sched[i1], sched[i2] = sched[i2], sched[i1]
                nd_games = recompute_nd_games()

    # --------------------------------------------------------
    # Schritt 2: 1. Spiel = Heimspiel
    # --------------------------------------------------------
    nd_games = recompute_nd_games()
    first = nd_games[0]
    if not first["home"]:
        # Wir wollen ein anderes Nova-Heimspiel an diese Stelle ziehen,
        # aber nicht das festgelegte 3. Spiel kaputtmachen.
        avoid_idx = nd_games[2]["idx"] if len(nd_games) >= 3 else None
        swap_candidate = None
        for g in nd_games[1:]:
            if g["home"] and g["idx"] != avoid_idx:
                swap_candidate = g
                break

        if swap_candidate is not None:
            i1 = first["idx"]
            i2 = swap_candidate["idx"]
            sched[i1], sched[i2] = sched[i2], sched[i1]
            nd_games = recompute_nd_games()

    # --------------------------------------------------------
    # Schritt 3: 2. Spiel = Auswärtsspiel (wenn möglich)
    # --------------------------------------------------------
    nd_games = recompute_nd_games()
    if len(nd_games) >= 2:
        second = nd_games[1]
        if second["home"]:
            # Suche ein späteres Auswärtsspiel, das NICHT das 3. Spiel ist
            avoid_idx = nd_games[2]["idx"] if len(nd_games) >= 3 else None
            swap_candidate = None
            for g in nd_games[2:]:
                if (not g["home"]) and g["idx"] != avoid_idx:
                    swap_candidate = g
                    break

            if swap_candidate is not None:
                i1 = second["idx"]
                i2 = swap_candidate["idx"]
                sched[i1], sched[i2] = sched[i2], sched[i1]
                nd_games = recompute_nd_games()

    return sched



def create_schedule(teams: List[Dict[str,Any]]) -> List[Tuple[str,str]]:
    # Original-Teams sichern, bevor wir BYE etc. reinmurksen
    original_teams = teams.copy()

    teams = teams.copy()
    if len(teams)%2:
        teams.append({"Team":"BYE"})
    days, half = len(teams)-1, len(teams)//2
    sched: List[Tuple[str, str]] = []
    for d in range(days*2):
        day=[]
        for i in range(half):
            a,b = teams[i]["Team"],teams[-i-1]["Team"]
            day.append((a,b) if d%2==0 else (b,a))
        sched.extend(day)
        teams.insert(1,teams.pop())

    # STORY-CONSTRAINTS anwenden (Nova-Delta-Panther, Augsburg-Ferox)
    sched = _apply_story_constraints_to_schedule(sched, original_teams)
    return sched


def update_player_stats(team: str, goals: int, df: pd.DataFrame, stats: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Aktualisiert Stats für 'goals' Tore eines Teams und liefert pro Tor:
      {
        "scorer": <Fake-Name>,
        "scorer_number": <Rückennummer oder None>,
        "assist": <Fake-Name oder None>,
        "assist_number": <Rückennummer oder None>
      }
    zurück.

    WICHTIG: Wir nutzen "Name" als ID für Stats + Replay.
    """
    # Roster aus Lineup, falls vorhanden – sonst Fallback auf komplettes Roster
    mask = df["Team"] == team
    if not mask.any() or goals <= 0:
        return []

    use_column = "Players"
    if "Lineup" in df.columns:
        candidate = df.loc[mask, "Lineup"].iloc[0]
        if isinstance(candidate, list) and candidate:
            use_column = "Lineup"

    roster = df.loc[mask, use_column].iloc[0]
    # Für Stats ggf. auf 18 Spieler begrenzen
    roster = random.sample(roster, 18) if len(roster) > 18 else roster

    # --- Skater-Pool: komplett ohne Goalies (für Tore UND Assists) ----------
    skaters = [
        p for p in roster
        if str(p.get("PositionGroup", "")).upper() != "G"
    ]

    # Fallback: falls aus irgendeinem Grund keine Skater markiert sind,
    # nimm das ganze Roster, damit die Simulation nicht crasht.
    if not skaters:
        skaters = roster

    # Pool + Gewichte
    scorer_pool = skaters
    scorer_names = [p["Name"] for p in scorer_pool]
    scorer_weights = [max(1, int(p.get("Offense", 50)) // 5) for p in scorer_pool]

    goal_events: List[Dict[str, Any]] = []

    for _ in range(goals):
        # --- Torschütze (nur Skater) ----------------------------------------
        scorer_player = random.choices(scorer_pool, weights=scorer_weights)[0]
        scorer_name = scorer_player["Name"]
        scorer_number = scorer_player.get("Number")

        # Stats-Update für den Torschützen
        stats.loc[stats["Player"] == scorer_name, "Goals"] += 1

        # --- Assistent (optional, auch nur Skater, != Torschütze) -----------
        assist_name = None
        assist_number = None

        assist_candidates = [p for p in skaters if p.get("Name") != scorer_name]
        if assist_candidates:
            assist_player = random.choice(assist_candidates)
            assist_name = assist_player["Name"]
            assist_number = assist_player.get("Number")
            stats.loc[stats["Player"] == assist_name, "Assists"] += 1

        goal_events.append(
            {
                "scorer": scorer_name,
                "scorer_number": scorer_number,
                "assist": assist_name,
                "assist_number": assist_number,
            }
        )

    return goal_events



def simulate_match(df: pd.DataFrame,
                   home: str,
                   away: str,
                   stats: pd.DataFrame,
                   conf: str) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
    """
    Simuliert EIN Spiel:
      - Ergebnis + Tabellenupdate + Spielerstats
      - Replay-Struct mit Aktionen:
        * action_id: int
        * step_in_action: 0..3
        * Zonenfolge: defensiv -> neutral -> offensiv -> offensiv (Abschluss)
        * result: "goal" oder "none"
        * player_main / player_secondary (Fake-Namen aus 'Name')
    """

    # --- Ergebnis & Tabellen wie bisher ------------------------------------
    r_h = df[df["Team"] == home].iloc[0]
    r_a = df[df["Team"] == away].iloc[0]

    strength_home = calc_strength(r_h, True)
    strength_away = calc_strength(r_a, False)
    p_home = strength_home / (strength_home + strength_away)

    g_home = max(0, int(random.gauss(p_home * 5, 1)))
    g_away = max(0, int(random.gauss((1 - p_home) * 5, 1)))

    # Tabelle updaten
    df.loc[df["Team"] == home, ["Goals For", "Goals Against"]] += [g_home, g_away]
    df.loc[df["Team"] == away, ["Goals For", "Goals Against"]] += [g_away, g_home]

    if g_home > g_away:
        df.loc[df["Team"] == home, "Points"] += 3
    elif g_away > g_home:
        df.loc[df["Team"] == away, "Points"] += 3
    else:
        df.loc[df["Team"].isin([home, away]), "Points"] += 1

    # Spielerstats (unabhängig von Replay)
    update_player_stats(home, g_home, df, stats)
    update_player_stats(away, g_away, df, stats)

    res_str = f"{home} {g_home}:{g_away} {away}"
    res_json = {
        "home": home,
        "away": away,
        "g_home": g_home,
        "g_away": g_away,
        "conference": conf,
    }

    # --- Hilfsfunktionen für Replay-Events ---------------------------------
    def _get_skaters(team_name: str) -> List[Dict[str, Any]]:
        mask = df["Team"] == team_name
        if not mask.any():
            return []

        row = df[mask].iloc[0]
        players = row.get("Lineup") or row["Players"]
        skaters = [p for p in players
                   if str(p.get("PositionGroup", "")).upper() != "G"]
        return skaters or players

    sk_home = _get_skaters(home)
    sk_away = _get_skaters(away)

    def _pick_pair(team_key: str) -> Tuple[Optional[str], Optional[int], Optional[str], Optional[int]]:
        sk = sk_home if team_key == "home" else sk_away
        if not sk:
            return None, None, None, None
        shooter = random.choice(sk)
        others = [p for p in sk if p is not shooter]
        assister = random.choice(others) if others else None
        return (
            shooter.get("Name"),
            shooter.get("Number"),
            assister.get("Name") if assister else None,
            assister.get("Number") if assister else None,
        )

    # --- Aktionenliste bauen -----------------------------------------------
    events: List[Dict[str, Any]] = []
    current_index = 0
    action_id = 0

    total_goals = g_home + g_away
    goal_actions: List[Optional[str]] = ["home"] * g_home + ["away"] * g_away

    # Extra-Aktionen ohne Tor für schönere Zwischenphasen
    extra_no_goal = max(2, len(goal_actions))  # mindestens so viele No-Goal-Actions wie Toraktionen
    goal_actions += [None] * extra_no_goal

    random.shuffle(goal_actions)

    for team_key_raw in goal_actions:
        if team_key_raw is None:
            team_key = random.choice(["home", "away"])
            is_goal = False
        else:
            team_key = team_key_raw
            is_goal = True

        player_main, player_main_number, player_secondary, player_secondary_number = _pick_pair(team_key)

        # 4-Schritte-Aktion:
        # 0: Aufbau hinten
        # 1: Durch neutrale Zone
        # 2: Druck in offensiver Zone
        # 3: Abschluss (mit/ohne Tor)
        seq: List[Tuple[str, str, str]] = [
            ("build_up", "defensive", "none"),
            ("attack", "neutral", "none"),
            ("attack", "offensive", "none"),
        ]
        if is_goal:
            seq.append(("goal", "offensive", "goal"))
        else:
            seq.append(("attack", "offensive", "none"))

        for step, (ev_type, zone, result) in enumerate(seq):
            events.append({
                "i": current_index,
                "t": current_index,           # einfache Timeline
                "action_id": action_id,
                "step_in_action": step,
                "team": team_key,             # "home" / "away"
                "zone": zone,                 # "defensive" / "neutral" / "offensive"
                "type": ev_type,              # "build_up" / "attack" / "goal"
                "result": result,             # "goal" / "none"
                "player_main": player_main,
                "player_main_number": player_main_number,
                "player_secondary": player_secondary,
                "player_secondary_number": player_secondary_number,
                "details": {},
            })
            current_index += 1

        action_id += 1

    replay_struct: Dict[str, Any] = {
        "home": home,
        "away": away,
        "g_home": g_home,
        "g_away": g_away,
        "conference": conf,
        "events": events,
    }

    return res_str, res_json, replay_struct




def init_stats() -> pd.DataFrame:
    rows = []
    for t in nord_teams + sued_teams:
        team_name = t["Team"]
        for p in t["Players"]:
            rows.append({
                "Player": p["Name"],
                "Team": team_name,
                "Number": p.get("Number"),
                "PositionGroup": p.get("PositionGroup"),
                "Goals": 0,
                "Assists": 0,
            })
    return pd.DataFrame(rows)


# ------------------------------------------------
# 7  PLAYOFFS – SERIEN (Bo7)
# ------------------------------------------------
def _initial_playoff_pairings(nord: pd.DataFrame, sued: pd.DataFrame) -> List[Tuple[str, str]]:
    nord4 = nord.sort_values(["Points", "Goals For"], ascending=False).head(4)
    sued4 = sued.sort_values(["Points", "Goals For"], ascending=False).head(4)
    return [
        (nord4.iloc[0]["Team"], sued4.iloc[3]["Team"]),
        (nord4.iloc[1]["Team"], sued4.iloc[2]["Team"]),
        (nord4.iloc[2]["Team"], sued4.iloc[1]["Team"]),
        (nord4.iloc[3]["Team"], sued4.iloc[0]["Team"]),
    ]

def simulate_playoff_match(a: str, b: str,
                           nord: pd.DataFrame,
                           sued: pd.DataFrame,
                           stats: pd.DataFrame) -> Tuple[str, str, Dict[str,int]]:
    dfA = nord if a in list(nord["Team"]) else sued
    dfB = nord if b in list(nord["Team"]) else sued

    # Für jedes Playoff-Spiel eigenes Lineup bauen
    prepare_lineups_for_matches(dfA, [(a, a)])  # Dummy-Paarung nur für Team a
    prepare_lineups_for_matches(dfB, [(b, b)])  # Dummy-Paarung nur für Team b

    rA = dfA[dfA["Team"] == a].iloc[0]
    rB = dfB[dfB["Team"] == b].iloc[0]
    pA = calc_strength(rA, True)
    pB = calc_strength(rB, False)
    prob = pA / (pA + pB)
    gA = max(0, int(random.gauss(prob * 5, 1)))
    gB = max(0, int(random.gauss((1 - prob) * 5, 1)))
    update_player_stats(a, gA, dfA, stats)
    update_player_stats(b, gB, dfB, stats)
    return f"{a} {gA}:{gB} {b}", (a if gA > gB else b), {"g_home": gA, "g_away": gB}

def simulate_series_best_of(a: str, b: str,
                            nord: pd.DataFrame,
                            sued: pd.DataFrame,
                            stats: pd.DataFrame,
                            wins_needed: int = 4) -> Dict[str, Any]:
    winsA = winsB = 0
    games = []
    gnum = 1
    while winsA < wins_needed and winsB < wins_needed:
        res, winner, goals = simulate_playoff_match(a, b, nord, sued, stats)
        g_home, g_away = goals["g_home"], goals["g_away"]
        if winner == a:
            winsA += 1
        else:
            winsB += 1
        games.append({
            "g": gnum, "home": a, "away": b,
            "g_home": g_home, "g_away": g_away,
            "winner": winner
        })
        gnum += 1
    return {
        "a": a, "b": b,
        "games": games,
        "result": f"{winsA}:{winsB}",
        "winner": a if winsA > winsB else b
    }

def run_playoffs(season: int,
                 nord: pd.DataFrame,
                 sued: pd.DataFrame,
                 stats: pd.DataFrame,
                 *,
                 interactive: bool = True) -> str:
    """Simuliert komplette Playoffs in Runden, speichert runde_XX.json, gibt Champion zurück."""
    rnd = 1
    pairings = _initial_playoff_pairings(nord, sued)
    while True:
        if interactive:
            input(f"➡️  Enter für Play-off-Runde {rnd} (Saison {season}) …")
        round_series = []
        winners = []
        print(f"\n=== PLAY-OFF RUNDE {rnd} (Saison {season}) ===")
        for a, b in pairings:
            series = simulate_series_best_of(a, b, nord, sued, stats)
            round_series.append(series)
            winners.append(series["winner"])
            print(f"• Serie: {a} vs {b} → {series['result']}  Sieger: {series['winner']}")
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
        save_state({  # Fortschritt (Info)
            "season": season,
            "spieltag": f"Playoff_Runde_{rnd}",
            "nord": _df_to_records_clean(nord),
            "sued": _df_to_records_clean(sued),
            "nsched": [], "ssched": [],
            "stats": _df_to_records_clean(stats),
            "phase": "playoffs",
            "playoff_round": rnd + 1,
            "playoff_alive": winners
        })
        if len(winners) == 1:
            champion = winners[0]
            print(f"\n🏆  Champion Saison {season}: {champion}  🏆\n")
            return champion
        pairings = [(winners[i], winners[i+1]) for i in range(0, len(winners), 2)]
        rnd += 1

# ------------------------------------------------
# 8  STEP-APIS FÜR GUI
# ------------------------------------------------
def read_tables_for_ui() -> Dict[str, Any]:
    state = load_state()
    if not state:
        season = get_next_season_number()
        base = _init_new_season_state(season)
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

def step_regular_season_once() -> Dict[str, Any]:
    state = load_state()
    if not state:
        season = get_next_season_number()
        state = _init_new_season_state(season)
        save_state(state)
    season   = state["season"]
    spieltag = state["spieltag"]
    nord     = pd.DataFrame(state["nord"])
    sued     = pd.DataFrame(state["sued"])
    nsched   = state["nsched"]
    ssched   = state["ssched"]
    stats    = pd.DataFrame(state["stats"])
    max_spieltage = (len(nord_teams)-1)*2
    if isinstance(spieltag, int) and spieltag > max_spieltage:
        return {"status": "season_over", "season": season, "spieltag": spieltag}

    results_json: List[Dict[str, Any]] = []
    replay_matches: List[Dict[str, Any]] = []  # NEU: Replay-Infos sammeln

    # --- NORD ---
    print("\n— Nord —")
    today_nord_matches = nsched[:len(nord)//2]
    prepare_lineups_for_matches(nord, today_nord_matches)

    # DEBUG: Lineup-Tabelle + Stärkevergleich
    lineup_table_nord = _build_lineup_table(nord, today_nord_matches)
    if not lineup_table_nord.empty:
        print("\n📋 Lineups Nord (heute):")
        print(lineup_table_nord.to_string(index=False))
    strength_nord = _build_strength_panel(nord, today_nord_matches)
    if not strength_nord.empty:
        print("\n⚖️ Stärkevergleich Nord:")
        print(strength_nord.to_string(index=False))

    for m in today_nord_matches:
        s,j,replay = simulate_match(nord,*m,stats,"Nord")
        print(s)
        results_json.append(j)
        replay_matches.append(replay)
    nsched=nsched[len(nord)//2:]

    # --- SÜD ---
    print("\n— Süd —")
    today_sued_matches = ssched[:len(sued)//2]
    prepare_lineups_for_matches(sued, today_sued_matches)

    lineup_table_sued = _build_lineup_table(sued, today_sued_matches)
    if not lineup_table_sued.empty:
        print("\n📋 Lineups Süd (heute):")
        print(lineup_table_sued.to_string(index=False))
    strength_sued = _build_strength_panel(sued, today_sued_matches)
    if not strength_sued.empty:
        print("\n⚖️ Stärkevergleich Süd:")
        print(strength_sued.to_string(index=False))

    for m in today_sued_matches:
        s,j,replay = simulate_match(sued,*m,stats,"Süd")
        print(s)
        results_json.append(j)
        replay_matches.append(replay)
    ssched=ssched[len(sued)//2:]

    _print_tables(nord,sued,stats)

    # JSON-Debug-Payload pro Spieltag
    debug_payload = {
        "nord_matches": _build_debug_matches_payload(nord, today_nord_matches),
        "sued_matches": _build_debug_matches_payload(sued, today_sued_matches),
    }

    save_spieltag_json(
        season,
        spieltag,
        results_json,
        nord,
        sued,
        stats,
        debug=debug_payload,
    )

    # NEU: Replay-JSON für den Spieltag sichern
    save_replay_json(
        season,
        spieltag,
        replay_matches,
    )

    spieltag+=1
    save_state({
        "season": season, "spieltag": spieltag,
        "nord": _df_to_records_clean(nord),
        "sued": _df_to_records_clean(sued),
        "nsched": nsched, "ssched": ssched,
        "stats": _df_to_records_clean(stats),
        "history": state.get("history", []),
        "phase": "regular",
    })
    return {"status":"ok","season":season,"spieltag":spieltag}

def simulate_full_playoffs_and_advance() -> Dict[str, Any]:
    state = load_state()
    if not state:
        return {"status": "no_state"}
    season = state["season"]
    nord   = pd.DataFrame(state["nord"])
    sued   = pd.DataFrame(state["sued"])
    stats  = pd.DataFrame(state["stats"])
    history= state.get("history", [])
    champion = run_playoffs(season, nord, sued, stats, interactive=False)
    history.append({"season": season, "champion": champion, "finished_at": datetime.now().isoformat()})
    next_season_num = season + 1
    next_state = _init_new_season_state(next_season_num)
    next_state["history"] = history
    save_state(next_state)
    return {"status": "ok", "champion": champion, "next_season": next_season_num}

def step_playoffs_round_once() -> Dict[str, Any]:
    """
    Simuliert GENAU EINE Playoff-Runde (Bo7-Serien).
    Speichert runde_XX.json; bei Champion: History + Saison+1.
    """
    state = load_state()
    if not state:
        return {"status": "no_state"}
    nord = pd.DataFrame(state["nord"]); sued = pd.DataFrame(state["sued"])
    stats = pd.DataFrame(state["stats"]); history = state.get("history", [])
    max_spieltage = (len(nord_teams)-1)*2
    if isinstance(state.get("spieltag"), int) and state["spieltag"] <= max_spieltage:
        return {"status":"regular_not_finished"}
    rnd = int(state.get("playoff_round", 1))
    alive = state.get("playoff_alive", [])
    if rnd == 1 and not alive:
        pairings = _initial_playoff_pairings(nord, sued)
    else:
        if not alive or len(alive) < 2:
            return {"status":"invalid_playoff_state"}
        pairings = [(alive[i], alive[i+1]) for i in range(0, len(alive), 2)]
    round_series=[]; winners=[]
    for a,b in pairings:
        series = simulate_series_best_of(a,b,nord,sued,stats)
        round_series.append(series); winners.append(series["winner"])
        print(f"• Serie: {a} vs {b} → {series['result']}  Sieger: {series['winner']}")
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
    if len(winners)==1:
        champion=winners[0]
        history.append({"season": state["season"], "champion": champion, "finished_at": datetime.now().isoformat()})
        next_season_num = state["season"]+1
        next_state=_init_new_season_state(next_season_num)
        next_state["history"]=history
        save_state(next_state)
        return {"status":"champion","round":rnd,"champion":champion,"next_season":next_season_num}
    save_state({
        "season": state["season"],
        "spieltag": f"Playoff_Runde_{rnd}",
        "nord": _df_to_records_clean(nord),
        "sued": _df_to_records_clean(sued),
        "nsched": [], "ssched": [],

        "stats": _df_to_records_clean(stats),
        "history": history,
        "phase": "playoffs",
        "playoff_round": rnd+1,
        "playoff_alive": winners,
    })
    return {"status":"ok","round":rnd,"winners":winners}

# ------------------------------------------------
# 9  RUN-SIMULATION (für GUI-Button)
# ------------------------------------------------
def run_simulation(max_seasons: int = 1, interactive: bool = False) -> None:
    """
    Simuliert max_seasons Saisons komplett (Hauptrunde + Playoffs).
    Wird von der Streamlit-GUI verwendet.
    """
    for _ in range(max_seasons):
        # ensure State existiert
        state = load_state()
        if not state:
            season = get_next_season_number()
            state = _init_new_season_state(season)
            save_state(state)

        # Regular Season
        while True:
            res = step_regular_season_once()
            if res.get("status") == "season_over":
                break
            if interactive:
                print(f"Spieltag {res.get('spieltag')} simuliert")

        # Playoffs komplett
        po_res = simulate_full_playoffs_and_advance()
        if interactive:
            print(f"Saison abgeschlossen. Champion: {po_res.get('champion')}.")

# ------------------------------------------------
# 10  SELF-TEST & DEMO (CLI)
# ------------------------------------------------
def _self_tests()->None:
    dummy=[{"Team":str(i)} for i in range(6)]
    assert len(create_schedule(dummy))==6*5, "Schedule wrong"
    fake_row=pd.Series({"Players":[{"Offense":60,"Defense":60,"Speed":60,"Chemistry":60} for _ in range(5)]})
    assert 0<calc_strength(fake_row)<100, "Strength out of range"
    print("✅ Self-Tests bestanden")

if __name__ == "__main__":
    _ensure_dirs()
    _self_tests()

    state = load_state()
    if not state:
        season = get_next_season_number()
        state = _init_new_season_state(season)
        save_state(state)
        print(f"\n🎬 Neue Saison {season} gestartet.")
    else:
        print(f"\n🔄 Saison {state['season']} wird fortgesetzt (Spieltag {state['spieltag']}).")

    print("\nBedienung:")
    print("  [Enter]  → nächsten Spieltag simulieren")
    print("  p       → EINE Playoff-Runde simulieren")
    print("  f       → komplette Playoffs simulieren und neue Saison starten")
    print("  q       → beenden")

    while True:
        cmd = input("\nEingabe ([Enter]/p/f/q): ").strip().lower()

        if cmd == "q":
            print("👋 Ende.")
            break

        elif cmd == "p":
            res = step_playoffs_round_once()
            print(f"▶️  Playoff-Runde: {res}")
            if res.get("status") == "champion":
                print(f"🏆 Champion: {res.get('champion')}")
                print(f"➡️ Neue Saison {res.get('next_season')} wurde initialisiert.")

        elif cmd == "f":
            res = simulate_full_playoffs_and_advance()
            print(f"⚙️  Playoffs-Run (vollständig): {res}")
            state = load_state()
            print(f"🔁 Neue Saison {state['season']} gestartet (Spieltag {state['spieltag']}).")

        else:
            res = step_regular_season_once()
            print(f"▶️  Spieltag-Result: {res}")
            if res.get("status") == "season_over":
                print("🏁 Hauptrunde beendet. Mit 'p' kannst du die Playoffs rundenweise simulieren oder mit 'f' komplett durchlaufen lassen.")
