import json
from pathlib import Path
from collections import defaultdict

def debug_konsistenzpruefung(spieler_name, team_name, season=1, max_spieltag=4):
    print(f"[DEBUG KONSISTENZPRÜFUNG] Spieler: {spieler_name} (Team: {team_name})\n")
    for spieltag in range(1, max_spieltag+1):
        # 1. Team-Ergebnis
        replay_dir = Path(f"replays/saison_{season:02}/spieltag_{spieltag:02}")
        match_file = None
        for f in replay_dir.glob(f"{team_name}-*.json"):
            match_file = f
            break
        if not match_file:
            for f in replay_dir.glob(f"*-{team_name}.json"):
                match_file = f
                break
        if not match_file:
            print(f"Spieltag {spieltag}: Kein Replay für {team_name} gefunden!")
            continue
        with open(match_file, "r", encoding="utf-8") as f:
            replay = json.load(f)
        home = replay["home"]["name"]
        away = replay["away"]["name"]
        score = f"{replay['home']['score']} : {replay['away']['score']}"
        print(f"Spieltag {spieltag}: {home} vs {away}  Ergebnis: {score}")
        # 2. Replay-Events für Spieler
        goals = 0
        assists = 0
        goal_minutes = []
        assist_minutes = []
        for event in replay.get("events", []):
            if event.get("type") == "goal" and event.get("result") == "goal":
                if event.get("player_main") == spieler_name:
                    goals += 1
                    goal_minutes.append(event.get("t"))
                if event.get("player_secondary") == spieler_name:
                    assists += 1
                    assist_minutes.append(event.get("t"))
        print(f"  Replay-Events: Tore: {goals} (Minuten: {goal_minutes}), Assists: {assists} (Minuten: {assist_minutes})")
        # 3. Player Stats aus JSON
        stats_path = Path(f"stats/saison_{season:02}/league/player_stats_after_spieltag_{spieltag:02}.json")
        goals_stats = assists_stats = pts_stats = None
        if stats_path.exists():
            with open(stats_path, "r", encoding="utf-8") as f:
                stats = json.load(f)
            if isinstance(stats, dict) and "players" in stats:
                stats = stats["players"]
            for entry in stats:
                if not isinstance(entry, dict):
                    continue
                if entry.get("name") == spieler_name or entry.get("Player") == spieler_name:
                    goals_stats = entry.get("g") or entry.get("Goals") or 0
                    assists_stats = entry.get("a") or entry.get("Assists") or 0
                    pts_stats = entry.get("pts") or entry.get("Points") or 0
                    break
        print(f"  Player Stats: Goals: {goals_stats}, Assists: {assists_stats}, Points: {pts_stats}")
        # 4. Vergleich
        konsistent = (goals == (goals_stats or 0)) and (assists == (assists_stats or 0))
        print(f"  → Konsistent: {'JA' if konsistent else 'NEIN'}\n")

if __name__ == "__main__":
    # Beispiel: Spieler und Team anpassen!
    debug_konsistenzpruefung("Owene Headricik", "Nürnberg Eistiger", season=1, max_spieltag=8)
