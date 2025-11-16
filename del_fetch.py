"""
DEL-Stats (Skater + Goalies) aus dem PENNY-DEL-HTML ziehen und
auf eine gemeinsame Baseline normalisieren.

- Quelle Skater:  https://www.penny-del.org/statistik/saison-2025-26/hauptrunde/playerstats/basis
- Quelle Goalies: https://www.penny-del.org/statistik/saison-2025-26/hauptrunde/goaliestats/basis

Baseline-Skater-Felder (für DEL und DEL2 kompatibel):
  league, team (Code), number, name_raw, nation, position,
  games, goals, assists, points, plus_minus, pim,
  faceoff_won, faceoff_total, faceoff_pct

Baseline-Goalie-Felder:
  league, team (Code), number, name_raw, nation, position,
  games, minutes, wins, losses, shutouts,
  goals_against, gaa, shots_against, saves, save_pct

Output:
  data/del_skaters.json
  data/del_goalies.json

Benötigt:
  data/del_team_id_map.json   (Mapping Logo-ID -> Team-Code)
"""

from __future__ import annotations

import json
import re
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

# ------------------------------------------------------------
#  Konfiguration
# ------------------------------------------------------------

DEL_SKATERS_URL = (
    "https://www.penny-del.org/statistik/saison-2025-26/hauptrunde/playerstats/basis"
)
DEL_GOALIES_URL = (
    "https://www.penny-del.org/statistik/saison-2025-26/hauptrunde/goaliestats/basis"
)

OUT_DIR = Path("data")
OUT_SKATERS = OUT_DIR / "del_skaters.json"
OUT_GOALIES = OUT_DIR / "del_goalies.json"

TEAM_ID_MAP_FILE = OUT_DIR / "del_team_id_map.json"


# ------------------------------------------------------------
#  Helpers: HTTP & Parsing
# ------------------------------------------------------------

def fetch_html(url: str) -> str:
    """HTML von einer DEL-URL holen (einfache GET-Request)."""
    print(f"🌐 Lade HTML von {url}")
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    return resp.text


def parse_html_table(html: str) -> pd.DataFrame:
    """Erste HTML-Tabelle aus einem HTML-String ziehen (via pandas.read_html)."""
    tables = pd.read_html(StringIO(html))
    if not tables:
        raise RuntimeError("Keine Tabelle im HTML gefunden.")
    if len(tables) > 1:
        print(f"⚠️ Achtung: {len(tables)} Tabellen gefunden, nutze Tabelle 0.")
    return tables[0]


def parse_minutes_str(s: str) -> float:
    """
    Min.-String in Minuten konvertieren.
    Unterstützt:
      - '807:39' (min:sec)
      - '07:36:10' (h:mm:ss)
    Rückgabe: float Minuten.
    """
    if not isinstance(s, str) or not s.strip():
        return 0.0
    s = s.strip()
    parts = s.split(":")
    nums: List[int] = []
    for p in parts:
        p = p.strip()
        if not p:
            nums.append(0)
        else:
            p_clean = p.replace(".", "").replace(",", "")
            if p_clean.isdigit():
                nums.append(int(p_clean))
            else:
                nums.append(0)
    if len(nums) == 2:
        m, sec = nums
        return m + sec / 60.0
    if len(nums) == 3:
        h, m, sec = nums
        return h * 60 + m + sec / 60.0
    return 0.0


def parse_float_percent(val: Any) -> Optional[float]:
    """'94,64 %' → 94.64"""
    if isinstance(val, (int, float)):
        return float(val)
    if not isinstance(val, str):
        return None
    s = val.strip().replace("%", "").replace(" %", "").replace(",", ".")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


# ------------------------------------------------------------
#  Team-ID-Mapping (Logo-ID -> Team-Code)
# ------------------------------------------------------------

def load_team_id_map() -> Dict[int, str]:
    """
    Lädt data/del_team_id_map.json.

    Dein Format:

    {
      "1":  { "real": "ERC Ingolstadt", "real_code": "ING", "fake": "Novadelta Panther", "fake_code": "NDP" },
      "2":  { "real": "Adler Mannheim", "real_code": "MAN", "fake": "Mannheim Ventus", "fake_code": "MVE" },
      ...
    }

    → Wir verwenden hier den real_code (ING, MAN, …) als 'team'-Feld
      in den DEL-Skater-/Goalie-JSONs.
    """
    if not TEAM_ID_MAP_FILE.exists():
        raise FileNotFoundError(
            f"team-id-map-Datei nicht gefunden: {TEAM_ID_MAP_FILE} "
            f"(erwartet Mapping Logo-ID -> Team-Meta mit real_code/fake_code)"
        )

    raw = json.loads(TEAM_ID_MAP_FILE.read_text(encoding="utf-8"))
    mapping: Dict[int, str] = {}

    if isinstance(raw, dict):
        # Keys = Logo-ID als String, Values = Dict mit real/real_code/fake/fake_code
        for k, v in raw.items():
            try:
                logo_id = int(k)
            except ValueError:
                print(f"[WARN] Ungültiger Logo-ID-Key in del_team_id_map.json: {k!r}")
                continue

            if not isinstance(v, dict):
                print(f"[WARN] Unerwarteter Wert für Logo-ID {logo_id}: {v!r}")
                continue

            # Standard: real_code benutzen
            code_val = v.get("real_code") or v.get("real") or v.get("fake_code")
            if not code_val:
                print(f"[WARN] Kein real_code/fake_code für Logo-ID {logo_id}: {v}")
                continue

            code = str(code_val).strip().upper()
            if not code:
                print(f"[WARN] Leerer Code für Logo-ID {logo_id} in del_team_id_map.json")
                continue

            mapping[logo_id] = code

    else:
        raise ValueError(
            f"del_team_id_map.json hat unerwartetes Format (Typ {type(raw)}). "
            "Für dein aktuelles Setup wird ein Dict erwartet."
        )

    print(f"✅ del_team_id_map geladen: {len(mapping)} Logo-IDs")
    for lid, code in sorted(mapping.items()):
        print(f"   - ID {lid}: {code}")
    return mapping



# ------------------------------------------------------------
#  Team-IDs aus Player-/Goalie-Stats-HTML
# ------------------------------------------------------------

def extract_team_ids_from_stats_html(html: str) -> List[Optional[int]]:
    """
    Geht über die <tbody>-Zeilen der Stats-Tabelle (Skater oder Goalies) und
    extrahiert pro <tr> das erste Vorkommen von 'team_X' aus dem <img src>.

    Fehlt ein Logo in einer Zeile, wird die letzte bekannte ID durchgereicht.
    """
    start = html.find("<tbody")
    end = html.find("</tbody>", start)
    if start == -1 or end == -1:
        raise RuntimeError("Keine <tbody> in Stats-HTML gefunden")

    tbody = html[start:end]
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", tbody, flags=re.S)

    team_ids: List[Optional[int]] = []
    current: Optional[int] = None

    for row_html in rows:
        m = re.search(r'team_(\d+)[^"]*\.(?:png|svg)', row_html)
        if m:
            current = int(m.group(1))
        team_ids.append(current)

    ids_clean = sorted({i for i in team_ids if i is not None})
    print(f"🧩 Team-IDs aus Stats-HTML: {len(team_ids)} Zeilen, IDs = {ids_clean}")
    return team_ids


# ------------------------------------------------------------
#  Normalisierung DEL-SKATER
# ------------------------------------------------------------

def normalize_del_skaters(
    df: pd.DataFrame,
    team_ids: List[Optional[int]],
    logo_id_to_code: Dict[int, str],
) -> List[Dict[str, Any]]:
    """
    Erwartete Spalten laut HTML-Snapshot:
      ['#','Team','#.1','Spieler','Nat','POS','GP','G','A','P','PIM','+','-','+/-','FOW','FOW%']

    df: DataFrame aus pandas.read_html(...)
    team_ids: pro Zeile eine Logo-ID (oder None), gleiche Länge wie df
    logo_id_to_code: Mapping {logo_id: 'ING' | 'MUC' | ...} aus del_team_id_map.json
    """
    df = df.rename(
        columns={
            "#": "Rank",
            "#.1": "No",
            "Spieler": "Player",
            "Nat": "Nation",
            "POS": "Pos",
            "GP": "GP",
            "G": "G",
            "A": "A",
            "P": "P",
            "PIM": "PIM",
            "+": "Plus",
            "-": "Minus",
            "+/-": "PlusMinus",
            "FOW": "FOW_raw",
            "FOW%": "FOW_pct_raw",
        }
    )

    if len(team_ids) != len(df):
        print(
            f"⚠️ team_ids-Länge ({len(team_ids)}) passt nicht zu df-Zeilen ({len(df)}). "
            f"Ich versuche trotzdem zu mappen."
        )

    players: List[Dict[str, Any]] = []
    unknown_logo_ids: set[int] = set()

    for idx, (_, row) in enumerate(df.iterrows()):
        name = str(row.get("Player", "")).strip()
        if not name or name == "nan":
            continue

        # Name "Nachname, Vorname" glätten
        name = re.sub(r"\s+", " ", name)

        # Team über Logo-ID
        logo_id: Optional[int] = team_ids[idx] if idx < len(team_ids) else None
        team_code: Optional[str] = None
        if logo_id is not None:
            team_code = logo_id_to_code.get(logo_id)
            if team_code is None:
                unknown_logo_ids.add(logo_id)
                print(f"[WARN] DEL-Skater {name}: Logo-ID {logo_id} nicht im ID-Mapping")
        else:
            print(f"[WARN] DEL-Skater {name}: keine Logo-ID in dieser Zeile gefunden")

        # Faceoffs: "102 / 206" oder "-/-"
        fow_raw = str(row.get("FOW_raw", "")).strip()
        fow_won: Optional[int] = None
        fow_tot: Optional[int] = None
        if "/" in fow_raw:
            try:
                left, right = fow_raw.split("/")
                left = left.replace(" ", "")
                right = right.replace(" ", "")
                if left.isdigit() and right.isdigit():
                    fow_won = int(left)
                    fow_tot = int(right)
            except Exception:
                pass

        fow_pct = parse_float_percent(row.get("FOW_pct_raw"))

        # Plus/Minus
        plus_minus: Optional[int]
        if pd.notna(row.get("PlusMinus")):
            plus_minus = int(row["PlusMinus"])
        elif pd.notna(row.get("Plus")) and pd.notna(row.get("Minus")):
            plus_minus = int(row["Plus"]) - int(row["Minus"])
        else:
            plus_minus = None

        players.append(
            {
                "league": "DEL",
                "team": team_code,
                "team_logo_id": logo_id,
                "number": int(row["No"]) if pd.notna(row.get("No")) else None,
                "name_raw": name,
                "nation": str(row.get("Nation", "")).strip() or None,
                "position": str(row.get("Pos", "")).strip() or None,
                "games": int(row["GP"]) if pd.notna(row.get("GP")) else 0,
                "goals": int(row["G"]) if pd.notna(row.get("G")) else 0,
                "assists": int(row["A"]) if pd.notna(row.get("A")) else 0,
                "points": int(row["P"]) if pd.notna(row.get("P")) else 0,
                "plus_minus": plus_minus,
                "pim": int(row["PIM"]) if pd.notna(row.get("PIM")) else 0,
                "faceoff_won": fow_won,
                "faceoff_total": fow_tot,
                "faceoff_pct": fow_pct,
            }
        )

    if unknown_logo_ids:
        print("\n⚠️ Unbekannte Logo-IDs bei Skatern (in del_team_id_map.json nicht vorhanden):")
        for lid in sorted(unknown_logo_ids):
            print(f"   - Logo-ID {lid}")

    return players


# ------------------------------------------------------------
#  Normalisierung DEL-GOALIES
# ------------------------------------------------------------

def normalize_del_goalies(
    df: pd.DataFrame,
    team_ids: List[Optional[int]],
    logo_id_to_code: Dict[int, str],
) -> List[Dict[str, Any]]:
    """
    Erwartete Spalten laut HTML-Snapshot:
      ['#','Team','#.1','Spieler','Nat','POS','GP','Min.','S','N','SO','GT','GTS','SV','SV%']

    df: DataFrame aus pandas.read_html(...)
    team_ids: pro Zeile eine Logo-ID (oder None), gleiche Länge wie df
    logo_id_to_code: Mapping {logo_id: 'ING' | 'MUC' | ...} aus del_team_id_map.json
    """
    df = df.rename(
        columns={
            "#": "Rank",
            "#.1": "No",
            "Spieler": "Player",
            "Nat": "Nation",
            "POS": "Pos",
            "GP": "GP",
            "Min.": "Min",
            "S": "W",   # Siege
            "N": "L",   # Niederlagen
            "SO": "SO",
            "GT": "GA",
            "GTS": "GAA",
            "SV": "SV",
            "SV%": "SV_pct",
        }
    )

    if len(team_ids) != len(df):
        print(
            f"⚠️ team_ids-Länge ({len(team_ids)}) passt nicht zu df-Zeilen ({len(df)}). "
            f"Ich versuche trotzdem zu mappen."
        )

    goalies: List[Dict[str, Any]] = []
    unknown_logo_ids: set[int] = set()

    for idx, (_, row) in enumerate(df.iterrows()):
        name = str(row.get("Player", "")).strip()
        if not name or name == "nan":
            continue

        name = re.sub(r"\s+", " ", name)

        logo_id: Optional[int] = team_ids[idx] if idx < len(team_ids) else None
        team_code: Optional[str] = None
        if logo_id is not None:
            team_code = logo_id_to_code.get(logo_id)
            if team_code is None:
                unknown_logo_ids.add(logo_id)
                print(f"[WARN] DEL-Goalie {name}: Logo-ID {logo_id} nicht im ID-Mapping")
        else:
            print(f"[WARN] DEL-Goalie {name}: keine Logo-ID in dieser Zeile gefunden")

        minutes = parse_minutes_str(str(row.get("Min", "")).strip())
        sv_pct = parse_float_percent(row.get("SV_pct"))

        ga = int(row["GA"]) if pd.notna(row.get("GA")) else 0
        sv = int(row["SV"]) if pd.notna(row.get("SV")) else 0
        shots_against = sv + ga

        raw_gaa = row.get("GAA")
        if pd.notna(raw_gaa):
            try:
                gaa = float(str(raw_gaa).replace(",", ".").replace(" ", ""))
            except ValueError:
                gaa = None
        else:
            gaa = None

        goalies.append(
            {
                "league": "DEL",
                "team": team_code,
                "team_logo_id": logo_id,
                "number": int(row["No"]) if pd.notna(row.get("No")) else None,
                "name_raw": name,
                "nation": str(row.get("Nation", "")).strip() or None,
                "position": str(row.get("Pos", "")).strip() or None,
                "games": int(row["GP"]) if pd.notna(row.get("GP")) else 0,
                "minutes": minutes,
                "wins": int(row["W"]) if pd.notna(row.get("W")) else 0,
                "losses": int(row["L"]) if pd.notna(row.get("L")) else 0,
                "shutouts": int(row["SO"]) if pd.notna(row.get("SO")) else 0,
                "goals_against": ga,
                "gaa": gaa,
                "shots_against": shots_against,
                "saves": sv,
                "save_pct": sv_pct,
            }
        )

    if unknown_logo_ids:
        print("\n⚠️ Unbekannte Logo-IDs bei Goalies (in del_team_id_map.json nicht vorhanden):")
        for lid in sorted(unknown_logo_ids):
            print(f"   - Logo-ID {lid}")

    return goalies


# ------------------------------------------------------------
#  Main
# ------------------------------------------------------------

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # ---- Team-ID-Mapping laden ----
    print("=== del_team_id_map laden ===")
    logo_id_map = load_team_id_map()

    # ---- Skater ----
    print("\n=== DEL Skater laden (HTML) ===")
    html_players = fetch_html(DEL_SKATERS_URL)
    team_ids_skaters = extract_team_ids_from_stats_html(html_players)

    df_players = parse_html_table(html_players)
    print(f"🔎 Skater-Tabelle: {len(df_players)} Zeilen, Spalten: {list(df_players.columns)}")

    skaters = normalize_del_skaters(df_players, team_ids_skaters, logo_id_map)
    print(f"✅ Normalisierte Skater: {len(skaters)}")
    if skaters:
        print("   Beispiel Skater:", skaters[0])

    OUT_SKATERS.write_text(json.dumps(skaters, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"💾 Skater-JSON gespeichert → {OUT_SKATERS}")

    # ---- Goalies ----
    print("\n=== DEL Goalies laden (HTML) ===")
    html_goalies = fetch_html(DEL_GOALIES_URL)
    team_ids_goalies = extract_team_ids_from_stats_html(html_goalies)

    df_goalies = parse_html_table(html_goalies)
    print(f"🔎 Goalie-Tabelle: {len(df_goalies)} Zeilen, Spalten: {list(df_goalies.columns)}")

    goalies = normalize_del_goalies(df_goalies, team_ids_goalies, logo_id_map)
    print(f"✅ Normalisierte Goalies: {len(goalies)}")
    if goalies:
        print("   Beispiel Goalie:", goalies[0])

    OUT_GOALIES.write_text(json.dumps(goalies, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"💾 Goalie-JSON gespeichert → {OUT_GOALIES}")


if __name__ == "__main__":
    main()
