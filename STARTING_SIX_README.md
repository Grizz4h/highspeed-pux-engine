# Starting Six Feature

## Overview

The Starting Six feature automatically selects 6 players (2D, 3F, 1G) from all matchday lineups to highlight standout performers. Selection is weighted-random with anti-repeat logic to ensure variety across matchdays.

## Integration

The feature is integrated into `LigageneratorV2.py` and runs automatically during `step_regular_season_once()`:

1. **After lineups are generated** for Nord and Süd matches
2. **Before narrative generation** (so narratives can reference Starting Six if needed)
3. **Results embedded** into `spieltag_XX.json` under `starting_six` key

## Selection Algorithm

### Candidate Pool
- **Forwards**: All forwards from line1, line2, line3, line4, plus rotation
- **Defenders**: All defenders from pair1, pair2, pair3, plus rotation  
- **Goalies**: All team goalies
- **Deduplication**: By player ID across all teams

### Weight Formula
```
weight = overall + line_bonus - rotation_penalty - consecutive_penalty - appearance_penalty

Where:
- overall: Player's overall rating (base weight)
- line_bonus: Line/Pair position bonus
  - Line/Pair 1: +6
  - Line/Pair 2: +3
  - Line/Pair 3: +1
  - Line/Pair 4 or rotation: 0
- rotation_penalty: -4 if player.rotation == true
- consecutive_penalty: -10 if player appeared in last matchday's Starting Six
- appearance_penalty: -0.8 * total_appearances_this_season
```

### Selection
- **3 Forwards**: Weighted random without replacement
- **2 Defenders**: Weighted random without replacement
- **1 Goalie**: Weighted random without replacement
- **Seed**: `(season * 1000 + spieltag) % 2^31` for deterministic results

## Output Format

Embedded in `spieltag_XX.json`:

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
      "pool_sizes": {
        "F": 96,
        "D": 56,
        "G": 8
      }
    }
  }
}
```

## Persistent State

Two maps are tracked in `savegame.json`:

```json
{
  "startingSixAppearances": {
    "player_123": 3,
    "player_456": 1,
    ...
  },
  "lastStartingSixMatchday": {
    "player_123": 14,
    "player_456": 12,
    ...
  }
}
```

These maps ensure:
- Players who appeared recently get penalized (variety)
- Frequent appearances accumulate a penalty (spread the spotlight)

## Migration

Old savegames without Starting Six tracking are automatically migrated:
- Missing maps are initialized as empty `{}`
- No manual intervention needed

## Files Modified

- `starting_six.py` (new): Core algorithm
- `LigageneratorV2.py`: Integration hook
  - Import added
  - `_init_new_season_state()`: Initialize Starting Six maps
  - `step_regular_season_once()`: Migration + generation + embed
  - `save_state()`: Persist Starting Six maps

## Testing

### Unit Test
```bash
# Create a mock lineup JSON
python starting_six.py <lineup_json_path> <matchday_json_path>
```

### Integration Test
```bash
# Run one matchday step and verify starting_six appears in JSON
python -c "
from LigageneratorV2 import step_regular_season_once
result = step_regular_season_once()
print(result)
"
```

### Verify Output
```bash
# Check spieltag JSON has starting_six
cat data/spieltage/saison_01/spieltag_01.json | jq '.starting_six'
```

## Future Enhancements

1. **Narrative Integration**: Reference Starting Six players in matchday narratives
2. **UI Display**: Show Starting Six in web frontend
3. **Historical Stats**: Track lifetime Starting Six appearances per player
4. **Themed Selections**: e.g., "Defensive Dominance" (4D, 2G) or "Offensive Explosion" (4F, 2G)
