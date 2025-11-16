"""
DEL-Stats (Skater + Goalies) aus dem PENNY-DEL-HTML ziehen und
auf eine gemeinsame Baseline normalisieren.

- Quelle Skater:  https://www.penny-del.org/statistik/saison-2025-26/hauptrunde/playerstats/basis
- Quelle Goalies: https://www.penny-del.org/statistik/saison-2025-26/hauptrunde/goaliestats/basis

Baseline-Skater-Felder (für DEL und DEL2 kompatibel):
  league, team (optional), number, name_raw, nation, position,
  games, goals, assists, points, plus_minus, pim,
  faceoff_won, faceoff_total, faceoff_pct

Baseline-Goalie-Felder:
  league, team (optional), number, name_raw, nation, position,
  games, minutes, wins, losses, shutouts,
  goals_against, gaa, shots_against, saves, save_pct

Output:
  data/del_skaters.json
  data/del_goalies.json
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


# ------------------------------------------------------------
#  Helpers
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
#  Normalisierung DEL-SKATER
# ------------------------------------------------------------

def normalize_del_skaters(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Erwartete Spalten laut HTML-Snapshot:
      ['#','Team','#.1','Spieler','Nat','POS','GP','G','A','P','PIM','+','-','+/-','FOW','FOW%']
    """
    # Umbenennen für Klarheit
    df = df.rename(
        columns={
            "#": "Rank",
            "Team": "Team",
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

    players: List[Dict[str, Any]] = []

    for _, row in df.iterrows():
        name = str(row.get("Player", "")).strip()
        if not name or name == "nan":
            continue

        # Name "Nachname,  Vorname" glätten
        name = re.sub(r"\s+", " ", name)

        # Team-Kürzel aus der "Team"-Spalte holen
        team_raw = str(row.get("Team", "")).strip()
        if not team_raw or team_raw.lower() == "nan":
            # Spieler ohne Team ignorieren
            continue
        team = team_raw.upper()

        print("DEL Skater Teams:", sorted(df["Team"].dropna().unique()))

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
                "team": team,  
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

    return players


# ------------------------------------------------------------
#  Normalisierung DEL-GOALIES
# ------------------------------------------------------------

def normalize_del_goalies(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Erwartete Spalten laut HTML-Snapshot:
      ['#','Team','#.1','Spieler','Nat','POS','GP','Min.','S','N','SO','GT','GTS','SV','SV%']
    """
    df = df.rename(
        columns={
            "#": "Rank",
            "Team": "Team",
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

    goalies: List[Dict[str, Any]] = []

    for _, row in df.iterrows():
        name = str(row.get("Player", "")).strip()
        if not name or name == "nan":
            continue

        name = re.sub(r"\s+", " ", name)

        # Team-Kürzel aus der "Team"-Spalte holen
        team_raw = str(row.get("Team", "")).strip()
        if not team_raw or team_raw.lower() == "nan":
            continue
        team = team_raw.upper()

        print("DEL Goalie Teams:", sorted(df["Team"].dropna().unique()))

        minutes = parse_minutes_str(str(row.get("Min", "")).strip())
        sv_pct = parse_float_percent(row.get("SV_pct"))

        ga = int(row["GA"]) if pd.notna(row.get("GA")) else 0
        sv = int(row["SV"]) if pd.notna(row.get("SV")) else 0
        shots_against = sv + ga

        # GAA-Feld kann z. B. "2.38" oder "2,38" oder "2.38 " sein
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
                "team": team,
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

    return goalies


# ------------------------------------------------------------
#  Main
# ------------------------------------------------------------

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # ---- Skater ----
    print("=== DEL Skater laden (HTML) ===")
    html_players = fetch_html(DEL_SKATERS_URL)
    df_players = parse_html_table(html_players)
    print(f"🔎 Skater-Tabelle: {len(df_players)} Zeilen, Spalten: {list(df_players.columns)}")

    skaters = normalize_del_skaters(df_players)
    print(f"✅ Normalisierte Skater: {len(skaters)}")
    print("   Beispiel:", skaters[0] if skaters else "keine Daten")

    OUT_SKATERS.write_text(json.dumps(skaters, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"💾 Skater-JSON gespeichert → {OUT_SKATERS}")

    # ---- Goalies ----
    print("\n=== DEL Goalies laden (HTML) ===")
    html_goalies = fetch_html(DEL_GOALIES_URL)
    df_goalies = parse_html_table(html_goalies)
    print(f"🔎 Goalie-Tabelle: {len(df_goalies)} Zeilen, Spalten: {list(df_goalies.columns)}")

    goalies = normalize_del_goalies(df_goalies)
    print(f"✅ Normalisierte Goalies: {len(goalies)}")
    print("   Beispiel:", goalies[0] if goalies else "keine Daten")

    OUT_GOALIES.write_text(json.dumps(goalies, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"💾 Goalie-JSON gespeichert → {OUT_GOALIES}")


if __name__ == "__main__":
    main()
