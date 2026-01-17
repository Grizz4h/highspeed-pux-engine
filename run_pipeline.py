"""
run_pipeline.py

Führt die komplette Daten-Pipeline für den LigaGenerator in der richtigen Reihenfolge aus:

1. del2_fetch.py
   → schreibt z.B. DEL2-JSONs (Goalies/Skater), je nach Implementierung
2. del_fetch.py
   → schreibt DEL-JSONs
3. merge_players_baseline.py
   → erzeugt data/all_players_baseline.json
4. normalize_names.py
   → bereinigt/normalisiert Namen in all_players_baseline.json
5. build_ratings.py
   → erzeugt data/players_rated.json
6. build_realeTeams_from_ratings.py
   → liest:
        - data/players_rated.json
        - team_mapping.json
        - mapping_player_names.json
     und schreibt:
        - realeTeams_live.py

Voraussetzung:
- Alle oben genannten Skripte liegen im selben Verzeichnis wie dieses Skript.
"""

from __future__ import annotations

import subprocess
import sys
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
REALETEAMS_FILE = BASE_DIR / "realeTeams_live.py"

# Falls du später mal die Reihenfolge ändern willst, musst du nur diese Liste anfassen.
PIPELINE_STEPS = [
    ("Players.json regenerieren", "regenerate_players.py"),
    ("DEL2-Fetch (Goalies/Skater etc.)", "del2_fetch.py"),
    ("DEL-Fetch (Goalies/Skater etc.)", "del_fetch.py"),
    ("Merge Baseline (DEL + DEL2)", "merge_players_baseline.py"),
    ("Namen normalisieren", "normalize_names.py"),
    ("Duplikate nach Spiele-Anzahl bereinigen", "dedupe_players_by_games.py"),
    ("Ratings berechnen", "build_ratings.py"),
    ("Fake-Namen generieren", "generate_fake_names.py"),
    ("Reale Teams aus Ratings bauen", "build_realeTeams_from_ratings.py"),
]


def run_step(description: str, script_name: str) -> None:
    """Einen einzelnen Pipeline-Schritt ausführen."""
    script_path = BASE_DIR / script_name

    if not script_path.exists():
        print(f"❌ Skript nicht gefunden: {script_name}")
        sys.exit(1)

    print(f"\n=== Schritt: {description} ===")
    print(f"➡️  Starte: {script_name}")

    # Environment mit UTF-8-IO erzwingen
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(BASE_DIR),
        env=env,
    )

    if result.returncode != 0:
        print(f"❌ Schritt fehlgeschlagen: {script_name} (Exit-Code {result.returncode})")
        sys.exit(result.returncode)

    print(f"✅ Fertig: {description}")


def fix_realeTeams_nulls() -> None:
    """
    Nach build_realeTeams_from_ratings.py:
    Ersetze 'null' (aus JSON) durch Python 'None' in realeTeams_live.py.
    """
    if not REALETEAMS_FILE.exists():
        print(f"\n[WARN] {REALETEAMS_FILE} nicht gefunden – überspringe null→None-Fix.")
        return

    text = REALETEAMS_FILE.read_text(encoding="utf-8")

    if "null" not in text:
        print("\n In realeTeams_live.py wurden keine 'null'-Tokens gefunden – nichts zu tun.")
        return

    new_text = (
        text
        .replace(": null", ": None")
        .replace(":  null", ": None")
        .replace(":null", ": None")
        .replace("= null", "= None")
        .replace("=  null", "= None")
        .replace("=null", "= None")
    )

    # Fallback, falls doch noch nackte "null" übrig bleiben
    if " null" in new_text or "(null" in new_text:
        new_text = new_text.replace("null", "None")

    REALETEAMS_FILE.write_text(new_text, encoding="utf-8")
    print("\n  realeTeams_live.py angepasst: 'null' → 'None'.")

def main() -> None:
    print("Starte LigaGenerator-Pipeline...\n")

    print(f"Arbeitsverzeichnis: {BASE_DIR}")

    for desc, script in PIPELINE_STEPS:
        run_step(desc, script)

    # NEU: null → None Fix nach dem Bau von realeTeams_live.py
    fix_realeTeams_nulls()

    print("\n Pipeline komplett durchgelaufen.")
    print("   → Wichtige Outputs u.a.:")
    print("      - data/all_players_baseline.json")
    print("      - data/players_rated.json")
    print("      - realeTeams_live.py (null→None bereinigt)")



if __name__ == "__main__":
    main()
