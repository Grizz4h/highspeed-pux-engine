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
from pathlib import Path


# Falls du später mal die Reihenfolge ändern willst, musst du nur diese Liste anfassen.
PIPELINE_STEPS = [
    ("DEL2-Fetch (Goalies/Skater etc.)", "del2_fetch.py"),
    ("DEL-Fetch (Goalies/Skater etc.)", "del_fetch.py"),
    ("Merge Baseline (DEL + DEL2)", "merge_players_baseline.py"),
    ("Namen normalisieren", "normalize_names.py"),
    ("Ratings berechnen", "build_ratings.py"),
    ("Fake-Namen generieren", "generate_fake_names.py"),
    ("Reale Teams aus Ratings bauen", "build_realeTeams_from_ratings.py"),
]


def run_step(description: str, script_name: str) -> None:
    """Einen einzelnen Pipeline-Schritt ausführen."""
    script_path = Path(script_name)

    if not script_path.exists():
        print(f"❌ Skript nicht gefunden: {script_name}")
        sys.exit(1)

    print(f"\n=== Schritt: {description} ===")
    print(f"➡️  Starte: {script_name}")

    # Nutzt denselben Python-Interpreter, mit dem run_pipeline.py gestartet wurde
    result = subprocess.run([sys.executable, str(script_path)])

    if result.returncode != 0:
        print(f"❌ Schritt fehlgeschlagen: {script_name} (Exit-Code {result.returncode})")
        sys.exit(result.returncode)

    print(f"✅ Fertig: {description}")


def main() -> None:
    print("🚦 Starte LigaGenerator-Pipeline...\n")

    base_dir = Path(__file__).resolve().parent
    print(f"Arbeitsverzeichnis: {base_dir}")

    for desc, script in PIPELINE_STEPS:
        run_step(desc, script)

    print("\n🏁 Pipeline komplett durchgelaufen.")
    print("   → Wichtige Outputs u.a.:")
    print("      - data/all_players_baseline.json")
    print("      - data/players_rated.json")
    print("      - realeTeams_live.py")


if __name__ == "__main__":
    main()
