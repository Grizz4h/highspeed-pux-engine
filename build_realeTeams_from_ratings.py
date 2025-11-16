from __future__ import annotations

import json
from pathlib import Path
from collections import defaultdict
import pprint

# -------------------------
# Pfade
# -------------------------
DATA_DIR = Path("data")
PLAYERS_FILE = DATA_DIR / "players_rated.json"
TEAM_MAPPING_FILE = DATA_DIR / "team_mapping.json"
PLAYER_MAPPING_FILE = DATA_DIR / "mapping_player_names.json"

OUTPUT_FILE = Path("realeTeams_live.py")

# Deine Nord/Süd-Fake-Teams


# -------------------------
# Team-Mapping laden
# -------------------------
def load_team_mapping() -> tuple[dict[str, str], dict[str, str]]:
    """
    Liest data/team_mapping.json im Format:

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
      - name_map:      z.B. {"BER": "Whiteout Berlin", "DEL|BER": "Whiteout Berlin", ...}
      - conference_map: z.B. {"Whiteout Berlin": "Nord", "Novadelta Panther": "Sued", ...}
    """
    if not TEAM_MAPPING_FILE.exists():
        print(f"⚠️  {TEAM_MAPPING_FILE} nicht gefunden – verwende Team-Code als Namen.")
        return {}, {}

    raw = json.loads(TEAM_MAPPING_FILE.read_text(encoding="utf-8"))

    if not isinstance(raw, list):
        print("⚠️  team_mapping.json ist kein Array – erwarte Liste von Objekten.")
        return {}, {}

    name_map: dict[str, str] = {}
    conference_map: dict[str, str] = {}

    for item in raw:
        if not isinstance(item, dict):
            continue

        league = item.get("league")         # "DEL" / "DEL2"
        real_code = item.get("real_code")   # z. B. "BER"
        high_name = item.get("highspeed_name")  # "Whiteout Berlin"
        high_code = item.get("highspeed_code")  # z. B. "WOB"
        conf = item.get("conference")       # "Nord" / "Sued"

        # Mapping Code -> Highspeed-Name
        if isinstance(real_code, str) and isinstance(high_name, str):
            name_map[real_code] = high_name
            if isinstance(league, str):
                name_map[f"{league}|{real_code}"] = high_name

        # optional: Highspeed-Code auch mappen
        if isinstance(high_code, str) and isinstance(high_name, str):
            name_map[high_code] = high_name

        # Conference-Mapping
        if isinstance(high_name, str) and isinstance(conf, str):
            conference_map[high_name] = conf

    if not name_map:
        print("⚠️  Konnte aus team_mapping.json keine Team-Namen-Mappings extrahieren.")
    if not conference_map:
        print("⚠️  Konnte aus team_mapping.json keine Conference-Mappings extrahieren.")

    return name_map, conference_map


# -------------------------
# Spieler-Mapping laden
# -------------------------
def load_player_mapping() -> dict[str, str]:
    """
    Erwartetes Format (Liste):

    [
      { "real": "Konrad Abeltshauser", "fake": "Konradu Abeltshausdunov" },
      ...
    ]
    """
    if not PLAYER_MAPPING_FILE.exists():
        print(f"⚠️  {PLAYER_MAPPING_FILE} nicht gefunden – verwende Realnamen.")
        return {}

    raw = json.loads(PLAYER_MAPPING_FILE.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        print("⚠️  mapping_player_names.json ist kein Array – erwarte Liste von Objekten.")
        return {}

    mapping: dict[str, str] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        real = item.get("real")
        fake = item.get("fake")
        if isinstance(real, str) and isinstance(fake, str):
            mapping[real.strip()] = fake.strip()

    if not mapping:
        print("⚠️  Keine Spieler-Mappings gefunden – verwende Realnamen.")
    return mapping


def resolve_team_name(team_code: str | None, league: str, team_map: dict[str, str]) -> str:
    """Sorgt dafür, dass immer ein String als Teamname zurückkommt."""
    code = (str(team_code).strip() if team_code is not None else "")

    # 1) Liga-spezifisches Mapping: "DEL|BER"
    if code and league:
        key = f"{league}|{code}"
        if key in team_map:
            return team_map[key]

    # 2) Nur Code: "BER"
    if code and code in team_map:
        return team_map[code]

    # 3) Fallback: zumindest der Code, oder Dummy
    if code:
        return code
    if league:
        return f"{league}_UNKNOWN"
    return "UNKNOWN_TEAM"


def resolve_fake_player_name(name_real: str | None, player_map: dict[str, str]) -> str:
    if not name_real:
        return "Unknown Player"
    key = name_real.strip()
    if key in player_map:
        return player_map[key]
    # Fallback: Realname
    return name_real

# -------------------------
# Hauptfunktion: aus players_rated → realeTeams_live
# -------------------------
def build_realeTeams_from_ratings() -> tuple[list[dict], list[dict]]:
    if not PLAYERS_FILE.exists():
        raise FileNotFoundError(f"{PLAYERS_FILE} nicht gefunden")

    players = json.loads(PLAYERS_FILE.read_text(encoding="utf-8"))
    if not isinstance(players, list):
        raise ValueError("players_rated.json muss eine Liste von Spielern enthalten")

    team_map, conference_map = load_team_mapping()
    player_map = load_player_mapping()

    teams_dict: dict[str, dict] = {}
    players_by_team: dict[str, list] = defaultdict(list)

    for p in players:
        if not isinstance(p, dict):
            continue

        league = p.get("league", "")  # "DEL" / "DEL2"
        team_code = p.get("team_code")  # z. B. "BER", "FRB"
        name_real = p.get("name_real", "Unknown Player")

        fake_team = resolve_team_name(team_code, league, team_map)
        fake_name = resolve_fake_player_name(name_real, player_map)

        player_entry = {
            "Name": fake_name,
            # diese vier Felder nutzt der Generator aktuell:
            "Offense": p.get("rating_offense", 50),
            "Defense": p.get("rating_defense", 50),
            "Speed": p.get("rating_speed", 50),
            "Chemistry": p.get("rating_chemistry", 50),
            # Zusatzinfos für später:
            "Overall": p.get("rating_overall", 50),
            "League": league,
            "TeamCode": team_code,
            "Number": p.get("number"),
            "Nation": p.get("nation"),
            "PositionRaw": p.get("position_raw"),
            "PositionGroup": p.get("position_group"),  # "F", "D", "G"
            "GP": p.get("gp", 0),
            "Goals": p.get("goals", 0),
            "Assists": p.get("assists", 0),
            "Points": p.get("points", 0),
            "PlusMinus": p.get("plus_minus", 0),
            "PIM": p.get("pim", 0),
            "FO_Won": p.get("fo_won", 0),
            "FO_Lost": p.get("fo_lost", 0),
            "FO_Pct": p.get("fo_pct", 0.0),
            "Type": p.get("type"),  # "skater" / "goalie"
            "Minutes": p.get("minutes", 0.0),
            "Wins": p.get("wins", 0),
            "Losses": p.get("losses", 0),
            "Shutouts": p.get("shutouts", 0),
            "GoalsAgainst": p.get("goals_against", 0),
            "GAA": p.get("gaa", 0.0),
            "ShotsAgainst": p.get("shots_against", 0),
            "Saves": p.get("saves", 0),
            "SV_Pct": p.get("sv_pct", 0.0),
        }

        players_by_team[fake_team].append(player_entry)

        if fake_team not in teams_dict:
            teams_dict[fake_team] = {
                "Team": fake_team,
                "League": league,
                "TeamCode": team_code,
                "Players": players_by_team[fake_team],
                "Momentum": 0,
            }

    nord_list: list[dict] = []
    sued_list: list[dict] = []
    others: list[str] = []

    for team_name, team_data in sorted(teams_dict.items(), key=lambda kv: str(kv[0])):
        conf = conference_map.get(team_name, "").lower()
        if conf.startswith("nord"):
            nord_list.append(team_data)
        elif conf.startswith("sued") or conf.startswith("süd"):
            sued_list.append(team_data)
        else:
            others.append(team_name)


    print(f"✅ Teams insgesamt: {len(teams_dict)}")
    print(f"   → Nord: {len(nord_list)}")
    print(f"   → Süd : {len(sued_list)}")
    if others:
        print("ℹ️  Teams außerhalb deiner 10+10 Highspeed-Teams (werden ignoriert):")
        for t in others:
            print("   -", t)

    return nord_list, sued_list


def write_realeTeams_py(nord: list[dict], sued: list[dict]) -> None:
    content_lines = [
        "# AUTO-GENERATED from data/players_rated.json",
        "# Bitte nicht manuell bearbeiten – Skript: build_realeTeams_from_ratings.py",
        "",
        "nord_teams = ",
        pprint.pformat(nord, width=120, sort_dicts=False),
        "",
        "sued_teams = ",
        pprint.pformat(sued, width=120, sort_dicts=False),
        "",
    ]
    OUTPUT_FILE.write_text("\n".join(content_lines), encoding="utf-8")
    print(f"💾 Datei geschrieben: {OUTPUT_FILE}")


def main() -> None:
    nord, sued = build_realeTeams_from_ratings()
    write_realeTeams_py(nord, sued)


if __name__ == "__main__":
    main()
