"""
dedupe_players_by_games.py

Bereinigt doppelte Spieler in all_players_baseline.json, wenn sie in mehreren Teams/Ligen auftauchen.

Logik:
- Gruppiert nach Spielername (name oder name_real).
- Wenn ein Spieler mehrfach vorkommt:
    -> wähle den Eintrag mit den meisten gespielten Spielen (gp).
    -> Bei Gleichstand: bevorzuge DEL vor DEL2.
- Schreibt das Ergebnis zurück nach data/all_players_baseline.json.

Anpassung:
- GAME_KEY ist hier auf "gp" gesetzt (aus deinen DEL/DEL2-Stats).
"""

from __future__ import annotations

import json
from pathlib import Path
from collections import defaultdict
from typing import Any, Dict, List

DATA_DIR = Path("data")
IN_FILE = DATA_DIR / "all_players_baseline.json"
OUT_FILE = IN_FILE  # überschreibt dieselbe Datei

# Feldname für gespielte Spiele in deinen Stats
GAME_KEY = "gp"


def _to_int(val: Any) -> int:
    try:
        if val is None:
            return 0
        return int(val)
    except (TypeError, ValueError):
        return 0


def _league_priority(player: Dict[str, Any]) -> int:
    """
    Tie-Breaker, wenn zwei Einträge gleich viele Spiele haben.
    Höherer Wert = höher priorisiert.

    Aktuell:
    - DEL2 -> 1
    - DEL  -> 2
    - sonst -> 0
    """
    league = (player.get("league") or player.get("Liga") or "").upper()
    if "DEL2" in league:
        return 1
    if "DEL" in league:
        return 2
    return 0


def _get_name_key(player: Dict[str, Any]) -> str:
    """
    Holt den Namen, nach dem gruppiert wird.
    Nutzt bevorzugt:
    - "name"
    - dann "name_real"
    - dann "Name"
    """
    name = (
        player.get("name")
        or player.get("name_real")
        or player.get("Name")
    )
    if not name:
        # Fallback, damit keine Einträge verloren gehen
        return f"__no_name___{id(player)}"
    return str(name)


def _get_team_label(player: Dict[str, Any]) -> str:
    return (
        player.get("team_name")
        or player.get("team")
        or player.get("Team")
        or player.get("team_code")
        or "?"
    )


def main() -> None:
    if not IN_FILE.exists():
        raise SystemExit(f"Input-Datei nicht gefunden: {IN_FILE}")

    with IN_FILE.open("r", encoding="utf-8") as f:
        players_raw = json.load(f)

    # Sicherstellen, dass wir eine Liste haben
    if isinstance(players_raw, dict):
        # Falls du irgendwann ein Wrapper-Objekt baust,
        # musst du hier ggf. anpassen, z.B. players_raw["players"]
        raise SystemExit(
            "all_players_baseline.json ist kein List-JSON. "
            "Passe dedupe_players_by_games.py an (Wrapper-Objekt?)."
        )

    players: List[Dict[str, Any]] = players_raw

    # Gruppiere Spieler nach Name
    buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for p in players:
        key = _get_name_key(p)
        buckets[key].append(p)

    deduped: List[Dict[str, Any]] = []
    merged_count = 0
    total_dupe_groups = 0

    for name_key, entries in buckets.items():
        if len(entries) == 1:
            deduped.append(entries[0])
            continue

        total_dupe_groups += 1

        # Wähle den "besten" Eintrag:
        # 1) Meiste Spiele (gp)
        # 2) Bevorzugte Liga (DEL vor DEL2)
        def sort_key(e: Dict[str, Any]):
            games = _to_int(e.get(GAME_KEY, 0))
            league_prio = _league_priority(e)
            return (games, league_prio)

        best = max(entries, key=sort_key)

        # Logging für Debug / Transparenz
        real_name = (
            entries[0].get("name")
            or entries[0].get("name_real")
            or entries[0].get("Name")
            or name_key
        )
        print(f"[DEDUP] Spieler '{real_name}' kommt {len(entries)}x vor:")
        for e in entries:
            team = _get_team_label(e)
            league = (e.get("league") or e.get("Liga") or "?").upper()
            games = _to_int(e.get(GAME_KEY, 0))
            marker = "  -> KEEP" if e is best else "     drop"
            print(f"   {marker} {team:25s} | {league:5s} | Spiele={games}")

        deduped.append(best)
        merged_count += len(entries) - 1

    with OUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(deduped, f, ensure_ascii=False, indent=2)

    print()
    print(f"Fertig. Doppelte Spieler-Gruppen: {total_dupe_groups}")
    print(f"Insgesamt entfernte Duplikate:    {merged_count}")
    print(f"Übrig gebliebene Spieler:          {len(deduped)}")


if __name__ == "__main__":
    main()
