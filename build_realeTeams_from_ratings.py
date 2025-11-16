from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional

# ------------------------------------------------------------
# Pfade
# ------------------------------------------------------------

BASE_DIR = Path(".")
DATA_DIR = BASE_DIR / "data"

PLAYERS_FILE = DATA_DIR / "players_rated.json"
TEAM_MAPPING_FILE = DATA_DIR / "team_mapping.json"
NAME_MAPPING_FILE = DATA_DIR / "mapping_player_names.json"
OUTPUT_FILE = BASE_DIR / "realeTeams_live.py"


# ------------------------------------------------------------
# Loader
# ------------------------------------------------------------

def load_players() -> List[Dict[str, Any]]:
    if not PLAYERS_FILE.exists():
        raise FileNotFoundError(f"{PLAYERS_FILE} nicht gefunden.")
    raw = json.loads(PLAYERS_FILE.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("players_rated.json muss eine Liste sein.")
    return raw


def load_team_mapping() -> Tuple[List[Dict[str, Any]],
                                 Dict[Tuple[str, str], Dict[str, Any]],
                                 Dict[Tuple[str, str], Dict[str, Any]]]:
    """
    team_mapping.json:
    [
      {
        "league": "DEL",
        "real_team_name": "Eisbären Berlin",
        "real_code": "BER",
        "highspeed_name": "Whiteout Berlin",
        "highspeed_code": "WOB",
        "conference": "Nord"
      },
      ...
    ]

    Rückgabe:
      - liste aller Einträge
      - dict_by_code[(league, real_code)] -> mapping
      - dict_by_name[(league, real_team_name)] -> mapping
    """
    if not TEAM_MAPPING_FILE.exists():
        raise FileNotFoundError(f"{TEAM_MAPPING_FILE} nicht gefunden.")

    raw = json.loads(TEAM_MAPPING_FILE.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("team_mapping.json muss eine Liste sein.")

    by_code: Dict[Tuple[str, str], Dict[str, Any]] = {}
    by_name: Dict[Tuple[str, str], Dict[str, Any]] = {}

    for entry in raw:
        league = str(entry.get("league", "")).strip()
        real_code = entry.get("real_code")
        real_name = entry.get("real_team_name")

        if league and real_code:
            by_code[(league, str(real_code).strip())] = entry
        if league and real_name:
            by_name[(league, str(real_name).strip())] = entry

    return raw, by_code, by_name


def load_name_mapping() -> Dict[str, str]:
    """
    mapping_player_names.json:
    [
      { "real": "Riley Barber", "fake": "Rilan Barvik" },
      ...
    ]
    → Rückgabe: { "Riley Barber": "Rilan Barvik", ... }
    """
    if not NAME_MAPPING_FILE.exists():
        print(f"⚠️  {NAME_MAPPING_FILE} nicht gefunden – echte Namen werden verwendet.")
        return {}

    raw = json.loads(NAME_MAPPING_FILE.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("mapping_player_names.json muss eine Liste sein.")

    mapping: Dict[str, str] = {}
    for entry in raw:
        real = str(entry.get("real", "")).strip()
        fake = str(entry.get("fake", "")).strip()
        if real and fake:
            mapping[real] = fake
    return mapping


# ------------------------------------------------------------
# Hilfen
# ------------------------------------------------------------

def get_fake_name(real_name: str, name_map: Dict[str, str]) -> str:
    """
    Holt Fake-Namen aus mapping_player_names.json.
    Fallback: realer Name, wenn kein Mapping (mit Warnung).
    """
    if real_name in name_map:
        return name_map[real_name]
    print(f"⚠️  Kein Fake-Name-Mapping für Spieler '{real_name}' – verwende Realnamen.")
    return real_name


def derive_position_group(player: Dict[str, Any]) -> str:
    """
    PositionGroup aus den vorhandenen Feldern ableiten – robust.
    Erwartet idealerweise 'position_group' im players_rated.json.
    Fallback: aus position_raw / position.
    """
    pg = player.get("position_group")
    if isinstance(pg, str) and pg:
        return pg.upper()

    pos_raw = str(player.get("position_raw") or player.get("position") or "").upper()

    # Sehr grobe Heuristik:
    if pos_raw.startswith("G") or pos_raw == "GK":
        return "G"
    if pos_raw.startswith("D"):
        return "D"
    return "F"


def build_realeTeams_from_ratings() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    players = load_players()
    _, team_by_code, team_by_name = load_team_mapping()
    name_map = load_name_mapping()

    teams: Dict[str, Dict[str, Any]] = {}  # key: highspeed_code
    unknown_team_keys = set()  # zum Sammeln von Teams ohne Mapping

    for p in players:
        league = str(p.get("league", "")).strip()
        if league not in ("DEL", "DEL2"):
            continue  # andere Ligen aktuell ignorieren

        # ---- Teamcode / Teamname aus players_rated.json
        raw_code = p.get("team_code")
        raw_name = p.get("team_name")

        # beides kann None sein; bei DEL oft: code=None, name="MUC"
        # bei DEL2 oft: code="SCB", name=None
        code_candidate = None
        if isinstance(raw_code, str) and raw_code.strip():
            code_candidate = raw_code.strip()
        elif isinstance(raw_name, str) and raw_name.strip():
            # hier ist 'team_name' in deiner Datenbasis bei DEL ein Kürzel wie "MUC"
            code_candidate = raw_name.strip()

        mapping_entry: Optional[Dict[str, Any]] = None

        # 1) Versuch: über Code (BER, WOB, MUC, EVL, etc.)
        if code_candidate:
            mapping_entry = team_by_code.get((league, code_candidate))

        # 2) Versuch: über "vollen" Namen (falls du irgendwann echte Namen in team_name speicherst)
        if mapping_entry is None and isinstance(raw_name, str) and raw_name.strip():
            mapping_entry = team_by_name.get((league, raw_name.strip()))

        if mapping_entry is None:
            key = (league, code_candidate or "NONE", raw_name or "NONE")
            if key not in unknown_team_keys:
                unknown_team_keys.add(key)
            # Spieler bleiben in players_rated.json, aber wir nehmen sie nicht in realeTeams auf
            continue

        high_name = mapping_entry.get("highspeed_name")
        high_code = mapping_entry.get("highspeed_code")
        conference = mapping_entry.get("conference", "")

        if not high_name or not high_code:
            # kaputte Mappingzeilen wollen wir nicht
            continue

        # Team-Container in Dict anlegen
        if high_code not in teams:
            teams[high_code] = {
                "Team": high_name,
                "Code": high_code,
                "Conference": conference,
                "Players": [],
            }

        # Fake-Name & Positionsgruppe
        real_name = str(p.get("name_real") or p.get("name_raw") or "").strip()
        if not real_name:
            # zur Sicherheit: wenn echt gar kein Name drin ist, überspringen
            continue
        fake_name = get_fake_name(real_name, name_map)
        pos_group = derive_position_group(p)

        # Spiele
        gp = p.get("gp")
        if gp is None:
            gp = p.get("games", 0)
        try:
            gp = int(gp)
        except Exception:
            gp = 0

        # Ratings (bereits aus build_ratings.py berechnet)
        r_off = p.get("rating_offense", 40)
        r_def = p.get("rating_defense", 40)
        r_spd = p.get("rating_speed", 40)
        r_chem = p.get("rating_chemistry", 40)
        r_ovr = p.get("rating_overall", 50)

        player_obj = {
            "Name": fake_name,
            "NameReal": real_name,
            "Number": p.get("number"),
            "Nation": p.get("nation"),
            "PositionRaw": p.get("position_raw") or p.get("position"),
            "PositionGroup": pos_group,
            "GamesPlayed": gp,
            # Originalwerte optional mitgeben, kann später für Stats / UI hilfreich sein
            "League": league,
            "TeamCodeReal": code_candidate,
            "TeamNameRaw": raw_name,
            # Ratings → exakt die Keys, die dein Generator nutzt:
            "Offense": r_off,
            "Defense": r_def,
            "Speed": r_spd,
            "Chemistry": r_chem,
            "Overall": r_ovr,

            "Minutes": p.get("minutes"),
            "GoalsAgainst": p.get("goals_against"),
            "ShotsAgainst": p.get("shots_against"),
            "Saves": p.get("saves"),
            "SavePct": p.get("save_pct"),
            "GAA": p.get("gaa"),
        }

        teams[high_code]["Players"].append(player_obj)

    # ---- Warnungen für Teams ohne Mapping
    if unknown_team_keys:
        print("ℹ️  Teams ohne Mapping in team_mapping.json (werden ignoriert):")
        for league, code_candidate, raw_name in sorted(unknown_team_keys):
            print(f"   - league={league} code={code_candidate!r} name={raw_name!r}")

    # ---- Aufteilen in Nord / Süd
    nord_teams: List[Dict[str, Any]] = []
    sued_teams: List[Dict[str, Any]] = []

    for code, t in sorted(teams.items(), key=lambda kv: kv[0]):
        conf = (t.get("Conference") or "").lower()
        if conf == "nord":
            nord_teams.append(t)
        elif conf in ("sued", "süd"):
            sued_teams.append(t)
        else:
            print(f"⚠️  Team ohne gültige Conference (Nord/Sued): {t['Team']} – Conference={t.get('Conference')}")

    print(f"✅ Teams insgesamt: {len(teams)}")
    print(f"   → Nord: {len(nord_teams)}")
    print(f"   → Süd : {len(sued_teams)}")

    return nord_teams, sued_teams


def write_realeTeams_py(nord: List[Dict[str, Any]], sued: List[Dict[str, Any]]) -> None:
    """
    schreibt realeTeams_live.py mit nord_teams / sued_teams als Python-Listen.
    """
    content = [
        "# Diese Datei wurde automatisch aus players_rated.json erzeugt.",
        "# Enthält die aktuellen REALEN Kader als HIGHspeed-Teams (Nord/Süd).",
        "",
        "nord_teams = ",
        json.dumps(nord, indent=2, ensure_ascii=False),
        "",
        "sued_teams = ",
        json.dumps(sued, indent=2, ensure_ascii=False),
        "",
    ]
    OUTPUT_FILE.write_text("\n".join(content), encoding="utf-8")
    print(f"💾 Datei geschrieben: {OUTPUT_FILE}")


def main() -> None:
    nord, sued = build_realeTeams_from_ratings()
    write_realeTeams_py(nord, sued)


if __name__ == "__main__":
    main()
