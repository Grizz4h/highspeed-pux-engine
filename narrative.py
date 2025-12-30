"""
narrative.py

Generiert deterministische Zwei-Zeilen-Narratives aus Replay-Daten.
"""

import json
import random
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional

def derive_match_features(replay: Dict[str, Any]) -> Dict[str, Any]:
    """
    Leitet Flags und Derived Values aus dem Replay ab.
    """
    g_home = replay.get("g_home", 0)
    g_away = replay.get("g_away", 0)
    goal_diff = abs(g_home - g_away)
    winner = replay["home"] if g_home > g_away else replay["away"]
    loser = replay["away"] if g_home > g_away else replay["home"]
    result = f"{g_home}:{g_away}"

    events = replay.get("events", [])
    goals = [e for e in events if e.get("type") == "goal"]

    # Lead changes (vereinfacht: zähle Score-Änderungen)
    lead_changes = 0
    current_lead = None
    for goal in goals:
        # Annahme: goals haben minute oder ähnlich
        pass  # Placeholder

    # Late decider: letztes Goal nach 45 Min (vereinfacht)
    last_goal_minute = max((g.get("minute", 0) for g in goals), default=0)
    late_decider = last_goal_minute >= 45

    # Comeback: loser führte mit >=2 und verlor
    comeback = False  # Placeholder

    flags = {
        "close_game": goal_diff <= 1,
        "blowout": goal_diff >= 3,
        "late_decider": late_decider,
        "lead_changes": lead_changes >= 2,
        "comeback": comeback,
        "ot_game": replay.get("overtime", False),
        "so_game": replay.get("shootout", False),
        "special_teams_edge": False,  # Placeholder
        "goalie_decided": False,  # Placeholder
        "chaos_game": False,  # Placeholder
    }

    derived = {
        "winner": winner,
        "loser": loser,
        "home_team": replay["home"],
        "away_team": replay["away"],
        "result": result,
        "score": result,
        "decisive_minute": last_goal_minute,
        "gwg_minute": last_goal_minute,
        "goal_diff": goal_diff,
        "lead_changes": lead_changes,
    }

    return {"flags": flags, "derived": derived}

def select_fragment(fragments: List[Dict[str, Any]], flags: Dict[str, bool], seed: int) -> Optional[Dict[str, Any]]:
    """
    Wählt deterministisch ein Fragment, das requires erfüllt.
    """
    random.seed(seed)
    candidates = [f for f in fragments if all(flags.get(r, False) for r in f.get("requires", []))]
    if not candidates:
        return None
    weights = [f.get("w", 1) for f in candidates]
    return random.choices(candidates, weights=weights, k=1)[0]

def render_two_line_narrative(replay: Dict[str, Any], library: Dict[str, Any], seed_key: str) -> Dict[str, Any]:
    """
    Rendert die zwei Zeilen.
    """
    features = derive_match_features(replay)
    flags = features["flags"]
    derived = features["derived"]

    version = library.get("version", "unknown")
    seed = int(hashlib.md5(f"{seed_key}_{version}".encode()).hexdigest(), 16) % (2**32)

    # Line1: opener
    openers = library["fragments"]["openers"]
    opener = select_fragment(openers, flags, seed)
    if not opener:
        line1 = f"{derived['winner']} setzt sich durch."
    else:
        line1 = opener["t"].format(**derived)

    # Line2
    if flags["so_game"]:
        fragments = library["fragments"]["so_line2"]
    elif flags["ot_game"]:
        fragments = library["fragments"]["ot_line2"]
    else:
        fragments = library["fragments"]["factor_line2"]

    factor = select_fragment(fragments, flags, seed + 1)
    if not factor:
        line2 = f"Endstand: {derived['result']}."
    else:
        line2 = factor["t"].format(**derived)

    return {
        "line1": line1,
        "line2": line2,
        "used_fragment_ids": [opener.get("id") if opener else None, factor.get("id") if factor else None],
        "flags": flags,
        "derived": derived
    }