# Starting Six - Quick Reference

## What It Does
Automatically selects 6 standout players (3F, 2D, 1G) from each matchday's lineups and embeds them into `spieltag_XX.json`.

## How It Works
1. **Pool**: All players from all teams (deduplicated by ID)
2. **Weights**: Based on overall rating, line/pair position, rotation status, and anti-repeat penalties
3. **Selection**: Deterministic weighted random (seeded by season + matchday)
4. **Output**: Embedded as `starting_six` object in matchday JSON

## Weight Formula
```
weight = overall 
       + line_bonus (1st:+6, 2nd:+3, 3rd:+1)
       - rotation_penalty (-4)
       - consecutive_penalty (-10 if last matchday)
       - appearance_penalty (-0.8 per appearance)
```

## Files

| File | Purpose |
|------|---------|
| `starting_six.py` | Core algorithm |
| `LigageneratorV2.py` | Integration (runs after lineups, before narratives) |
| `test_starting_six.py` | Unit tests |
| `STARTING_SIX_README.md` | Full documentation |

## Example Output
```json
{
  "starting_six": {
    "version": 1,
    "seed": 1042,
    "source": "lineups",
    "players": [
      {"id": "player_123", "pos": "F"},
      {"id": "player_456", "pos": "F"},
      {"id": "player_789", "pos": "F"},
      {"id": "player_321", "pos": "D"},
      {"id": "player_654", "pos": "D"},
      {"id": "player_987", "pos": "G"}
    ],
    "meta": {
      "fallback_used": false,
      "pool_sizes": {"F": 96, "D": 56, "G": 8}
    }
  }
}
```

## Persistent State (in savegame.json)
```json
{
  "startingSixAppearances": {"player_123": 3, ...},
  "lastStartingSixMatchday": {"player_123": 14, ...}
}
```

## Testing
```bash
# Unit tests
python test_starting_six.py

# Integration test (run one matchday)
python app.py  # Use GUI to step forward

# Verify output
cat data/spieltage/saison_01/spieltag_XX.json | jq '.starting_six'
```

## Migration
Old savegames are auto-migrated. No manual action needed.

## Future Ideas
- Reference Starting Six in narratives
- Display in web UI
- Track lifetime Starting Six stats per player
- Themed selections (e.g., "Defensive Wall", "Offensive Explosion")
