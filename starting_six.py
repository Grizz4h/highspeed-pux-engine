"""
Starting Six Generator

Generates matchday-wide Starting Six selection from lineup JSONs.
Selection criteria:
- Pool: All players from all teams' lineups (forwards, defense, goalies)
- Positions: 2D, 3F, 1G
- Weighted random selection with anti-repeat logic
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Dict, List, Set, Optional, Tuple


def _compute_weight(
    player: Dict[str, Any],
    last_starting_six_matchday: Dict[str, int],
    starting_six_appearances: Dict[str, int],
    current_spieltag: int,
) -> float:
    """
    Compute selection weight for a player.
    
    Weight formula:
    - base = overall
    - bonus for line/pair: 1:+6, 2:+3, 3:+1
    - penalty if rotation==true: -4
    - anti-repeat penalty:
        - if lastStartingSixMatchday[id] == spieltag-1: -10 (or exclude by returning 0)
        - minus startingSixAppearances[id] * 0.8
    """
    player_id = player["id"]
    base = float(player.get("overall", 70))
    
    # Line/Pair bonus
    line = player.get("line")
    pair = player.get("pair")
    
    bonus = 0
    if line == 1:
        bonus = 6
    elif line == 2:
        bonus = 3
    elif line == 3:
        bonus = 1
    
    if pair == 1:
        bonus = 6
    elif pair == 2:
        bonus = 3
    elif pair == 3:
        bonus = 1
    
    # Rotation penalty
    rotation_penalty = 4 if player.get("rotation", False) else 0
    
    # Anti-repeat penalties
    last_matchday = last_starting_six_matchday.get(player_id, 0)
    appearances = starting_six_appearances.get(player_id, 0)
    
    # If appeared in last matchday, heavily penalize or exclude
    consecutive_penalty = 10 if last_matchday == current_spieltag - 1 else 0
    appearance_penalty = appearances * 0.8
    
    weight = base + bonus - rotation_penalty - consecutive_penalty - appearance_penalty
    
    # Ensure non-negative weight
    return max(0.1, weight)


def _collect_candidate_pool(
    lineups: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Collect all players from all teams into position pools.
    
    Returns:
        (forwards, defenders, goalies) - deduplicated by player ID, each with 'team' field
    """
    forwards_map: Dict[str, Dict[str, Any]] = {}
    defenders_map: Dict[str, Dict[str, Any]] = {}
    goalies_map: Dict[str, Dict[str, Any]] = {}
    
    for team_name, team_data in lineups.items():
        # Forwards
        fwd_data = team_data.get("forwards", {})
        for line_key in ["line1", "line2", "line3", "line4"]:
            for player in fwd_data.get(line_key, []):
                pid = player["id"]
                if pid not in forwards_map:
                    player_with_team = player.copy()
                    player_with_team["team"] = team_name
                    forwards_map[pid] = player_with_team
        
        # Rotation forwards if present
        for player in fwd_data.get("rotation", []):
            pid = player["id"]
            if pid not in forwards_map:
                player_with_team = player.copy()
                player_with_team["team"] = team_name
                forwards_map[pid] = player_with_team
        
        # Defenders
        def_data = team_data.get("defense", {})
        for pair_key in ["pair1", "pair2", "pair3"]:
            for player in def_data.get(pair_key, []):
                pid = player["id"]
                if pid not in defenders_map:
                    player_with_team = player.copy()
                    player_with_team["team"] = team_name
                    defenders_map[pid] = player_with_team
        
        # Rotation defenders if present
        for player in def_data.get("rotation", []):
            pid = player["id"]
            if pid not in defenders_map:
                player_with_team = player.copy()
                player_with_team["team"] = team_name
                defenders_map[pid] = player_with_team
        
        # Goalie (single object, not array)
        goalie = team_data.get("goalie")
        if goalie and isinstance(goalie, dict):
            pid = goalie["id"]
            if pid not in goalies_map:
                goalie_with_team = goalie.copy()
                goalie_with_team["team"] = team_name
                goalies_map[pid] = goalie_with_team
    
    return (
        list(forwards_map.values()),
        list(defenders_map.values()),
        list(goalies_map.values()),
    )


def _weighted_random_choice(
    candidates: List[Dict[str, Any]],
    weights: List[float],
    k: int,
    seed: int,
) -> List[Dict[str, Any]]:
    """
    Select k items from candidates using weighted random sampling without replacement.
    """
    rng = random.Random(seed)
    
    if len(candidates) < k:
        # Not enough candidates, return all
        return candidates
    
    # Use random.choices with weights, then deduplicate
    # Since we need without replacement, we'll do it manually
    selected = []
    remaining_candidates = candidates[:]
    remaining_weights = weights[:]
    
    for _ in range(k):
        if not remaining_candidates:
            break
        
        # Weighted random choice
        total = sum(remaining_weights)
        if total <= 0:
            # All weights are zero, pick randomly
            choice = rng.choice(remaining_candidates)
        else:
            r = rng.random() * total
            cumulative = 0
            choice = None
            for i, w in enumerate(remaining_weights):
                cumulative += w
                if r <= cumulative:
                    choice = remaining_candidates[i]
                    break
            if choice is None:
                choice = remaining_candidates[-1]
        
        selected.append(choice)
        
        # Remove selected from remaining
        idx = remaining_candidates.index(choice)
        remaining_candidates.pop(idx)
        remaining_weights.pop(idx)
    
    return selected


def generate_starting_six(
    lineups: Dict[str, Any],
    season: int,
    spieltag: int,
    season_state: Dict[str, Any],
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Generate Starting Six from matchday lineups.
    
    Args:
        lineups: Lineups payload from spieltag JSON (teams dict)
        season: Current season number
        spieltag: Current matchday number
        season_state: Persistent season state with:
            - startingSixAppearances: {player_id: count}
            - lastStartingSixMatchday: {player_id: matchday}
        seed: Optional seed for deterministic selection
    
    Returns:
        Starting Six payload to embed in matchday JSON:
        {
            "version": 1,
            "seed": int,
            "source": "lineups",
            "players": [{"id": str, "pos": str, "team": str}, ...],
            "meta": {
                "fallback_used": bool,
                "pool_sizes": {"F": int, "D": int, "G": int}
            }
        }
    """
    if seed is None:
        seed = (season * 1000 + spieltag) % (2**31)
    
    # Get persistent state
    starting_six_appearances = season_state.get("startingSixAppearances", {})
    last_starting_six_matchday = season_state.get("lastStartingSixMatchday", {})
    
    # Collect candidate pools
    forwards, defenders, goalies = _collect_candidate_pool(lineups)
    
    # Compute weights
    fwd_weights = [
        _compute_weight(p, last_starting_six_matchday, starting_six_appearances, spieltag)
        for p in forwards
    ]
    def_weights = [
        _compute_weight(p, last_starting_six_matchday, starting_six_appearances, spieltag)
        for p in defenders
    ]
    gol_weights = [
        _compute_weight(p, last_starting_six_matchday, starting_six_appearances, spieltag)
        for p in goalies
    ]
    
    # Select 3F, 2D, 1G
    selected_forwards = _weighted_random_choice(forwards, fwd_weights, 3, seed)
    selected_defenders = _weighted_random_choice(defenders, def_weights, 2, seed + 1)
    selected_goalies = _weighted_random_choice(goalies, gol_weights, 1, seed + 2)
    
    # Build result
    players = []
    for p in selected_forwards:
        players.append({"id": p["id"], "pos": "F", "team": p["team"]})
    for p in selected_defenders:
        players.append({"id": p["id"], "pos": "D", "team": p["team"]})
    for p in selected_goalies:
        players.append({"id": p["id"], "pos": "G", "team": p["team"]})
    
    # Update season state
    for p in selected_forwards + selected_defenders + selected_goalies:
        pid = p["id"]
        starting_six_appearances[pid] = starting_six_appearances.get(pid, 0) + 1
        last_starting_six_matchday[pid] = spieltag
    
    # Store updated state back
    season_state["startingSixAppearances"] = starting_six_appearances
    season_state["lastStartingSixMatchday"] = last_starting_six_matchday
    
    fallback_used = (
        len(selected_forwards) < 3 or
        len(selected_defenders) < 2 or
        len(selected_goalies) < 1
    )
    
    return {
        "version": 1,
        "seed": seed,
        "source": "lineups",
        "players": players,
        "meta": {
            "fallback_used": fallback_used,
            "pool_sizes": {
                "F": len(forwards),
                "D": len(defenders),
                "G": len(goalies),
            }
        }
    }


def load_lineup_json(lineup_path: Path) -> Dict[str, Any]:
    """Load lineup JSON from file."""
    with open(lineup_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_matchday_json_with_starting_six(
    matchday_path: Path,
    starting_six: Dict[str, Any],
) -> None:
    """
    Load matchday JSON, add starting_six, and save back.
    """
    with open(matchday_path, "r", encoding="utf-8") as f:
        matchday_json = json.load(f)
    
    matchday_json["starting_six"] = starting_six
    
    with open(matchday_path, "w", encoding="utf-8") as f:
        json.dump(matchday_json, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    # Test/debug mode
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python starting_six.py <lineup_json_path> <matchday_json_path>")
        sys.exit(1)
    
    lineup_path = Path(sys.argv[1])
    matchday_path = Path(sys.argv[2])
    
    # Load lineup
    lineup_data = load_lineup_json(lineup_path)
    lineups = lineup_data.get("teams", {})
    season = lineup_data.get("season", 1)
    spieltag = lineup_data.get("spieltag", 1)
    
    # Mock season state for testing
    season_state = {
        "startingSixAppearances": {},
        "lastStartingSixMatchday": {},
    }
    
    # Generate Starting Six
    starting_six = generate_starting_six(lineups, season, spieltag, season_state)
    
    print(json.dumps(starting_six, indent=2))
    
    # Save to matchday JSON
    save_matchday_json_with_starting_six(matchday_path, starting_six)
    print(f"\n✅ Starting Six embedded into {matchday_path}")
