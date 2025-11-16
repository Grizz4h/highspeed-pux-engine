# del2_fetch.py
#
# Holt DEL2-Skater- und Goalie-Tabellen (HTML)
# und speichert sie in ein gemeinsames Baseline-Schema,
# das mit DEL kompatibel ist.
#
# Output: data/del2_players.json
# Struktur pro Spieler:
#   - league: "DEL2"
#   - type: "skater" | "goalie"
#   - team_code, name_real, number, nation
#   - position_raw, position_group
#   - Skater-Stats: gp, goals, assists, points, points_per_game,
#                   plus_minus, pp_goals, sh_goals,
#                   pim, fo_won, fo_lost, fo_pct
#   - Goalie-Stats: gp, minutes, wins, losses, shutouts,
#                   goals_against, gaa, shots_against, saves, sv_pct

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import requests


# === URLs – die funktionieren bei dir bereits ===
DEL2_SKATERS_URL = "https://www.del-2.org/stats/scorer/?round=146&club=0"
DEL2_GOALIES_URL = "https://www.del-2.org/stats/goalies/?round=146&club=0"

OUTFILE = Path("data/del2_players.json")


def fetch_html(url: str) -> str:
    """HTML einer Seite holen – mit einfachem User-Agent."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        )
    }
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    return resp.text


def load_table(url: str) -> pd.DataFrame:
    """Liest die erste HTML-Tabelle einer Seite als DataFrame."""
    html = fetch_html(url)
    tables = pd.read_html(StringIO(html))
    if not tables:
        raise RuntimeError(f"Keine Tabellen gefunden bei {url}")
    print(f"🔎 {len(tables)} Tabellen gefunden bei {url}")
    for i, t in enumerate(tables):
        print(f"  Tabelle {i}: Spalten -> {list(t.columns)}")
    return tables[0]


# ---------- Helfer ----------

def _to_int(val: Any) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0


def _to_float(val: Any) -> float:
    try:
        return float(str(val).replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def _parse_mip_to_minutes(mip: Any) -> float:
    """Wandelt '807:39' in Minuten-Float um."""
    if isinstance(mip, (int, float)):
        return float(mip)
    if not isinstance(mip, str):
        return 0.0

    mip = mip.strip()
    if not mip or ":" not in mip:
        try:
            return float(mip)
        except ValueError:
            return 0.0

    try:
        mins_s, secs_s = mip.split(":")
        mins = int(mins_s)
        secs = int(secs_s)
        return mins + secs / 60.0
    except Exception:
        return 0.0


# ---------- Skater-Normalisierung ----------

def normalize_skaters(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Bringt die DEL2-Skater-Tabelle auf das Baseline-Schema.

    Erwartete Spalten (Stand jetzt):
    ['#', 'Spieler', 'Club', 'Nat', 'Nr', 'Pos', 'G/C',
     'GP', 'T', 'A', 'P', 'P/GP', '+/-', 'PPT', 'SHT',
     'FOW', 'FOL', 'FOW%', 'PIM']
    """
    if "Spieler" not in df.columns:
        raise ValueError("Spalte 'Spieler' nicht gefunden – Struktur der DEL2-Skater-Tabelle hat sich geändert.")

    records: List[Dict[str, Any]] = []

    for _, row in df.iterrows():
        name_raw = str(row["Spieler"]).strip()
        if not name_raw or name_raw.lower() == "nan":
            continue

        team = str(row.get("Club", "")).strip()
        nation = str(row.get("Nat", "")).strip()

        number = None
        if "Nr" in df.columns:
            try:
                num_val = row.get("Nr")
                number = int(num_val) if pd.notna(num_val) else None
            except (TypeError, ValueError):
                number = None

        pos_raw = str(row.get("Pos", "")).strip().upper()  # FO / DE / GK etc.

        # --- Goalies, die fälschlich in der Skaterliste stehen, direkt überspringen ---
        # Alles was klar nach Goalie aussieht, ignorieren wir hier.
        if pos_raw in ("G", "GK", "T", "TOR", "TORH", "TORHÜTER"):
            # Dieser Spieler kommt sauber aus der DEL2_GOALIES_URL mit Stats,
            # also hier nicht als Skater aufnehmen.
            continue

        # Vereinheitlichte Position für Skater:
        if pos_raw in ("DE", "D", "V", "DE (U21)"):
            pos_group = "D"
        else:
            pos_group = "F"


        gp = _to_int(row.get("GP"))
        goals = _to_int(row.get("T"))
        assists = _to_int(row.get("A"))
        points = _to_int(row.get("P"))
        points_per_game = (points / gp) if gp > 0 else 0.0

        plus_minus = _to_int(row.get("+/-"))
        pp_goals = _to_int(row.get("PPT"))
        sh_goals = _to_int(row.get("SHT"))
        pim = _to_int(row.get("PIM"))

        fo_won = _to_int(row.get("FOW"))
        fo_lost = _to_int(row.get("FOL"))
        fo_pct = _to_float(row.get("FOW%"))

        rec: Dict[str, Any] = {
            "league": "DEL2",
            "type": "skater",
            "team_code": team,
            "name_real": name_raw,
            "number": number,
            "nation": nation,
            "position_raw": pos_raw,
            "position_group": pos_group,  # F oder D

            "gp": gp,
            "goals": goals,
            "assists": assists,
            "points": points,
            "points_per_game": points_per_game,
            "plus_minus": plus_minus,
            "pp_goals": pp_goals,
            "sh_goals": sh_goals,
            "pim": pim,
            "fo_won": fo_won,
            "fo_lost": fo_lost,
            "fo_pct": fo_pct,
        }
        records.append(rec)

    return records


# ---------- Goalie-Normalisierung ----------

def normalize_goalies(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Bringt die DEL2-Goalie-Tabelle auf das Baseline-Schema.

    Erwartete Spalten (Stand jetzt):
    ['#', 'Spieler', 'Club', 'Nat', 'Nr', 'POS', 'G/C',
     'G', 'GP', 'MIP', 'W', 'L', 'SO', 'GA', 'GAA', 'SOG', 'SV', 'SV%']
    """
    if "Spieler" not in df.columns:
        raise ValueError("Spalte 'Spieler' nicht gefunden – Struktur der DEL2-Goalie-Tabelle hat sich geändert.")

    records: List[Dict[str, Any]] = []

    for _, row in df.iterrows():
        name_raw = str(row["Spieler"]).strip()
        if not name_raw or name_raw.lower() == "nan":
            continue

        team = str(row.get("Club", "")).strip()
        nation = str(row.get("Nat", "")).strip()

        number = None
        if "Nr" in df.columns:
            try:
                num_val = row.get("Nr")
                number = int(num_val) if pd.notna(num_val) else None
            except (TypeError, ValueError):
                number = None

        pos_raw = str(row.get("POS", "")).strip().upper()  # GK
        pos_group = "G"

        gp = _to_int(row.get("GP"))
        minutes = _parse_mip_to_minutes(row.get("MIP"))
        wins = _to_int(row.get("W"))
        losses = _to_int(row.get("L"))
        shutouts = _to_int(row.get("SO"))
        goals_against = _to_int(row.get("GA"))
        gaa = _to_float(row.get("GAA"))
        saves = _to_int(row.get("SV"))
        sv_pct = _to_float(row.get("SV%"))

        # SOG = Schüsse gegen Goalie → DEL2 liefert 'SOG'
        shots_against = _to_int(row.get("SOG"))

        rec: Dict[str, Any] = {
            "league": "DEL2",
            "type": "goalie",
            "team_code": team,
            "name_real": name_raw,
            "number": number,
            "nation": nation,
            "position_raw": pos_raw,
            "position_group": pos_group,  # G

            "gp": gp,
            "minutes": minutes,
            "wins": wins,
            "losses": losses,
            "shutouts": shutouts,
            "goals_against": goals_against,
            "gaa": gaa,
            "shots_against": shots_against,
            "saves": saves,
            "sv_pct": sv_pct,
        }
        records.append(rec)

    return records


# ---------- Main ----------

def main() -> None:
    print("=== DEL2 Skater laden & normalisieren ===")
    skater_df = load_table(DEL2_SKATERS_URL)
    skater_records = normalize_skaters(skater_df)
    print(f"✅ {len(skater_records)} Skater normalisiert")

    print("\n=== DEL2 Goalies laden & normalisieren ===")
    goalie_df = load_table(DEL2_GOALIES_URL)
    goalie_records = normalize_goalies(goalie_df)
    print(f"✅ {len(goalie_records)} Goalies normalisiert")

    all_players = skater_records + goalie_records

    OUTFILE.parent.mkdir(parents=True, exist_ok=True)
    with OUTFILE.open("w", encoding="utf-8") as f:
        json.dump(all_players, f, indent=2, ensure_ascii=False)

    print(f"\n📦 JSON gespeichert → {OUTFILE.resolve()}")
    print("Beispiel-Einträge:")
    for rec in all_players[:5]:
        print(" -", rec["type"], rec["name_real"], rec["team_code"], "POS:", rec["position_group"])


if __name__ == "__main__":
    main()
