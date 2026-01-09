"""
Example Output & Use Cases for Narrative Engine

This document shows real-world examples of how narratives are generated and used.
"""

# ============================================================
# EXAMPLE 1: Shootout Drama
# ============================================================

Match Input:
  {
    "home": "Munich Eagles",
    "away": "Berlin Wolves",
    "g_home": 2,
    "g_away": 2,
    "overtime": True,
    "shootout": True
  }

Form Data:
  Munich Eagles: ["W", "W", "L", "L", "W"] → form_score = +1
  Berlin Wolves: ["W", "W", "W", "W", "W"] → form_score = +5

Classification:
  1. Check shootout → YES → "SO_DRAMA"

Generated Narrative:
  key: "Munich Eagles-Berlin Wolves"
  line1: "Munich Eagles siegt im Shootout gegen Berlin Wolves."
  type: "SO_DRAMA"
  meta: {
    "margin": 0,
    "total_goals": 4,
    "form_diff": 4,
    "home_form": 1,
    "away_form": 5,
    "winner": "Munich Eagles",
    "loser": "Berlin Wolves",
    "score": "2:2",
    "overtime": true,
    "shootout": true
  }


# ============================================================
# EXAMPLE 2: Shutout - Dominant Defense
# ============================================================

Match Input:
  {
    "home": "Hamburg Sharks",
    "away": "Frankfurt Phoenix",
    "g_home": 3,
    "g_away": 0,
    "overtime": False,
    "shootout": False
  }

Form Data:
  Hamburg Sharks: ["W", "W", "W", "W", "W"] → form_score = +5
  Frankfurt Phoenix: ["L", "L", "L", "L", "L"] → form_score = -5

Classification:
  1. Check shootout → NO
  2. Check overtime → NO
  3. Check loser_goals == 0 → YES → "SHUTOUT"

Generated Narrative:
  key: "Hamburg Sharks-Frankfurt Phoenix"
  line1: "Hamburg Sharks shutout Frankfurt Phoenix mit voller Kontrolle."
  type: "SHUTOUT"
  meta: {
    "margin": 3,
    "total_goals": 3,
    "form_diff": 10,
    "home_form": 5,
    "away_form": -5,
    "winner": "Hamburg Sharks",
    "loser": "Frankfurt Phoenix",
    "score": "3:0",
    "overtime": false,
    "shootout": false
  }


# ============================================================
# EXAMPLE 3: Upset - Bad Form Team Wins
# ============================================================

Match Input:
  {
    "home": "Stuttgart Strikers",
    "away": "Cologne Kings",
    "g_home": 3,
    "g_away": 1,
    "overtime": False,
    "shootout": False
  }

Form Data:
  Stuttgart Strikers: ["L", "L", "L", "L", "L"] → form_score = -5
  Cologne Kings: ["W", "W", "W", "W", "W"] → form_score = +5

Classification:
  1. Check shootout → NO
  2. Check overtime → NO
  3. Check loser_goals == 0 → NO (1 goal allowed)
  4. Check margin >= 5 → NO (margin = 2)
  5. Check margin >= 3 → YES, but form_diff = -5-5 = -10 <= -3 → "UPSET"
     (Actually, winner form = -5, loser form = +5, diff = -10)
     (Wait, recalculating: margin = 3-1 = 2, which is not >= 3)
     (So skip to form_diff check: -5 - (+5) = -10 <= -3 → "UPSET")

Generated Narrative:
  key: "Stuttgart Strikers-Cologne Kings"
  line1: "Stuttgart Strikers überrascht Cologne Kings mit Sieg."
  type: "UPSET"
  meta: {
    "margin": 2,
    "total_goals": 4,
    "form_diff": 10,
    "home_form": -5,
    "away_form": 5,
    "winner": "Stuttgart Strikers",
    "loser": "Cologne Kings",
    "score": "3:1",
    "overtime": false,
    "shootout": false
  }


# ============================================================
# EXAMPLE 4: Grind Win - Tight 1-Goal Battle
# ============================================================

Match Input:
  {
    "home": "Dusseldorf Dragons",
    "away": "Dresden Titans",
    "g_home": 2,
    "g_away": 1,
    "overtime": False,
    "shootout": False
  }

Form Data:
  Dusseldorf Dragons: ["W", "W", "L", "W", "L"] → form_score = +1
  Dresden Titans: ["L", "W", "W", "W", "W"] → form_score = +3

Classification:
  1. Check shootout → NO
  2. Check overtime → NO
  3. Check loser_goals == 0 → NO
  4. Check margin >= 5 → NO
  5. Check margin >= 3 → NO
  6. Check form_diff <= -3 → NO (form_diff = 1-3 = -2, not <= -3)
  7. Check margin == 1 → YES → "GRIND_WIN"

Generated Narrative:
  key: "Dusseldorf Dragons-Dresden Titans"
  line1: "Dusseldorf Dragons siegt knapp gegen Dresden Titans nach hartem Kampf."
  type: "GRIND_WIN"
  meta: {
    "margin": 1,
    "total_goals": 3,
    "form_diff": 2,
    "home_form": 1,
    "away_form": 3,
    "winner": "Dusseldorf Dragons",
    "loser": "Dresden Titans",
    "score": "2:1",
    "overtime": false,
    "shootout": false
  }


# ============================================================
# EXAMPLE 5: Track Meet - Goal Fest
# ============================================================

Match Input:
  {
    "home": "Augsburg Aviators",
    "away": "Mannheim Meteors",
    "g_home": 5,
    "g_away": 3,
    "overtime": False,
    "shootout": False
  }

Form Data:
  Augsburg Aviators: ["W", "W", "W", "L", "W"] → form_score = +3
  Mannheim Meteors: ["W", "L", "W", "W", "W"] → form_score = +3

Classification:
  1. Check shootout → NO
  2. Check overtime → NO
  3. Check loser_goals == 0 → NO
  4. Check margin >= 5 → NO (margin = 2)
  5. Check margin >= 3 → NO
  6. Check form_diff <= -3 → NO
  7. Check margin == 1 → NO
  8. Check total_goals >= 7 → NO (total = 8... wait, that's >= 7!) → "TRACK_MEET"

Generated Narrative:
  key: "Augsburg Aviators-Mannheim Meteors"
  line1: "Augsburg Aviators und Mannheim Meteors liefern sich ein Tor-Feuerwerk."
  type: "TRACK_MEET"
  meta: {
    "margin": 2,
    "total_goals": 8,
    "form_diff": 0,
    "home_form": 3,
    "away_form": 3,
    "winner": "Augsburg Aviators",
    "loser": "Mannheim Meteors",
    "score": "5:3",
    "overtime": false,
    "shootout": false
  }


# ============================================================
# EXAMPLE 6: Domination - Blowout
# ============================================================

Match Input:
  {
    "home": "Koblenz Knights",
    "away": "Rostock Rays",
    "g_home": 6,
    "g_away": 1,
    "overtime": False,
    "shootout": False
  }

Form Data:
  Koblenz Knights: ["W", "W", "W", "W", "W"] → form_score = +5
  Rostock Rays: ["L", "L", "L", "L", "L"] → form_score = -5

Classification:
  1. Check shootout → NO
  2. Check overtime → NO
  3. Check loser_goals == 0 → NO (1 goal allowed)
  4. Check margin >= 5 → YES (margin = 5) → "DOMINATION"

Generated Narrative:
  key: "Koblenz Knights-Rostock Rays"
  line1: "Koblenz Knights dominiert Rostock Rays mit großem Vorsprung."
  type: "DOMINATION"
  meta: {
    "margin": 5,
    "total_goals": 7,
    "form_diff": 10,
    "home_form": 5,
    "away_form": -5,
    "winner": "Koblenz Knights",
    "loser": "Rostock Rays",
    "score": "6:1",
    "overtime": false,
    "shootout": false
  }


# ============================================================
# USAGE IN RENDERER / UI
# ============================================================

Example UI Integration (pseudo-code):

```python
import json
from pathlib import Path

class MatchdayRenderer:
    def load_narratives(self, season: int, matchday: int) -> dict:
        path = Path(f"spieltage/saison_{season:02d}/narratives_{matchday:02d}.json")
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}
    
    def render_match_graphic(self, season: int, matchday: int, home: str, away: str):
        narratives = self.load_narratives(season, matchday)
        key = f"{home}-{away}"
        narrative = narratives.get(key, {})
        
        # Get display text
        line1 = narrative.get("line1", f"{home} vs {away}")  # fallback
        narrative_type = narrative.get("type", "FALLBACK")
        
        # Use for display
        print(f"Match: {home} vs {away}")
        print(f"Narrative: {line1}")
        print(f"Type: {narrative_type}")
        
        # Optional: Use metadata for styling
        meta = narrative.get("meta", {})
        if meta.get("shootout"):
            print("🔥 Penalty Shootout Decider!")
        elif meta.get("overtime"):
            print("⚡ Overtime Drama!")
        elif narrative_type == "SHUTOUT":
            print("🛡️ Defensive Masterclass")
        elif narrative_type == "DOMINATION":
            print("👑 Complete Domination")
        elif narrative_type == "UPSET":
            print("🌟 Stunning Upset!")
```

Output:
```
Match: Munich Eagles vs Berlin Wolves
Narrative: Munich Eagles siegt im Shootout gegen Berlin Wolves.
Type: SO_DRAMA
🔥 Penalty Shootout Decider!
```


# ============================================================
# DETERMINISTIC BEHAVIOR
# ============================================================

The same match always produces the same narrative:

Run 1 (Saison 5, Spieltag 3):
  seed_str = "5-3-Hamburg Sharks-Frankfurt Phoenix-3-0"
  template selected = TEMPLATES["SHUTOUT"][seed_hash % 5]
  Result: "Hamburg Sharks shutout Frankfurt Phoenix mit voller Kontrolle."

Run 2 (Same match, re-simulated):
  seed_str = "5-3-Hamburg Sharks-Frankfurt Phoenix-3-0"  ← SAME SEED
  template selected = TEMPLATES["SHUTOUT"][seed_hash % 5]  ← SAME INDEX
  Result: "Hamburg Sharks shutout Frankfurt Phoenix mit voller Kontrolle."  ← IDENTICAL

This ensures:
- Graphics are reproducible
- Narrative descriptions don't change between runs
- History is consistent even if simulation is re-run
