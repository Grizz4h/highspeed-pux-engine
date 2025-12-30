from __future__ import annotations

import json
import random
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional

import pandas as pd
import math
import os
import re


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


def _clean_for_json(obj: Any) -> Any:
    """
    Läuft rekursiv durch Dicts/Listen und ersetzt alle NaN durch None,
    damit json.dump gültiges JSON schreibt.
    """
    if isinstance(obj, float) and math.isnan(obj):
        return None

    if isinstance(obj, dict):
        return {k: _clean_for_json(v) for k, v in obj.items()}

    if isinstance(obj, list):
        return [_clean_for_json(v) for v in obj]

    # JSON kann keine tuples -> Listen
    if isinstance(obj, tuple):
        return [_clean_for_json(v) for v in obj]

    return obj
import re

# Logging setup
logging.basicConfig(
    filename='liga_simulation.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def to_index(value: str) -> int:
    """
    Macht aus '12', 'Spieltag_12', 'Playoff_Runde_3' -> 12 bzw. 3
    Knallt bewusst, wenn keine Zahl drin ist.
    """
    s = str(value)
    m = re.search(r"(\d+)", s)
    if not m:
        raise ValueError(f"Keine Zahl gefunden in: {s!r}")
    return int(m.group(1))


# ----------------------------
# Data Root (Single Source of Truth) - HARD FAIL wenn nicht gesetzt
# ----------------------------
env_root = os.environ.get("HIGHSPEED_DATA_ROOT")
if not env_root:
    raise RuntimeError(
        "HIGHSPEED_DATA_ROOT ist nicht gesetzt – sonst wird ins Engine-Repo geschrieben."
    )
DATA_ROOT = Path(env_root).resolve()

SAVEFILE     = DATA_ROOT / "saves" / "savegame.json"
SPIELTAG_DIR = DATA_ROOT / "spieltage"
PLAYOFF_DIR  = DATA_ROOT / "playoffs"
REPLAY_DIR   = DATA_ROOT / "replays"
SCHEDULE_DIR = DATA_ROOT / "schedules"
LINEUP_DIR   = DATA_ROOT / "lineups"
STATS_DIR    = DATA_ROOT / "stats"

print("✅ HIGHSPEED_DATA_ROOT =", DATA_ROOT)
print("✅ SAVEFILE =", SAVEFILE)

def season_folder(season: int) -> str:
    return f"saison_{int(season):02d}"

# ------------------------------------------------
# 2  TEAMS LADEN
# ------------------------------------------------
from realeTeams_live import nord_teams, sued_teams  # deine Datei mit Teams/Spielern


# ------------------------------------------------
# 3  SAVE/LOAD & INIT
# ------------------------------------------------
def _ensure_dirs() -> None:
    for p in (SAVEFILE.parent, SPIELTAG_DIR, PLAYOFF_DIR, REPLAY_DIR, SCHEDULE_DIR, LINEUP_DIR, STATS_DIR):
        p.mkdir(parents=True, exist_ok=True)


_ensure_dirs()


def load_state() -> Optional[Dict[str, Any]]:
    """
    Lädt den aktuellen State aus SAVEFILE.
    Gibt None zurück, wenn kein Save existiert.
    """
    if not SAVEFILE.exists():
        return None
    try:
        with SAVEFILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] load_state failed: {e}")
        return None


def save_state(state: Dict[str, Any]) -> None:
    """
    Speichert den aktuellen State nach SAVEFILE.
    """
    _ensure_dirs()
    cleaned = _clean_for_json(state)
    with SAVEFILE.open("w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2, ensure_ascii=False)
    # bewusst kein print-spam hier, dein Script printet eh genug


def get_next_season_number() -> int:
    if not SPIELTAG_DIR.exists():
        return 1
    nums = [
        int(p.name.split("_")[1])
        for p in SPIELTAG_DIR.iterdir()
        if p.is_dir() and p.name.startswith("saison_") and p.name.split("_")[1].isdigit()
    ]
    return max(nums, default=0) + 1


def _init_frames() -> Tuple[pd.DataFrame, pd.DataFrame]:
    n = pd.DataFrame(nord_teams)
    s = pd.DataFrame(sued_teams)
    for d in (n, s):
        # robust: falls Spalten fehlen, anlegen
        for col in ("Points", "Goals For", "Goals Against"):
            if col not in d.columns:
                d[col] = 0
        d[["Points", "Goals For", "Goals Against"]] = 0
    return n, s


def savefile_for_season(season: int) -> Path:
    """
    Saison-spezifischer Savefile-Pfad (optional/nützlich).
    Aktuell nutzt der Engine-State SAVEFILE als "latest", aber das hier bleibt drin.
    """
    return DATA_ROOT / "saves" / season_folder(season) / "savegame.json"



# ------------------------------------------------
# 3a SPIELPLAN-GENERATOR (REINES ROUND-ROBIN)
# ------------------------------------------------
def create_schedule(teams: List[Dict[str, Any]]) -> List[Tuple[str, str]]:
    """
    Standard Round-Robin mit Hin- und Rückrunde.
    KEINE Story-Constraints, KEINE Swaps.
    Ergebnis: Liste von (home, away)-Tuples der Länge N*(N-1).
    """
    teams = teams.copy()
    if len(teams) % 2:
        teams.append({"Team": "BYE"})

    days = len(teams) - 1
    half = len(teams) // 2

    sched: List[Tuple[str, str]] = []
    for d in range(days * 2):
        day_matches: List[Tuple[str, str]] = []
        for i in range(half):
            a, b = teams[i]["Team"], teams[-i - 1]["Team"]
            if d % 2 == 0:
                day_matches.append((a, b))
            else:
                day_matches.append((b, a))
        sched.extend(day_matches)
        teams.insert(1, teams.pop())

    sched = [(h, a) for (h, a) in sched if "BYE" not in (h, a)]
    return sched


def _find_team_name_by_keywords(teams: List[Dict[str, Any]], keywords: List[str]) -> Optional[str]:
    kws = [k.lower() for k in keywords]
    for t in teams:
        name = str(t.get("Team", ""))
        low = name.lower()
        if all(k in low for k in kws):
            return name
    return None


def _enforce_novadelta_augsburg_third_match(
    sched: List[Tuple[str, str]],
    teams: List[Dict[str, Any]],
) -> List[Tuple[str, str]]:
    """
    Story-Logik:
    - Nova: H/A/H/A/... (1. Spiel Heim)
    - 3. Nova-Spiel: Heim vs Augsburg, durch Swap ganzer Spieltage
    """
    nova = _find_team_name_by_keywords(teams, ["nova", "panther"])
    if not nova:
        return sched

    team_count = len(teams)
    if team_count % 2 != 0:
        print("[INFO] Story-Constraint deaktiviert (ungerade Teamanzahl in Conference).")
        return sched

    half = team_count // 2
    if len(sched) % half != 0:
        print("[WARN] _enforce_novadelta_augsburg_third_match: sched-Länge passt nicht zu 'half'")
        return sched

    # Schritt A: H/A-Muster für Nova
    nd_indices: List[Tuple[int, int]] = []
    for idx, (h, a) in enumerate(sched):
        if h == nova or a == nova:
            day = idx // half
            nd_indices.append((day, idx))

    if not nd_indices:
        return sched

    nd_indices.sort(key=lambda x: x[0])

    for k, (day, idx) in enumerate(nd_indices):
        desired_home = (k % 2 == 0)
        h, a = sched[idx]
        is_home_now = (h == nova)
        if is_home_now != desired_home:
            sched[idx] = (a, h)

    # Schritt B: 3. Nova-Spiel Heim vs Augsburg
    augs = _find_team_name_by_keywords(teams, ["augs", "ferox"])
    if not augs:
        return sched

    nd_games: List[Dict[str, Any]] = []
    for idx, (h, a) in enumerate(sched):
        if h == nova or a == nova:
            day = idx // half
            home = (h == nova)
            opp = a if home else h
            nd_games.append({"day": day, "idx": idx, "home": home, "opp": opp})

    nd_games.sort(key=lambda g: g["day"])
    if len(nd_games) < 3:
        return sched

    third_game = nd_games[2]
    third_day = third_game["day"]

    if not third_game["home"]:
        print("[WARN] 3. Nova-Spiel ist nach H/A-Logik doch nicht Heim – Story-Constraint wird nicht erzwungen.")
        return sched

    target_game: Optional[Dict[str, Any]] = None
    for g in nd_games:
        if g["home"] and g["opp"] == augs:
            target_game = g
            break

    if not target_game:
        return sched

    target_day = target_game["day"]
    if target_day == third_day:
        return sched

    d1, d2 = third_day, target_day
    for k in range(half):
        i1 = d1 * half + k
        i2 = d2 * half + k
        sched[i1], sched[i2] = sched[i2], sched[i1]

    return sched


# ------------------------------------------------
# 3b SAISON-INITIALISIERUNG + SPIELPLAN-PREVIEW
# ------------------------------------------------
def _build_schedule_matchdays(
    sched: List[Tuple[str, str]],
    team_count: int,
) -> List[Dict[str, Any]]:
    if team_count % 2 == 0:
        half = team_count // 2
    else:
        half = (team_count + 1) // 2

    days = (team_count - 1) * 2

    matchdays: List[Dict[str, Any]] = []
    for day in range(days):
        start = day * half
        end = start + half
        day_matches = sched[start:end]
        matchdays.append({
            "matchday": day + 1,
            "matches": [{"home": h, "away": a} for (h, a) in day_matches],
        })
    return matchdays


def _save_json(folder: Path, name: str, payload: Dict[str, Any]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    cleaned = _clean_for_json(payload)
    with (folder / name).open("w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2, ensure_ascii=False)
    print("📦 JSON gespeichert →", folder / name)


def _save_full_schedule_preview(
    season: int,
    nsched: List[Tuple[str, str]],
    ssched: List[Tuple[str, str]],
) -> None:
    north_team_names = [t["Team"] for t in nord_teams]
    south_team_names = [t["Team"] for t in sued_teams]

    nord_matchdays = _build_schedule_matchdays(nsched, len(north_team_names))
    sued_matchdays = _build_schedule_matchdays(ssched, len(south_team_names))

    payload: Dict[str, Any] = {
        "season": season,
        "created_at": datetime.now().isoformat(),
        "nord": {"teams": north_team_names, "matchdays": nord_matchdays},
        "sued": {"teams": south_team_names, "matchdays": sued_matchdays},
    }

    target_folder = SCHEDULE_DIR / season_folder(season)
    _save_json(target_folder, "spielplan.json", payload)

    print("📃 Saison-Spielplan gespeichert →", target_folder / "spielplan.json")



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


def _init_new_season_state(season: int) -> Dict[str, Any]:
    nord, sued = _init_frames()

    nsched = create_schedule(nord_teams)
    ssched = create_schedule(sued_teams)

    nsched = _enforce_novadelta_augsburg_third_match(nsched, nord_teams)
    ssched = _enforce_novadelta_augsburg_third_match(ssched, sued_teams)

    _save_full_schedule_preview(season, nsched, ssched)

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

    if "Number" not in stats.columns:
        stats["Number"] = None
    if "PositionGroup" not in stats.columns:
        stats["PositionGroup"] = None

    def _prep(df: pd.DataFrame) -> List[Dict[str, Any]]:
        d = df.copy()
        d.rename(columns={"Goals For": "GF", "Goals Against": "GA"}, inplace=True)
        d["GD"] = d["GF"] - d["GA"]
        if "last5" not in d.columns:
            d["last5"] = [[] for _ in range(len(d))]
        result = d.sort_values(["Points", "GF"], ascending=False)[
            ["Team", "Points", "GF", "GA", "GD"]
        ].to_dict("records")
        logging.info(f"Exported table with last5: {result[0] if result else 'No data'}")
        return result

    top = stats.sort_values("Points", ascending=False).head(20)[
        ["Player", "Team", "Number", "PositionGroup", "Goals", "Assists", "Points"]
    ]

    return {
        "tabelle_nord": _prep(nord_df),
        "tabelle_sued": _prep(sued_df),
        "top_scorer": _df_to_records_clean(top),
    }


def save_spieltag_json(
    season: int,
    gameday: int,
    results: List[Dict[str, Any]],
    nord: pd.DataFrame,
    sued: pd.DataFrame,
    stats: pd.DataFrame,
    *,
    debug: Optional[Dict[str, Any]] = None,
    lineups: Optional[Dict[str, Any]] = None,  # <<< NEU: Lines/Lineups pro Team
) -> None:
    payload: Dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "saison": season,
        "spieltag": gameday,
        "results": results,
        **_export_tables(nord, sued, stats),
    }
    if debug is not None:
        payload["debug"] = debug
    if lineups is not None:
        payload["lineups"] = lineups  # <<< NEU
    _save_json(SPIELTAG_DIR / season_folder(season), f"spieltag_{gameday:02}.json", payload)

    # Auch in stats/ speichern, falls die App das lädt
    teams = []
    for team in payload["tabelle_nord"] + payload["tabelle_sued"]:
        team_dict = dict(team)
        team_name = team["Team"]
        # last5 aus df holen
        nord_row = nord[nord["Team"] == team_name]
        if not nord_row.empty:
            last5_val = nord_row["last5"].iloc[0]
            team_dict["last5"] = last5_val
            logging.info(f"Team {team_name} last5 from nord: {last5_val}")
        else:
            sued_row = sued[sued["Team"] == team_name]
            if not sued_row.empty:
                last5_val = sued_row["last5"].iloc[0]
                team_dict["last5"] = last5_val
                logging.info(f"Team {team_name} last5 from sued: {last5_val}")
            else:
                team_dict["last5"] = []
                logging.info(f"Team {team_name} last5 not found, set to []")
        teams.append(team_dict)
    logging.info(f"Saving to stats: {teams[0]['last5'] if teams else 'No teams'}")
    _save_json(STATS_DIR / season_folder(season) / "league", f"after_spieltag_{gameday:02}.json", {
        "season": season,
        "upto_matchday": gameday,
        "generated_at": datetime.now().isoformat(),
        "teams": teams,
    })



def save_lineup_overview(
    season: int,
    gameday: int,
    lineups: Dict[str, Any],
) -> None:
    """
    Speichert eine kompakte, menschlich lesbare Lineup-Übersicht
    für schnellen Überblick / Story-Planung.
    """
    payload = {
        "season": season,
        "spieltag": gameday,
        "generated_at": datetime.now().isoformat(),
        "teams": lineups,
    }

    target = LINEUP_DIR / season_folder(season)

    _save_json(target, f"spieltag_{gameday:02}_lineups.json", payload)


# ------------------------------------------------
# 4b REPLAY-EXPORT
# ------------------------------------------------
def save_replay_json(
    season: int,
    gameday: int,
    replay_matches: List[Dict[str, Any]],
) -> None:
    base_folder = REPLAY_DIR / season_folder(season) / f"spieltag_{gameday:02}"

    base_folder.mkdir(parents=True, exist_ok=True)

    matchday_payload: Dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "season": season,
        "matchday": gameday,
        "games": [],
    }

    for m in replay_matches:
        home = m["home"]
        away = m["away"]
        g_home = m["g_home"]
        g_away = m["g_away"]
        conference = m.get("conference")

        game_id = m.get("game_id") or f"{home}-{away}"

        game_payload = {
            "season": season,
            "matchday": gameday,
            "game_id": game_id,
            "conference": conference,
            "home": {"id": home, "name": home, "score": g_home},
            "away": {"id": away, "name": away, "score": g_away},
            "overtime": m.get("overtime", False),
            "shootout": m.get("shootout", False),
            "events": m.get("events", []),
        }

        _save_json(base_folder, f"{game_id}.json", game_payload)

        matchday_payload["games"].append({
            "game_id": game_id,
            "featured": False,
            "conference": conference,
            "home": home,
            "away": away,
            "g_home": g_home,
            "g_away": g_away,
        })

    _save_json(base_folder, "replay_matchday.json", matchday_payload)


# ------------------------------------------------
# 4c STATS-SAMMLER (NEU) – ligaweit aus gespeicherten Spieltag-JSONs
# ------------------------------------------------
def _list_spieltag_files(season: int) -> List[Path]:
    folder = SPIELTAG_DIR / season_folder(season)

    if not folder.exists():
        return []
    return sorted(folder.glob("spieltag_*.json"))


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _calc_streak(results: List[str]) -> str:
    if not results:
        return ""
    last = results[-1]
    if last not in ("W", "L", "T"):
        return ""
    n = 0
    for r in reversed(results):
        if r == last:
            n += 1
        else:
            break
    return f"{last}{n}"


def _team_points_from_results(results: List[str]) -> int:
    pts = 0
    for r in results:
        if r == "W":
            pts += 3
        elif r == "T":
            pts += 1
    return pts


def _safe_mean(vals: List[Any]) -> Optional[float]:
    xs = [v for v in vals if isinstance(v, (int, float))]
    if not xs:
        return None
    return round(sum(xs) / len(xs), 2)


def _build_game_logs_from_spieltage(season: int) -> Dict[str, List[Dict[str, Any]]]:
    """
    Baut pro Team ein Game-Log aus den gespeicherten spieltag_XX.json.
    Nutzt optional debug.*.avg_overall falls vorhanden.
    """
    logs: Dict[str, List[Dict[str, Any]]] = {}

    for fp in _list_spieltag_files(season):
        payload = _load_json(fp)
        md = int(payload.get("spieltag", 0))
        results = payload.get("results", [])

        # debug-map: (matchday, team) -> avg_overall
        debug = payload.get("debug") or {}
        debug_map: Dict[Tuple[int, str], float] = {}

        def _ingest_side(side: str, m: Dict[str, Any]) -> None:
            block = m.get(side) or {}
            t = block.get("team")
            a = block.get("avg_overall")
            if isinstance(t, str) and isinstance(a, (int, float)):
                debug_map[(md, t)] = float(a)

        for key in ("nord_matches", "sued_matches"):
            for m in (debug.get(key) or []):
                if isinstance(m, dict):
                    _ingest_side("home", m)
                    _ingest_side("away", m)

        for r in results:
            home = r["home"]
            away = r["away"]
            gh = int(r["g_home"])
            ga = int(r["g_away"])
            conf = r.get("conference")
            is_ot_so = r.get("overtime", False) or r.get("shootout", False)

            if gh > ga:
                home_res = "W2" if is_ot_so else "W"
                away_res = "L1" if is_ot_so else "L"
            elif gh < ga:
                home_res = "L1" if is_ot_so else "L"
                away_res = "W2" if is_ot_so else "W"
            else:
                home_res, away_res = "T", "T"

            for team, opp, gf, gax, is_home, res in [
                (home, away, gh, ga, True, home_res),
                (away, home, ga, gh, False, away_res),
            ]:
                logs.setdefault(team, []).append({
                    "matchday": md,
                    "conference": conf,
                    "home": bool(is_home),
                    "opponent": opp,
                    "gf": int(gf),
                    "ga": int(gax),
                    "result": res,
                    "avg_overall": debug_map.get((md, team)),
                })

    for team in logs:
        logs[team] = sorted(logs[team], key=lambda x: x["matchday"])
    return logs


def save_league_stats_snapshot(
    season: int,
    upto_matchday: int,
    nord_df: pd.DataFrame,
    sued_df: pd.DataFrame,
    player_stats: pd.DataFrame,
) -> None:
    """
    Schreibt:
      stats/saison_<season>/league/latest.json
      stats/saison_<season>/league/after_spieltag_XX.json
    """
    logs = _build_game_logs_from_spieltage(season)

    teams_all: List[Dict[str, Any]] = []
    for conf_name, df in [("Nord", nord_df), ("Sued", sued_df)]:
        for _, row in df.iterrows():
            team = str(row["Team"])
            gl = logs.get(team, [])
            results = [g["result"] for g in gl]
            last5 = results[-5:]
            streak = _calc_streak(results)

            aovr_season = _safe_mean([g.get("avg_overall") for g in gl])
            aovr_last5 = _safe_mean([g.get("avg_overall") for g in gl[-5:]])

            gp = len(results)

            teams_all.append({
                "team": team,
                "conference": conf_name,
                "gp": gp,
                "w": results.count("W"),
                "l": results.count("L"),
                "t": results.count("T"),
                "points_table": int(row.get("Points", 0)),
                "points_from_logs": _team_points_from_results(results),
                "gf_table": int(row.get("Goals For", 0)),
                "ga_table": int(row.get("Goals Against", 0)),
                "gd_table": int(row.get("Goals For", 0)) - int(row.get("Goals Against", 0)),
                "ppg_table": round(float(row.get("Points", 0)) / max(1, gp), 2),
                "last5": last5,
                "streak": streak,
                "avg_overall_season": aovr_season,
                "avg_overall_last5": aovr_last5,
            })

    ps = player_stats.copy()
    ps["Points"] = ps["Goals"] + ps["Assists"]

    leaders = {
        "points": _df_to_records_clean(ps.sort_values("Points", ascending=False).head(20)[["Player","Team","Number","PositionGroup","Goals","Assists","Points"]]),
        "goals": _df_to_records_clean(ps.sort_values("Goals", ascending=False).head(20)[["Player","Team","Number","PositionGroup","Goals","Assists","Points"]]),
        "assists": _df_to_records_clean(ps.sort_values("Assists", ascending=False).head(20)[["Player","Team","Number","PositionGroup","Goals","Assists","Points"]]),
    }

    # Extremwerte (nur über "home" Einträge zählen, damit jedes Spiel 1x vorkommt)
    all_games: List[Dict[str, Any]] = []
    for team, gl in logs.items():
        for g in gl:
            if g.get("home") is True:
                all_games.append({
                    "matchday": g["matchday"],
                    "home": team,
                    "away": g["opponent"],
                    "g_home": g["gf"],
                    "g_away": g["ga"],
                    "conference": g.get("conference"),
                    "total_goals": g["gf"] + g["ga"],
                    "goal_diff": abs(g["gf"] - g["ga"]),
                })

    highest_scoring = max(all_games, key=lambda x: x["total_goals"], default=None)
    biggest_blowout = max(all_games, key=lambda x: x["goal_diff"], default=None)

    power_teams = [t for t in teams_all if isinstance(t.get("avg_overall_season"), (int, float))]
    power_rank = sorted(power_teams, key=lambda x: x["avg_overall_season"], reverse=True)

    payload = {
        "season": season,
        "upto_matchday": upto_matchday,
        "generated_at": datetime.now().isoformat(),
        "teams": teams_all,
        "leaderboards": leaders,
        "extremes": {
            "highest_scoring_game": highest_scoring,
            "biggest_blowout": biggest_blowout,
        },
        "power_ranking_by_avg_overall": [
            {"rank": i+1, "team": t["team"], "conference": t["conference"], "avg_overall_season": t["avg_overall_season"], "avg_overall_last5": t["avg_overall_last5"]}
            for i, t in enumerate(power_rank)
        ],
    }

    league_folder = STATS_DIR / season_folder(season) / "league"

    league_folder.mkdir(parents=True, exist_ok=True)

    _save_json(league_folder, f"after_spieltag_{upto_matchday:02}.json", payload)
    _save_json(league_folder, "latest.json", payload)


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
# 6  SIMULATIONSGRUNDSÄTZE + LINEUPS + LINES (NEU)
# ------------------------------------------------
def _weighted_pick_by_gp(players: List[Dict[str, Any]], count: int, jitter_factor: float = 0.3) -> List[Dict[str, Any]]:
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


def _score_fwd_scoring(p: Dict[str, Any]) -> float:
    return (
        float(p.get("Offense", 50))   * 0.50 +
        float(p.get("Speed", 50))     * 0.20 +
        float(p.get("Chemistry", 50)) * 0.20 +
        float(p.get("Defense", 50))   * 0.10
    )


def _score_fwd_checking(p: Dict[str, Any]) -> float:
    return (
        float(p.get("Defense", 50))   * 0.60 +
        float(p.get("Chemistry", 50)) * 0.20 +
        float(p.get("Speed", 50))     * 0.10 +
        float(p.get("Offense", 50))   * 0.10
    )


def _score_def_pair(p: Dict[str, Any]) -> float:
    return (
        float(p.get("Defense", 50))   * 0.60 +
        float(p.get("Speed", 50))     * 0.20 +
        float(p.get("Chemistry", 50)) * 0.20
    )


def _brief_player(p: Dict[str, Any]) -> Dict[str, Any]:
    # fürs JSON: klein + stabil
    return {
        "name": p.get("NameReal") or p.get("Name"),
        "id": p.get("Name"),
        "number": p.get("Number"),
        "pos": p.get("PositionGroup") or p.get("PositionRaw"),
        "overall": p.get("Overall"),
        "line": p.get("Line"),
        "pair": p.get("Pair"),
        "rotation": p.get("Rotation", False),
    }


def build_line_snapshot(lineup: List[Dict[str, Any]]) -> Dict[str, Any]:
    fwds = [p for p in lineup if str(p.get("PositionGroup", "")).upper() == "F"]
    defs = [p for p in lineup if str(p.get("PositionGroup", "")).upper() == "D"]
    gols = [p for p in lineup if str(p.get("PositionGroup", "")).upper() == "G"]

    def _by_line(n: int) -> List[Dict[str, Any]]:
        return [_brief_player(p) for p in fwds if p.get("Line") == n]

    def _by_pair(n: int) -> List[Dict[str, Any]]:
        return [_brief_player(p) for p in defs if p.get("Pair") == n]

    rotation = [_brief_player(p) for p in defs if p.get("Rotation")]

    goalie = _brief_player(gols[0]) if gols else None

    return {
        "forwards": {
            "line1": _by_line(1),
            "line2": _by_line(2),
            "line3": _by_line(3),
            "line4": _by_line(4),
        },
        "defense": {
            "pair1": _by_pair(1),
            "pair2": _by_pair(2),
            "pair3": _by_pair(3),
            "rotation": rotation,
        },
        "goalie": goalie,
    }


def _assign_lines_and_pairs(unique_lineup: List[Dict[str, Any]]) -> None:
    """
    Mutiert NUR das unique_lineup (Kopien), nicht das Roster im Save.
    - Forwards: Line 1-4
    - Defense: Pair 1-3 + Rotation
    """
    fwds = [p for p in unique_lineup if str(p.get("PositionGroup", "")).upper() == "F"]
    defs = [p for p in unique_lineup if str(p.get("PositionGroup", "")).upper() == "D"]

    # --- Forwards -> Lines
    fwds_sorted_scoring = sorted(fwds, key=_score_fwd_scoring, reverse=True)

    line1 = fwds_sorted_scoring[:3]
    line2 = fwds_sorted_scoring[3:6]
    remaining = fwds_sorted_scoring[6:]

    remaining_sorted_checking = sorted(remaining, key=_score_fwd_checking, reverse=True)
    line3 = remaining_sorted_checking[:3]
    line4 = remaining_sorted_checking[3:]  # Rest

    for p in line1:
        p["Line"] = 1
    for p in line2:
        p["Line"] = 2
    for p in line3:
        p["Line"] = 3
    for p in line4:
        p["Line"] = 4

    # Falls weniger Forwards als erwartet (Roster komisch): alles was noch ohne Line ist -> 4
    for p in fwds:
        if "Line" not in p:
            p["Line"] = 4

    # --- Defense -> Pairs
    defs_sorted = sorted(defs, key=_score_def_pair, reverse=True)
    pairs = [defs_sorted[0:2], defs_sorted[2:4], defs_sorted[4:6]]
    rotation = defs_sorted[6:]

    for i, pair in enumerate(pairs, start=1):
        for p in pair:
            p["Pair"] = i
            p["Rotation"] = False

    for p in rotation:
        p["Pair"] = None
        p["Rotation"] = True


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
    NEU:
      - Forwards bekommen Line 1-4
      - Defender bekommen Pair 1-3 + Rotation
    """
    if not players:
        return []

    ds = [p for p in players if str(p.get("PositionGroup", "")).upper() == "D"]
    fs = [p for p in players if str(p.get("PositionGroup", "")).upper() == "F"]
    gs = [p for p in players if str(p.get("PositionGroup", "")).upper() == "G"]

    # WICHTIG: Kopien erzeugen, damit wir das Save-Roster nicht mutieren
    picked: List[Dict[str, Any]] = []
    picked.extend([dict(p) for p in _weighted_pick_by_gp(ds, min(n_def, len(ds)))])
    picked.extend([dict(p) for p in _weighted_pick_by_gp(fs, min(n_fwd, len(fs)))])

    if gs:
        picked.extend([dict(p) for p in _weighted_pick_by_gp(gs, min(n_goalies, len(gs)))])
    else:
        print("[WARN] Team ohne Goalies im Roster – kein G im Lineup.")

    # Sicherheitsnetz: Keine Duplikate
    seen_ids = set()
    unique_lineup: List[Dict[str, Any]] = []
    for p in picked:
        key = (p.get("NameReal"), p.get("Number"))
        if key not in seen_ids:
            seen_ids.add(key)
            unique_lineup.append(p)

    # Lines/Pairs zuweisen (nur auf den Kopien)
    _assign_lines_and_pairs(unique_lineup)

    d_count = sum(1 for p in unique_lineup if str(p.get("PositionGroup", "")).upper() == "D")
    f_count = sum(1 for p in unique_lineup if str(p.get("PositionGroup", "")).upper() == "F")
    g_count = sum(1 for p in unique_lineup if str(p.get("PositionGroup", "")).upper() == "G")

    if (d_count != n_def) or (f_count != n_fwd) or (g_count != n_goalies):
        print(f"\n[DEBUG][Lineup Warnung] Team: {team_name}")
        print(f"   → {d_count}D / {f_count}F / {g_count}G  (Soll: {n_def}D / {n_fwd}F / {n_goalies}G)")
        if d_count < n_def:
            print("   -> FEHLENDE Verteidiger:", n_def - d_count)
        if f_count < n_fwd:
            print("   -> FEHLENDE Stürmer:", n_def - d_count)
        if g_count < n_goalies:
            print("   -> KEIN GOALIE verfügbar!")

    return unique_lineup


def _get_lineup_for_team(df: pd.DataFrame, team_name: str) -> List[Dict[str, Any]]:
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
    Baut pro Team heute:
      - df["Lineup"] (Liste Spieler)
      - df["LineSnapshot"] (Chasen-Struktur)
    Backwards compatible: Spalten werden bei Bedarf erstellt.
    """
    teams_today = set()
    for home, away in matches:
        teams_today.add(home)
        teams_today.add(away)

    if "Lineup" not in df.columns:
        df["Lineup"] = None
    if "LineSnapshot" not in df.columns:
        df["LineSnapshot"] = None

    for team_name in teams_today:
        mask = df["Team"] == team_name
        if not mask.any():
            print(f"[WARN] prepare_lineups_for_matches: Team '{team_name}' nicht in df gefunden")
            continue

        idx = df.index[mask].tolist()[0]
        players = df.at[idx, "Players"]

        lineup = build_lineup(players, team_name=team_name)
        df.at[idx, "Lineup"] = lineup
        df.at[idx, "LineSnapshot"] = build_line_snapshot(lineup)


def _collect_lineups_payload(df: pd.DataFrame, matches: List[Tuple[str, str]]) -> Dict[str, Any]:
    """
    Baut pro Team ein Snapshot-Payload fürs Spieltag-JSON.
    Wenn LineSnapshot fehlt, wird aus Lineup best-effort gebaut.
    """
    teams_today = set()
    for h, a in matches:
        teams_today.add(h)
        teams_today.add(a)

    out: Dict[str, Any] = {}
    for team in teams_today:
        mask = df["Team"] == team
        if not mask.any():
            continue
        row = df.loc[mask].iloc[0]

        snap = None
        if "LineSnapshot" in df.columns:
            candidate = row.get("LineSnapshot")
            if isinstance(candidate, dict) and candidate:
                snap = candidate

        if snap is None:
            lineup = row.get("Lineup")
            if isinstance(lineup, list) and lineup:
                snap = build_line_snapshot(lineup)

        if snap is not None:
            out[team] = snap

    return out


# -----------------------------------------------------
# DEBUG-Helfer: Tabellenansicht & Stärkevergleich & JSON-Payload
# -----------------------------------------------------
def _build_lineup_table(df: pd.DataFrame, matches: List[Tuple[str, str]]) -> pd.DataFrame:
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
                    "Line": p.get("Line"),
                    "Pair": p.get("Pair"),
                    "Rot": p.get("Rotation", False),
                    "GP": p.get("GamesPlayed"),
                    "OVR": p.get("Overall"),
                })
    if not rows:
        return pd.DataFrame(columns=["Team", "Rolle", "Gegner", "Name", "Pos", "Line", "Pair", "Rot", "GP", "OVR"])
    df_out = pd.DataFrame(rows)
    df_out = df_out.sort_values(["Team", "Rolle", "OVR"], ascending=[True, True, False])
    return df_out


def _build_strength_panel(df: pd.DataFrame, matches: List[Tuple[str, str]]) -> pd.DataFrame:
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
    total *= 1 + random.uniform(-5, 5) / 100
    total *= 1 + row.get("Momentum", 0) / 100
    total *= 1 + (3 if home else 0) / 100
    total *= 1 + random.uniform(-1, 2) / 100
    return round(total, 2)


# ------------------------------------------------
# 6c  STATS-UPDATES
# ------------------------------------------------
def update_player_stats(team: str, goals: int, df: pd.DataFrame, stats: pd.DataFrame) -> List[Dict[str, Any]]:
    mask = df["Team"] == team
    if not mask.any() or goals <= 0:
        return []

    use_column = "Players"
    if "Lineup" in df.columns:
        candidate = df.loc[mask, "Lineup"].iloc[0]
        if isinstance(candidate, list) and candidate:
            use_column = "Lineup"

    roster = df.loc[mask, use_column].iloc[0]
    roster = random.sample(roster, 18) if len(roster) > 18 else roster

    skaters = [p for p in roster if str(p.get("PositionGroup", "")).upper() != "G"]
    if not skaters:
        skaters = roster

    scorer_pool = skaters
    scorer_weights = [max(1, int(p.get("Offense", 50)) // 5) for p in scorer_pool]

    goal_events: List[Dict[str, Any]] = []

    for _ in range(goals):
        scorer_player = random.choices(scorer_pool, weights=scorer_weights)[0]
        scorer_name = scorer_player["Name"]
        scorer_number = scorer_player.get("Number")
        stats.loc[stats["Player"] == scorer_name, "Goals"] += 1

        assist_name = None
        assist_number = None

        assist_candidates = [p for p in skaters if p.get("Name") != scorer_name]
        if assist_candidates:
            assist_player = random.choice(assist_candidates)
            assist_name = assist_player["Name"]
            assist_number = assist_player.get("Number")
            stats.loc[stats["Player"] == assist_name, "Assists"] += 1

        goal_events.append({
            "scorer": scorer_name,
            "scorer_number": scorer_number,
            "assist": assist_name,
            "assist_number": assist_number,
        })

    return goal_events


def simulate_match(
    df: pd.DataFrame,
    home: str,
    away: str,
    stats: pd.DataFrame,
    conf: str
) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
    logging.info(f"Simuliere Liga-Spiel: {home} vs {away} in {conf}")
    r_h = df[df["Team"] == home].iloc[0]
    r_a = df[df["Team"] == away].iloc[0]

    strength_home = calc_strength(r_h, True)
    strength_away = calc_strength(r_a, False)
    p_home = strength_home / (strength_home + strength_away)

    g_home = max(0, int(random.gauss(p_home * 5, 1)))
    g_away = max(0, int(random.gauss((1 - p_home) * 5, 1)))
    logging.info(f"Reguläre Tore: {home} {g_home}:{g_away} {away}")

    is_overtime = False
    is_shootout = False
    ot_home = 0
    ot_away = 0
    so_home = 0
    so_away = 0
    if g_home == g_away:
        df.loc[df["Team"].isin([home, away]), "Points"] += 1
        is_overtime = True
        if random.random() < p_home:
            ot_home = 1
        else:
            ot_away = 1
        g_home += ot_home
        g_away += ot_away
        if g_home == g_away:
            is_shootout = True
            if random.random() < p_home * 0.7:
                so_home = 1
            else:
                so_away = 1
            g_home += so_home
            g_away += so_away

    logging.info(f"Endergebnis: {home} {g_home}:{g_away} {away} - Overtime: {is_overtime}, Shootout: {is_shootout}")
    if g_home > g_away:
        if is_overtime or is_shootout:
            df.loc[df["Team"] == home, "Points"] += 1
        else:
            df.loc[df["Team"] == home, "Points"] += 3
    elif g_away > g_home:
        if is_overtime or is_shootout:
            df.loc[df["Team"] == away, "Points"] += 1
        else:
            df.loc[df["Team"] == away, "Points"] += 3
    else:
        # Unentschieden nach allem, aber sollte nicht
        pass

    # Update last5 für Teams
    if g_home > g_away:
        home_result = "W2" if is_overtime or is_shootout else "W"
        away_result = "L1" if is_overtime or is_shootout else "L"
    else:
        home_result = "L1" if is_overtime or is_shootout else "L"
        away_result = "W2" if is_overtime or is_shootout else "W"

    # Home Team last5
    if "last5" not in df.columns:
        df["last5"] = [[] for _ in range(len(df))]
    current_last5_home = df.loc[df["Team"] == home, "last5"].iloc[0]
    if not isinstance(current_last5_home, list):
        current_last5_home = []
    current_last5_home.append(home_result)
    df.loc[df["Team"] == home, "last5"] = [current_last5_home[-5:]]

    logging.info(f"Updated last5 for {home}: {df.loc[df['Team'] == home, 'last5'].iloc[0]}")

    # Away Team last5
    current_last5_away = df.loc[df["Team"] == away, "last5"].iloc[0]
    if not isinstance(current_last5_away, list):
        current_last5_away = []
    current_last5_away.append(away_result)
    df.loc[df["Team"] == away, "last5"] = [current_last5_away[-5:]]

    logging.info(f"Updated last5 for {away}: {df.loc[df['Team'] == away, 'last5'].iloc[0]}")

    update_player_stats(home, g_home, df, stats)
    update_player_stats(away, g_away, df, stats)

    res_str = f"{home} {g_home}:{g_away} {away}"
    res_json = {
        "home": home,
        "away": away,
        "g_home": g_home,
        "g_away": g_away,
        "conference": conf,
        "overtime": is_overtime,
        "shootout": is_shootout,
    }

    def _get_skaters(team_name: str) -> List[Dict[str, Any]]:
        mask = df["Team"] == team_name
        if not mask.any():
            return []
        row = df[mask].iloc[0]
        players = row.get("Lineup") or row["Players"]
        skaters = [p for p in players if str(p.get("PositionGroup", "")).upper() != "G"]
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

    events: List[Dict[str, Any]] = []
    current_index = 0
    action_id = 0

    goal_actions: List[Optional[str]] = ["home"] * g_home + ["away"] * g_away
    extra_no_goal = max(2, len(goal_actions))
    goal_actions += [None] * extra_no_goal
    random.shuffle(goal_actions)

    for team_key_raw in goal_actions:
        if team_key_raw is None:
            team_key = "home" if random.random() < 0.5 else "away"
            is_goal = False
        else:
            team_key = team_key_raw
            is_goal = True

        player_main, player_main_number, player_secondary, player_secondary_number = _pick_pair(team_key)

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
                "t": current_index,
                "action_id": action_id,
                "step_in_action": step,
                "team": team_key,
                "zone": zone,
                "type": ev_type,
                "result": result,
                "player_main": player_main,
                "player_main_number": player_main_number,
                "player_secondary": player_secondary,
                "player_secondary_number": player_secondary_number,
                "details": {},
            })
            current_index += 1

        action_id += 1

    if is_overtime:
        events.append({
            "i": current_index,
            "t": current_index,
            "action_id": action_id,
            "step_in_action": 0,
            "team": "none",
            "zone": "none",
            "type": "overtime",
            "result": "start",
            "player_main": None,
            "player_main_number": None,
            "player_secondary": None,
            "player_secondary_number": None,
            "details": {},
        })
        current_index += 1
        action_id += 1
        if ot_home > 0 or ot_away > 0:
            team_key = "home" if ot_home > 0 else "away"
            player_main, player_main_number, player_secondary, player_secondary_number = _pick_pair(team_key)
            events.append({
                "i": current_index,
                "t": current_index,
                "action_id": action_id,
                "step_in_action": 0,
                "team": team_key,
                "zone": "offensive",
                "type": "goal",
                "result": "goal",
                "player_main": player_main,
                "player_main_number": player_main_number,
                "player_secondary": player_secondary,
                "player_secondary_number": player_secondary_number,
                "details": {},
            })
            current_index += 1
            action_id += 1
        if is_shootout:
            events.append({
                "i": current_index,
                "t": current_index,
                "action_id": action_id,
                "step_in_action": 0,
                "team": "none",
                "zone": "none",
                "type": "shootout",
                "result": "start",
                "player_main": None,
                "player_main_number": None,
                "player_secondary": None,
                "player_secondary_number": None,
                "details": {},
            })
            current_index += 1
            action_id += 1
            if so_home > 0 or so_away > 0:
                team_key = "home" if so_home > 0 else "away"
                player_main, player_main_number, player_secondary, player_secondary_number = _pick_pair(team_key)
                events.append({
                    "i": current_index,
                    "t": current_index,
                    "action_id": action_id,
                    "step_in_action": 0,
                    "team": team_key,
                    "zone": "offensive",
                    "type": "shootout_goal",
                    "result": "goal",
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
        "overtime": is_overtime,
        "shootout": is_shootout,
        "events": events,
    }

    return res_str, res_json, replay_struct


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


def simulate_playoff_match(
    a: str,
    b: str,
    nord: pd.DataFrame,
    sued: pd.DataFrame,
    stats: pd.DataFrame
) -> Tuple[str, str, Dict[str, int]]:
    logging.info(f"Simuliere Playoff-Spiel: {a} vs {b}")
    dfA = nord if a in list(nord["Team"]) else sued
    dfB = nord if b in list(nord["Team"]) else sued

    prepare_lineups_for_matches(dfA, [(a, a)])
    prepare_lineups_for_matches(dfB, [(b, b)])

    rA = dfA[dfA["Team"] == a].iloc[0]
    rB = dfB[dfB["Team"] == b].iloc[0]
    pA = calc_strength(rA, True)
    pB = calc_strength(rB, False)
    prob = pA / (pA + pB)
    gA = max(0, int(random.gauss(prob * 5, 1)))
    gB = max(0, int(random.gauss((1 - prob) * 5, 1)))
    logging.info(f"Reguläre Tore: {a} {gA}:{gB} {b}")

    if gA == gB:
        # Overtime
        if random.random() < prob:
            gA += 1
        else:
            gB += 1
        if gA == gB:
            # Shootout
            if random.random() < prob * 0.7:
                gA += 1
            else:
                gB += 1
        logging.info(f"Nach OT/SO: {a} {gA}:{gB} {b}")

    update_player_stats(a, gA, dfA, stats)
    update_player_stats(b, gB, dfB, stats)
    winner = a if gA > gB else b
    logging.info(f"Gewinner: {winner}")
    return f"{a} {gA}:{gB} {b}", winner, {"g_home": gA, "g_away": gB}


def simulate_series_best_of(
    a: str,
    b: str,
    nord: pd.DataFrame,
    sued: pd.DataFrame,
    stats: pd.DataFrame,
    wins_needed: int = 4
) -> Dict[str, Any]:
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


def run_playoffs(
    season: int,
    nord: pd.DataFrame,
    sued: pd.DataFrame,
    stats: pd.DataFrame,
    *,
    interactive: bool = True
) -> str:
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
            PLAYOFF_DIR / season_folder(season),
            f"runde_{rnd:02}.json",
            {
                "timestamp": datetime.now().isoformat(),
                "saison": season,
                "runde": rnd,
                "series": round_series,
                **_export_tables(nord, sued, stats),
            },
        )
        save_state({
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

    max_spieltage = (len(nord_teams) - 1) * 2
    if isinstance(spieltag, int) and spieltag > max_spieltage:
        return {"status": "season_over", "season": season, "spieltag": spieltag}

    results_json: List[Dict[str, Any]] = []
    replay_matches: List[Dict[str, Any]] = []

    # --- NORD ---
    print("\n— Nord —")
    today_nord_matches = nsched[:len(nord) // 2]
    prepare_lineups_for_matches(nord, today_nord_matches)

    lineup_table_nord = _build_lineup_table(nord, today_nord_matches)
    if not lineup_table_nord.empty:
        print("\n📋 Lineups Nord (heute):")
        print(lineup_table_nord.to_string(index=False))
    strength_nord = _build_strength_panel(nord, today_nord_matches)
    if not strength_nord.empty:
        print("\n⚖️ Stärkevergleich Nord:")
        print(strength_nord.to_string(index=False))

    for m in today_nord_matches:
        s, j, replay = simulate_match(nord, *m, stats, "Nord")
        print(s)
        results_json.append(j)
        replay_matches.append(replay)
    nsched = nsched[len(nord) // 2:]

    # --- SÜD ---
    print("\n— Süd —")
    today_sued_matches = ssched[:len(sued) // 2]
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
        s, j, replay = simulate_match(sued, *m, stats, "Süd")
        print(s)
        results_json.append(j)
        replay_matches.append(replay)
    ssched = ssched[len(sued) // 2:]

    _print_tables(nord, sued, stats)

    debug_payload = {
        "nord_matches": _build_debug_matches_payload(nord, today_nord_matches),
        "sued_matches": _build_debug_matches_payload(sued, today_sued_matches),
    }

    # NEU: Lineups payload (Nord+Süd zusammenführen)
    lineups_payload: Dict[str, Any] = {}
    lineups_payload.update(_collect_lineups_payload(nord, today_nord_matches))
    lineups_payload.update(_collect_lineups_payload(sued, today_sued_matches))

    # EXTRA: menschlich lesbare Lineup-Übersicht speichern
    save_lineup_overview(season, spieltag, lineups_payload)

    save_spieltag_json(
        season,
        spieltag,
        results_json,
        nord,
        sued,
        stats,
        debug=debug_payload,
        lineups=lineups_payload,
    )

    save_replay_json(season, spieltag, replay_matches)

    save_league_stats_snapshot(
        season=season,
        upto_matchday=spieltag,
        nord_df=nord,
        sued_df=sued,
        player_stats=stats,
    )

    spieltag += 1
    save_state({
        "season": season,
        "spieltag": spieltag,
        "nord": _df_to_records_clean(nord),
        "sued": _df_to_records_clean(sued),
        "nsched": nsched,
        "ssched": ssched,
        "stats": _df_to_records_clean(stats),
        "history": state.get("history", []),
        "phase": "regular",
    })
    return {"status": "ok", "season": season, "spieltag": spieltag}


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
    state = load_state()
    if not state:
        return {"status": "no_state"}
    nord = pd.DataFrame(state["nord"])
    sued = pd.DataFrame(state["sued"])
    stats = pd.DataFrame(state["stats"])
    history = state.get("history", [])

    max_spieltage = (len(nord_teams) - 1) * 2
    if isinstance(state.get("spieltag"), int) and state["spieltag"] <= max_spieltage:
        return {"status": "regular_not_finished"}

    rnd = int(state.get("playoff_round", 1))
    alive = state.get("playoff_alive", [])
    if rnd == 1 and not alive:
        pairings = _initial_playoff_pairings(nord, sued)
    else:
        if not alive or len(alive) < 2:
            return {"status": "invalid_playoff_state"}
        pairings = [(alive[i], alive[i+1]) for i in range(0, len(alive), 2)]

    round_series = []
    winners = []
    for a, b in pairings:
        series = simulate_series_best_of(a, b, nord, sued, stats)
        round_series.append(series)
        winners.append(series["winner"])
        print(f"• Serie: {a} vs {b} → {series['result']}  Sieger: {series['winner']}")

    _save_json(
        PLAYOFF_DIR / season_folder(state["season"]),
        f"runde_{rnd:02}.json",
        {
            "timestamp": datetime.now().isoformat(),
            "saison": state["season"],
            "runde": rnd,
            "series": round_series,
            **_export_tables(nord, sued, stats),
        },
    )

    if len(winners) == 1:
        champion = winners[0]
        history.append({"season": state["season"], "champion": champion, "finished_at": datetime.now().isoformat()})
        next_season_num = state["season"] + 1
        next_state = _init_new_season_state(next_season_num)
        next_state["history"] = history
        save_state(next_state)
        return {"status": "champion", "round": rnd, "champion": champion, "next_season": next_season_num}

    save_state({
        "season": state["season"],
        "spieltag": f"Playoff_Runde_{rnd}",
        "nord": _df_to_records_clean(nord),
        "sued": _df_to_records_clean(sued),
        "nsched": [], "ssched": [],
        "stats": _df_to_records_clean(stats),
        "history": history,
        "phase": "playoffs",
        "playoff_round": rnd + 1,
        "playoff_alive": winners,
    })
    return {"status": "ok", "round": rnd, "winners": winners}


# ------------------------------------------------
# 9  RUN-SIMULATION (für CLI)
# ------------------------------------------------
def run_simulation(max_seasons: int = 1, interactive: bool = False) -> None:
    for _ in range(max_seasons):
        state = load_state()
        if not state:
            season = get_next_season_number()
            state = _init_new_season_state(season)
            save_state(state)

        while True:
            res = step_regular_season_once()
            if res.get("status") == "season_over":
                break
            if interactive:
                print(f"Spieltag {res.get('spieltag')} simuliert")

        po_res = simulate_full_playoffs_and_advance()
        if interactive:
            print(f"Saison abgeschlossen. Champion: {po_res.get('champion')}.")


# ------------------------------------------------
# 10  SELF-TEST & DEMO (CLI)
# ------------------------------------------------
def _self_tests() -> None:
    dummy = [{"Team": str(i)} for i in range(6)]
    assert len(create_schedule(dummy)) == 6 * 5, "Schedule wrong"
    fake_row = pd.Series({"Players": [{"Offense": 60, "Defense": 60, "Speed": 60, "Chemistry": 60} for _ in range(5)]})
    assert 0 < calc_strength(fake_row) < 100, "Strength out of range"
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
