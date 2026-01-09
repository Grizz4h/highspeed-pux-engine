# Narrative Engine Integration Guide

## Overview
The narrative engine generates deterministic, one-liner match narratives (≤75 characters) for matchday result graphics. It's integrated into the LigaGenerator simulation pipeline and runs automatically after each matchday simulation.

## Components

### 1. **narrative_engine.py** (Main Module)
Located in `/opt/highspeed/pux-engine/narrative_engine.py`

#### Key Functions:

**`form_score(last5: List[str]) -> int`**
- Calculates team form from recent results
- W = +1, L = -1, T/D = 0
- Example: `["W", "W", "L", "W", "W"]` → +3

**`classify_narrative(match, home_form, away_form) -> str`**
- Classifies match into one of 10 narrative types based on priorities:
  1. `SO_DRAMA` - Shootout decided
  2. `OT_DRAMA` - Overtime decided
  3. `SHUTOUT` - Loser scored 0 goals
  4. `DOMINATION` - Margin ≥ 5 goals
  5. `STATEMENT_WIN` - Margin ≥ 3 (unless low form diff)
  6. `UPSET` - Low-form team wins against high-form team
  7. `GRIND_WIN` - Margin = 1 goal (tight win)
  8. `TRACK_MEET` - Total goals ≥ 7 (offensive showcase)
  9. `LOW_SCORING` - Total goals ≤ 3 (defensive grind)
  10. `FALLBACK` - Default catch-all

**`pick_template(narrative_type: str, seed_str: str) -> str`**
- Deterministically selects a template string from the TEMPLATES dict
- Hash-based selection ensures same match always gets same narrative
- Example seed: `"saison-01-05-Team_A-Team_B-3-1"`

**`build_narratives_for_matchday(spieltag_json, latest_json, season) -> Dict`**
- Main entry point for narrative generation
- Processes all matches in a spieltag
- Returns: `{ "home_team-away_team": { "line1": "...", "type": "...", "meta": {...} } }`

**`write_narratives_json(narratives, output_path) -> None`**
- Writes narratives to JSON file with validation
- Ensures UTF-8 encoding and proper formatting
- Validates all line1 lengths ≤ 75 chars

### 2. **TEMPLATES Dictionary**
Located in `narrative_engine.py` (lines ~100-180)

Each narrative type has 5 template variations:
```python
TEMPLATES = {
    "SO_DRAMA": [
        "{Winner} siegt im Shootout gegen {Loser}.",
        "{Winner} entscheidet das Penaltyschießen für sich.",
        # ... 3 more templates
    ],
    # ... 9 more types
}
```

Templates use `{Winner}` and `{Loser}` placeholders for team names.

## Integration into LigageneratorV2.py

### Import (Line ~15)
```python
from narrative_engine import build_narratives_for_matchday, write_narratives_json
```

### Call Location (After `save_spieltag_json()`, around line 1847)
```python
save_spieltag_json(...)

# Generate narratives for the matchday
try:
    spieltag_json_path = SPIELTAG_DIR / season_folder(season) / f"spieltag_{spieltag:02}.json"
    latest_json_path = STATS_DIR / season_folder(season) / "league" / "latest.json"
    narratives_json_path = SPIELTAG_DIR / season_folder(season) / f"narratives_{spieltag:02}.json"
    
    # Load the spieltag JSON we just saved
    with open(spieltag_json_path, "r", encoding="utf-8") as f:
        spieltag_json = json.load(f)
    
    # Load latest.json (exists after save_league_stats_snapshot)
    latest_json = None
    if latest_json_path.exists():
        with open(latest_json_path, "r", encoding="utf-8") as f:
            latest_json = json.load(f)
    
    if latest_json:
        # Convert latest.json teams to tabelle format
        tabelle_nord = []
        tabelle_sued = []
        for team_info in latest_json.get("teams", []):
            team_dict = {
                "Team": team_info.get("team", ""),
                "last5": team_info.get("last5", []),
            }
            if team_info.get("conference") == "Nord":
                tabelle_nord.append(team_dict)
            else:
                tabelle_sued.append(team_dict)
        
        latest_for_narrative = {
            "tabelle_nord": tabelle_nord,
            "tabelle_sued": tabelle_sued,
        }
        
        narratives = build_narratives_for_matchday(
            spieltag_json,
            latest_for_narrative,
            season=season,
        )
        write_narratives_json(narratives, narratives_json_path)
        logging.info(f"Narratives written to {narratives_json_path}")
except Exception as e:
    logging.error(f"Narrative generation failed: {e}", exc_info=True)
    # Continue execution even if narrative generation fails

save_replay_json(season, spieltag, replay_matches)
```

## Output Structure

### narratives_XX.json
```json
{
  "Team A-Team B": {
    "line1": "Team A gewinnt gegen Team B.",
    "type": "FALLBACK",
    "meta": {
      "margin": 2,
      "total_goals": 5,
      "form_diff": 2,
      "home_form": 1,
      "away_form": -1,
      "winner": "Team A",
      "loser": "Team B",
      "score": "3:1",
      "overtime": false,
      "shootout": false
    }
  },
  "Team C-Team D": {
    "line1": "Spannung bis zum Schluss: Team C gewinnt in der Verlängerung.",
    "type": "OT_DRAMA",
    "meta": { ... }
  }
}
```

## File Locations

| File | Purpose |
|------|---------|
| `spieltage/saison_XX/spieltag_YY.json` | Match results & standings (created by save_spieltag_json) |
| `stats/saison_XX/league/latest.json` | Team form & standings (created by save_league_stats_snapshot) |
| `spieltage/saison_XX/narratives_YY.json` | **NEW:** Generated narratives (created by narrative engine) |

## Testing

Run the included test suite:
```bash
python test_narrative_engine.py
```

Expected output:
```
✅ form_score tests passed
✅ SO_DRAMA classification passed
✅ OT_DRAMA classification passed
... (9 more tests)
✅ All tests passed!
```

## Data Flow

```
LigaGenerator Simulation
        ↓
[Matches played, results calculated]
        ↓
save_spieltag_json(results, teams, stats)
  → Writes: spieltag_XX.json
        ↓
save_league_stats_snapshot(stats)
  → Writes: latest.json (with last5 for each team)
        ↓
[NEW] Narrative Generation
  → load spieltag_XX.json
  → load latest.json
  → For each match:
    • Calculate form_score(home_last5) and form_score(away_last5)
    • Classify narrative type based on priorities
    • Pick deterministic template
    • Format with {Winner}/{Loser}
    • Validate length ≤ 75 chars
  → Write narratives_XX.json
```

## Usage in Renderer/UI

The renderer (e.g., in app.py) can now:

1. Load `narratives_XX.json` alongside `spieltag_XX.json`
2. Use the `line1` field for matchday graphics display
3. Use `type` for styling/color coding if desired
4. Use `meta` for debugging or detailed statistics panels

Example:
```python
with open(f"spieltage/saison_{season:02d}/narratives_{matchday:02d}.json") as f:
    narratives = json.load(f)

for home, away in matches:
    key = f"{home}-{away}"
    narrative = narratives.get(key, {})
    line1 = narrative.get("line1", "")
    print(f"{home} vs {away}: {line1}")
```

## Error Handling

The narrative generation is wrapped in a try-except block in the main simulation:
- If narrative generation fails, the simulation continues
- Errors are logged to `logs/liga_simulation.log`
- Missing narratives won't break the renderer

## Customization

To modify narrative templates:
1. Edit the `TEMPLATES` dict in `narrative_engine.py`
2. Keep 5 variations per type for good deterministic coverage
3. Ensure `{Winner}` and `{Loser}` placeholders are present
4. Keep each template ≤ 75 characters (including placeholders)

To change classification priorities:
1. Edit the `classify_narrative()` function
2. Reorder the if/elif chain as needed
3. Run `test_narrative_engine.py` to verify changes

## Performance

- Narrative generation is fast (< 50ms for typical 9-match matchday)
- Hash-based template selection is O(1)
- JSON I/O is minimal (single small file write)
- No external dependencies beyond stdlib

