"""
normalize_names.py

Ziel:
- In data/all_players_baseline.json stehen DEL-Spieler teils als "Nachname, Vorname".
- Wir normalisieren ALLE Namen auf "Vorname Nachname".

Pipeline:
    del2_fetch.py
    del_fetch.py
    merge_players_baseline.py
    normalize_names.py   <-- dieses Script
    build_ratings.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

BASELINE_FILE = Path("data") / "all_players_baseline.json"


def _normalize_name(name: str) -> str:
    """
    "Barber, Riley"  -> "Riley Barber"
    "Matsumoto, Jonathan" -> "Jonathan Matsumoto"
    "Riley Barber"  -> bleibt unverändert
    Leere oder kaputte Strings -> unverändert zurückgeben.
    """
    if not isinstance(name, str):
        return name

    s = name.strip()
    if not s:
        return s

    # Wenn kein Komma drin ist, lassen wir es wie es ist:
    if "," not in s:
        return " ".join(s.split())  # nur mehrfach-Spaces glätten

    parts = [p.strip() for p in s.split(",")]
    if len(parts) != 2:
        # irgendwas Komisches wie "Nachname, Vorname, Zusatztitel"
        return " ".join(s.split())

    last, first = parts[0], parts[1]
    if not first or not last:
        return " ".join(s.split())

    return f"{first} {last}"


def main() -> None:
    if not BASELINE_FILE.exists():
        print(f"❌ Datei nicht gefunden: {BASELINE_FILE}")
        return

    data: List[Dict[str, Any]] = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))

    changed = 0
    total = 0

    for rec in data:
        total += 1

        # Name-Feld: in unserer Pipeline heißt es name_real,
        # fallback auf name_raw falls nötig
        name_real = rec.get("name_real")
        name_raw = rec.get("name_raw")

        # Priorität: wenn name_real da ist, normalisieren wir das;
        # sonst versuchen wir name_raw und schreiben nach name_real.
        if isinstance(name_real, str) and name_real.strip():
            new = _normalize_name(name_real)
            if new != name_real:
                rec["name_real"] = new
                changed += 1
        elif isinstance(name_raw, str) and name_raw.strip():
            new = _normalize_name(name_raw)
            if new != name_raw:
                rec["name_real"] = new
                changed += 1

    BASELINE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"✅ Namen normalisiert in {BASELINE_FILE}")
    print(f"   Gesamt Datensätze: {total}")
    print(f"   Geänderte Namen:   {changed}")


if __name__ == "__main__":
    main()
