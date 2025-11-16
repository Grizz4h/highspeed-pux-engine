"""
merge_players_baseline.py

Zieht die bereits gescrapten DEL2- und DEL-Daten zusammen und
bringt sie auf ein gemeinsames Baseline-Schema für deinen Liga-Generator.

Input:
  data/del2_players.json   (aus del2_fetch.py)
  data/del_skaters.json    (aus del_fetch.py)
  data/del_goalies.json    (aus del_fetch.py)

Output:
  data/all_players_baseline.json

Baseline-Schema pro Datensatz:

Skater:
  league: "DEL2" | "DEL"
  type:   "skater"
  team_code:    Optional[str]  (bei DEL2: Club-Kürzel, bei DEL aktuell None/Platzhalter)
  team_name:    Optional[str]  (für DEL: Team-Name aus HTML, für DEL2: vorerst None)
  name_real:    str
  number:       Optional[int]
  nation:       Optional[str]
  position_raw: Optional[str]
  position_group: "F" | "D"

  gp: int
  goals: int
  assists: int
  points: int
  points_per_game: float
  plus_minus: Optional[int]
  pp_goals: int
  sh_goals: int
  pim: int
  fo_won: int
  fo_lost: int
  fo_pct: float

Goalies:
  league: "DEL2" | "DEL"
  type:   "goalie"
  team_code, team_name, name_real, number, nation, position_raw, position_group = "G"

  gp: int
  minutes: float
  wins: int
  losses: int
  shutouts: int
  goals_against: int
  gaa: Optional[float]
  shots_against: int
  saves: int
  sv_pct: Optional[float]
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import math


DATA_DIR = Path("data")
DEL2_FILE = DATA_DIR / "del2_players.json"
DEL_SKATERS_FILE = DATA_DIR / "del_skaters.json"
DEL_GOALIES_FILE = DATA_DIR / "del_goalies.json"
OUT_FILE = DATA_DIR / "all_players_baseline.json"


# ----------------- kleine Helfer -----------------


def _to_int(val: Any) -> int:
    try:
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return 0
        return int(val)
    except (TypeError, ValueError):
        return 0


def _to_float(val: Any) -> float:
    try:
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return 0.0
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _pos_group_from_raw(pos: Optional[str]) -> Optional[str]:
    """
    Mappt Roh-Positionsstrings wie
      - "DE", "DE (U21)", "D"
      - "FO", "FO (U21)", "C", "LW", "RW"
      - "GK", "G"
    sauber auf "D", "F", "G".
    """
    if not pos:
        return None

    p = str(pos).strip().upper()     # z.B. "DE (U21)"
    base = p.split()[0]              # -> "DE"

    # Verteidiger
    if base in ("D", "DE", "V", "DEF", "VERTEIDIGER"):
        return "D"

    # Goalies
    if base in ("G", "GK", "T", "TORHÜTER", "TORWART"):
        return "G"

    # alles andere = Stürmer
    return "F"



# ----------------- DEL2: schon Baseline, nur leicht säubern -----------------


def load_del2_players() -> List[Dict[str, Any]]:
    if not DEL2_FILE.exists():
        print(f"⚠️ DEL2-Datei fehlt: {DEL2_FILE}")
        return []

    data = json.loads(DEL2_FILE.read_text(encoding="utf-8"))
    cleaned: List[Dict[str, Any]] = []

    for rec in data:
        # Erwartet das Schema aus deinem del2_fetch.py (Baseline)
        if rec.get("type") == "skater":
            cleaned.append(
                {
                    "league": "DEL2",
                    "type": "skater",
                    "team_code": rec.get("team_code"),
                    "team_name": None,  # könnten wir später mappen
                    "name_real": rec.get("name_real"),
                    "number": rec.get("number"),
                    "nation": rec.get("nation"),
                    "position_raw": rec.get("position_raw"),
                    "position_group": rec.get("position_group"),

                    "gp": _to_int(rec.get("gp")),
                    "goals": _to_int(rec.get("goals")),
                    "assists": _to_int(rec.get("assists")),
                    "points": _to_int(rec.get("points")),
                    "points_per_game": _to_float(rec.get("points_per_game")),
                    "plus_minus": rec.get("plus_minus"),
                    "pp_goals": _to_int(rec.get("pp_goals")),
                    "sh_goals": _to_int(rec.get("sh_goals")),
                    "pim": _to_int(rec.get("pim")),
                    "fo_won": _to_int(rec.get("fo_won")),
                    "fo_lost": _to_int(rec.get("fo_lost")),
                    "fo_pct": _to_float(rec.get("fo_pct")),
                }
            )
        elif rec.get("type") == "goalie":
            cleaned.append(
                {
                    "league": "DEL2",
                    "type": "goalie",
                    "team_code": rec.get("team_code"),
                    "team_name": None,
                    "name_real": rec.get("name_real"),
                    "number": rec.get("number"),
                    "nation": rec.get("nation"),
                    "position_raw": rec.get("position_raw"),
                    "position_group": "G",

                    "gp": _to_int(rec.get("gp")),
                    "minutes": _to_float(rec.get("minutes")),
                    "wins": _to_int(rec.get("wins")),
                    "losses": _to_int(rec.get("losses")),
                    "shutouts": _to_int(rec.get("shutouts")),
                    "goals_against": _to_int(rec.get("goals_against")),
                    "gaa": _to_float(rec.get("gaa")),
                    "shots_against": _to_int(rec.get("shots_against")),
                    "saves": _to_int(rec.get("saves")),
                    "sv_pct": _to_float(rec.get("sv_pct")),
                }
            )

    print(f"✅ DEL2: {len(cleaned)} Datensätze übernommen")
    return cleaned


# ----------------- DEL: Skater/Goalies -> Baseline -----------------


def load_del_skaters() -> List[Dict[str, Any]]:
    if not DEL_SKATERS_FILE.exists():
        print(f"⚠️ DEL-Skater-Datei fehlt: {DEL_SKATERS_FILE}")
        return []

    raw = json.loads(DEL_SKATERS_FILE.read_text(encoding="utf-8"))
    result: List[Dict[str, Any]] = []

    for rec in raw:
        name = rec.get("name_raw") or rec.get("name") or ""
        if not name:
            continue

        games = _to_int(rec.get("games"))
        goals = _to_int(rec.get("goals"))
        assists = _to_int(rec.get("assists"))
        points = _to_int(rec.get("points"))
        ppg = points / games if games > 0 else 0.0

        fow = rec.get("faceoff_won")
        fow_tot = rec.get("faceoff_total")
        fo_won = _to_int(fow) if fow is not None else 0
        fo_total = _to_int(fow_tot) if fow_tot is not None else 0
        fo_lost = max(0, fo_total - fo_won)
        fo_pct = _to_float(rec.get("faceoff_pct")) if rec.get("faceoff_pct") is not None else (fo_won / fo_total * 100.0 if fo_total > 0 else 0.0)

        pos_raw = rec.get("position")
        pos_group = _pos_group_from_raw(pos_raw)
        if pos_group == "G":
            # ein Goalie, der versehentlich in der Skaterliste wäre -> überspringen
            continue

        result.append(
            {
                "league": "DEL",
                "type": "skater",
                "team_code": None,  # später via Mapping
                "team_name": rec.get("team"),  # aktuell None, aber Feld ist da
                "name_real": name,
                "number": rec.get("number"),
                "nation": rec.get("nation"),
                "position_raw": pos_raw,
                "position_group": pos_group or "F",

                "gp": games,
                "goals": goals,
                "assists": assists,
                "points": points,
                "points_per_game": ppg,
                "plus_minus": rec.get("plus_minus"),
                "pp_goals": 0,   # DEL-HTML liefert keine PP/SH-Zahlen
                "sh_goals": 0,
                "pim": _to_int(rec.get("pim")),
                "fo_won": fo_won,
                "fo_lost": fo_lost,
                "fo_pct": fo_pct,
            }
        )

    print(f"✅ DEL Skater: {len(result)} Datensätze normalisiert")
    return result


def load_del_goalies() -> List[Dict[str, Any]]:
    if not DEL_GOALIES_FILE.exists():
        print(f"⚠️ DEL-Goalie-Datei fehlt: {DEL_GOALIES_FILE}")
        return []

    raw = json.loads(DEL_GOALIES_FILE.read_text(encoding="utf-8"))
    result: List[Dict[str, Any]] = []

    for rec in raw:
        name = rec.get("name_raw") or rec.get("name") or ""
        if not name:
            continue

        pos_raw = rec.get("position")
        pos_group = _pos_group_from_raw(pos_raw)
        if pos_group != "G":
            # falls aus irgendeinem Grund ein Skater hier landen würde
            continue

        games = _to_int(rec.get("games"))
        minutes = _to_float(rec.get("minutes"))
        wins = _to_int(rec.get("wins"))
        losses = _to_int(rec.get("losses"))
        shutouts = _to_int(rec.get("shutouts"))
        ga = _to_int(rec.get("goals_against"))
        gaa = rec.get("gaa")
        try:
            gaa_val = float(gaa) if gaa is not None else None
        except (TypeError, ValueError):
            gaa_val = None
        shots_against = _to_int(rec.get("shots_against"))
        saves = _to_int(rec.get("saves"))
        sv_pct = rec.get("save_pct")
        try:
            sv_pct_val = float(sv_pct) if sv_pct is not None else None
        except (TypeError, ValueError):
            sv_pct_val = None

        # falls shots_against nicht gesetzt war, aus SV + GA berechnen
        if shots_against == 0 and (saves or ga):
            shots_against = saves + ga

        result.append(
            {
                "league": "DEL",
                "type": "goalie",
                "team_code": None,
                "team_name": rec.get("team"),
                "name_real": name,
                "number": rec.get("number"),
                "nation": rec.get("nation"),
                "position_raw": pos_raw,
                "position_group": "G",

                "gp": games,
                "minutes": minutes,
                "wins": wins,
                "losses": losses,
                "shutouts": shutouts,
                "goals_against": ga,
                "gaa": gaa_val,
                "shots_against": shots_against,
                "saves": saves,
                "sv_pct": sv_pct_val,
            }
        )

    print(f"✅ DEL Goalies: {len(result)} Datensätze normalisiert")
    return result

def dedupe_goalies(players):
    """
    Entfernt doppelte Goalies:
    - Wenn ein Spieler zweimal vorkommt (einmal als Skater, einmal als Goalie),
      dann behalten wir NUR die Goalie-Version.
    """
    by_key = {}  # key = (name_real, number)

    cleaned = []
    for p in players:
        key = (p.get("name_real") or p.get("NameReal"), p.get("number") or p.get("Number"))

        if key not in by_key:
            by_key[key] = p
            cleaned.append(p)
        else:
            existing = by_key[key]

            # echte Goalie-Version bevorzugen
            is_goalie_p = p.get("type") == "goalie" or str(p.get("position_group", "")).upper() == "G"
            is_goalie_existing = existing.get("type") == "goalie" or str(existing.get("position_group", "")).upper() == "G"

            if is_goalie_p and not is_goalie_existing:
                # Ersetze Skater-Version durch Goalie-Version
                cleaned.remove(existing)
                cleaned.append(p)
                by_key[key] = p
            # sonst Skater/Müll ignorieren

    return cleaned

# ----------------- Main -----------------


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Einzelquellen laden
    del2_players = load_del2_players()
    del_skaters  = load_del_skaters()
    del_goalies  = load_del_goalies()

    # 2. Alles zusammenwerfen
    all_players_raw = del2_players + del_skaters + del_goalies

    # 3. Goalie-Duplikate bereinigen
    all_players = dedupe_goalies(all_players_raw)

    print(f"\n📊 Gesamt (nach Dedupe): {len(all_players)} Spieler/Goalies in der Baseline-Datenbank")

    # 4. Schreiben
    OUT_FILE.write_text(
        json.dumps(all_players, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    print(f"💾 Baseline-JSON gespeichert → {OUT_FILE}")

    # 5. Mini-Debug-Ausgabe
    if all_players:
        print("\nBeispiel-Einträge:")
        for rec in all_players[:5]:
            print(
                " -",
                rec["league"],
                rec["type"],
                rec["name_real"],
                "POS:", rec["position_group"],
                "GP:", rec["gp"],
            )



if __name__ == "__main__":
    main()

