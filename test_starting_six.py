"""
Unit tests for Starting Six generation
"""

import json
from pathlib import Path
from starting_six import (
    _collect_candidate_pool,
    _compute_weight,
    generate_starting_six,
)


def test_candidate_pool():
    """Test that candidate pool collection works correctly."""
    lineups = {
        "TeamA": {
            "forwards": {
                "line1": [
                    {"id": "f1", "name": "Forward 1", "number": 10, "pos": "F", "overall": 85, "line": 1, "pair": None, "rotation": False}
                ],
                "line2": [
                    {"id": "f2", "name": "Forward 2", "number": 11, "pos": "F", "overall": 80, "line": 2, "pair": None, "rotation": False}
                ],
                "line3": [],
                "line4": [],
            },
            "defense": {
                "pair1": [
                    {"id": "d1", "name": "Defender 1", "number": 2, "pos": "D", "overall": 82, "line": None, "pair": 1, "rotation": False}
                ],
                "pair2": [],
                "pair3": [],
            },
            "goalie": {"id": "g1", "name": "Goalie 1", "number": 1, "pos": "G", "overall": 88, "line": None, "pair": None, "rotation": False}
        }
    }
    
    forwards, defenders, goalies = _collect_candidate_pool(lineups)
    
    assert len(forwards) == 2, f"Expected 2 forwards, got {len(forwards)}"
    assert len(defenders) == 1, f"Expected 1 defender, got {len(defenders)}"
    assert len(goalies) == 1, f"Expected 1 goalie, got {len(goalies)}"
    
    # Check that team field was added
    assert forwards[0]["team"] == "TeamA", f"Expected team 'TeamA', got {forwards[0].get('team')}"
    assert defenders[0]["team"] == "TeamA", f"Expected team 'TeamA', got {defenders[0].get('team')}"
    assert goalies[0]["team"] == "TeamA", f"Expected team 'TeamA', got {goalies[0].get('team')}"
    
    print("✅ test_candidate_pool passed")


def test_weight_computation():
    """Test weight computation with various scenarios."""
    player_line1 = {
        "id": "p1",
        "overall": 85,
        "line": 1,
        "pair": None,
        "rotation": False,
    }
    
    player_rotation = {
        "id": "p2",
        "overall": 80,
        "line": None,
        "pair": None,
        "rotation": True,
    }
    
    last_matchday = {}
    appearances = {}
    current_spieltag = 5
    
    # Line 1 player should get +6 bonus
    w1 = _compute_weight(player_line1, last_matchday, appearances, current_spieltag)
    assert w1 == 85 + 6, f"Expected 91, got {w1}"
    
    # Rotation player should get -4 penalty
    w2 = _compute_weight(player_rotation, last_matchday, appearances, current_spieltag)
    assert w2 == 80 - 4, f"Expected 76, got {w2}"
    
    # Test consecutive penalty
    last_matchday["p1"] = 4  # Appeared in spieltag 4
    w3 = _compute_weight(player_line1, last_matchday, appearances, current_spieltag)
    assert w3 == 85 + 6 - 10, f"Expected 81 (consecutive penalty), got {w3}"
    
    # Test appearance penalty
    appearances["p1"] = 3
    last_matchday["p1"] = 2  # Not consecutive
    w4 = _compute_weight(player_line1, last_matchday, appearances, current_spieltag)
    expected = 85 + 6 - (3 * 0.8)
    assert abs(w4 - expected) < 0.01, f"Expected {expected}, got {w4}"
    
    print("✅ test_weight_computation passed")


def test_generate_starting_six():
    """Test full Starting Six generation."""
    lineups = {
        "TeamA": {
            "forwards": {
                "line1": [
                    {"id": "f1", "name": "F1", "number": 10, "pos": "F", "overall": 85, "line": 1, "pair": None, "rotation": False},
                    {"id": "f2", "name": "F2", "number": 11, "pos": "F", "overall": 84, "line": 1, "pair": None, "rotation": False},
                    {"id": "f3", "name": "F3", "number": 12, "pos": "F", "overall": 83, "line": 1, "pair": None, "rotation": False},
                ],
                "line2": [
                    {"id": "f4", "name": "F4", "number": 13, "pos": "F", "overall": 80, "line": 2, "pair": None, "rotation": False},
                ],
                "line3": [],
                "line4": [],
            },
            "defense": {
                "pair1": [
                    {"id": "d1", "name": "D1", "number": 2, "pos": "D", "overall": 82, "line": None, "pair": 1, "rotation": False},
                    {"id": "d2", "name": "D2", "number": 3, "pos": "D", "overall": 81, "line": None, "pair": 1, "rotation": False},
                ],
                "pair2": [
                    {"id": "d3", "name": "D3", "number": 4, "pos": "D", "overall": 79, "line": None, "pair": 2, "rotation": False},
                ],
                "pair3": [],
            },
            "goalie": {"id": "g1", "name": "G1", "number": 1, "pos": "G", "overall": 88, "line": None, "pair": None, "rotation": False}
        },
        "TeamB": {
            "forwards": {
                "line1": [
                    {"id": "f5", "name": "F5", "number": 20, "pos": "F", "overall": 86, "line": 1, "pair": None, "rotation": False},
                ],
                "line2": [],
                "line3": [],
                "line4": [],
            },
            "defense": {
                "pair1": [
                    {"id": "d4", "name": "D4", "number": 22, "pos": "D", "overall": 83, "line": None, "pair": 1, "rotation": False},
                ],
                "pair2": [],
                "pair3": [],
            },
            "goalie": {"id": "g2", "name": "G2", "number": 21, "pos": "G", "overall": 87, "line": None, "pair": None, "rotation": False}
        }
    }
    
    season_state = {
        "startingSixAppearances": {},
        "lastStartingSixMatchday": {},
    }
    
    result = generate_starting_six(
        lineups=lineups,
        season=1,
        spieltag=5,
        season_state=season_state,
        seed=12345,
    )
    
    # Validate structure
    assert "version" in result
    assert "seed" in result
    assert "source" in result
    assert "players" in result
    assert "meta" in result
    
    assert result["version"] == 1
    assert result["source"] == "lineups"
    assert result["seed"] == 12345
    
    # Validate player count
    players = result["players"]
    forwards = [p for p in players if p["pos"] == "F"]
    defenders = [p for p in players if p["pos"] == "D"]
    goalies = [p for p in players if p["pos"] == "G"]
    
    assert len(forwards) == 3, f"Expected 3 forwards, got {len(forwards)}"
    assert len(defenders) == 2, f"Expected 2 defenders, got {len(defenders)}"
    assert len(goalies) == 1, f"Expected 1 goalie, got {len(goalies)}"
    
    # Validate all players have required fields
    for player in players:
        assert "id" in player, "Player missing 'id' field"
        assert "pos" in player, "Player missing 'pos' field"
        assert "team" in player, "Player missing 'team' field"
        assert player["pos"] in ["F", "D", "G"], f"Invalid position: {player['pos']}"
        assert isinstance(player["team"], str), f"Team should be string, got {type(player['team'])}"
    
    # Validate season state was updated
    assert len(season_state["startingSixAppearances"]) == 6, "All 6 players should have appearances tracked"
    assert len(season_state["lastStartingSixMatchday"]) == 6, "All 6 players should have last matchday tracked"
    
    # Validate all players have matchday 5
    for player_id, matchday in season_state["lastStartingSixMatchday"].items():
        assert matchday == 5, f"Player {player_id} should have lastMatchday=5, got {matchday}"
    
    print("✅ test_generate_starting_six passed")
    print(f"   Selected: {len(forwards)}F, {len(defenders)}D, {len(goalies)}G")
    print(f"   Pool sizes: {result['meta']['pool_sizes']}")


if __name__ == "__main__":
    print("🧪 Running Starting Six unit tests...\n")
    
    test_candidate_pool()
    test_weight_computation()
    test_generate_starting_six()
    
    print("\n✅ All tests passed!")
