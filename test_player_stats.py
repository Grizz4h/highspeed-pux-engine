"""
Unit tests for player stats export
"""

import json
from player_stats_export import (
    _collect_gp_from_lineup,
    build_player_stats_for_matchday,
    merge_into_season_player_stats,
)
import pandas as pd


def test_collect_gp_from_lineup():
    """Test GP collection from lineup JSON."""
    lineup_json = {
        "season": 1,
        "spieltag": 1,
        "teams": {
            "TeamA": {
                "forwards": {
                    "line1": [
                        {"id": "f1", "name": "Forward 1", "rotation": False, "pos": "F"},
                        {"id": "f2", "name": "Forward 2", "rotation": False, "pos": "F"},
                    ],
                    "line2": [
                        {"id": "f3", "name": "Forward 3", "rotation": True, "pos": "F"},  # rotation - should NOT count
                    ],
                    "line3": [],
                    "line4": [],
                },
                "defense": {
                    "pair1": [
                        {"id": "d1", "name": "Defender 1", "rotation": False, "pos": "D"},
                    ],
                    "pair2": [],
                    "pair3": [],
                },
                "goalie": {"id": "g1", "name": "Goalie 1", "pos": "G"},
            }
        }
    }
    
    gp_map = _collect_gp_from_lineup(lineup_json)
    
    # Check counts
    assert "f1" in gp_map, "Forward 1 should be in GP map"
    assert "f2" in gp_map, "Forward 2 should be in GP map"
    assert "f3" not in gp_map, "Forward 3 (rotation) should NOT be in GP map"
    assert "d1" in gp_map, "Defender 1 should be in GP map"
    assert "g1" in gp_map, "Goalie should be in GP map"
    
    # Check values
    assert gp_map["f1"]["gp"] == 1, "Forward 1 should have 1 GP"
    assert gp_map["f1"]["pos"] == "F", "Forward 1 should have pos F"
    
    assert gp_map["g1"]["gp"] == 1, "Goalie should have 1 GP"
    assert gp_map["g1"]["gs"] == 1, "Goalie should have 1 GS"
    assert gp_map["g1"]["pos"] == "G", "Goalie should have pos G"
    
    print("✅ test_collect_gp_from_lineup passed")


def test_merge_stats():
    """Test merging matchday stats into season stats."""
    existing = {
        "player1": {
            "pos": "F",
            "gp": 3,
            "g": 5,
            "a": 2,
            "pts": 7,
        },
        "player2": {
            "pos": "D",
            "gp": 2,
            "g": 1,
            "pts": 1,
        }
    }
    
    matchday_deltas = {
        "player1": {
            "pos": "F",
            "gp": 1,
            "g": 2,
            "a": 1,
            "pts": 3,
        },
        "player3": {
            "pos": "G",
            "gp": 1,
            "gs": 1,
        }
    }
    
    result = merge_into_season_player_stats(existing, matchday_deltas)
    
    # player1 should be updated
    assert result["player1"]["gp"] == 4, "player1 GP should be 4"
    assert result["player1"]["g"] == 7, "player1 goals should be 7"
    assert result["player1"]["a"] == 3, "player1 assists should be 3"
    assert result["player1"]["pts"] == 10, "player1 points should be 10"
    
    # player2 should be unchanged
    assert result["player2"]["gp"] == 2, "player2 should be unchanged"
    
    # player3 should be new
    assert "player3" in result, "player3 should be added"
    assert result["player3"]["gp"] == 1, "player3 GP should be 1"
    assert result["player3"]["gs"] == 1, "player3 GS should be 1"
    
    print("✅ test_merge_stats passed")


def test_build_player_stats():
    """Test building stats from lineup + DataFrame."""
    lineup_json = {
        "season": 1,
        "spieltag": 1,
        "teams": {
            "TeamA": {
                "forwards": {
                    "line1": [
                        {"id": "alice_id", "name": "Alice", "rotation": False, "pos": "F"},
                    ],
                    "line2": [],
                    "line3": [],
                    "line4": [],
                },
                "defense": {
                    "pair1": [
                        {"id": "bob_id", "name": "Bob", "rotation": False, "pos": "D"},
                    ],
                    "pair2": [],
                    "pair3": [],
                },
                "goalie": {"id": "charlie_id", "name": "Charlie", "pos": "G"},
            }
        }
    }
    
    # Mock DataFrame
    stats_df = pd.DataFrame([
        {"Player": "Alice", "Goals": 2, "Assists": 1},
        {"Player": "Bob", "Goals": 1, "Assists": 0},
        {"Player": "Charlie", "Goals": 0, "Assists": 0},
    ])
    
    # Mock teams for ID mapping
    all_teams = [
        {
            "Team": "TeamA",
            "Players": [
                {"Name": "Alice", "id": "alice_id"},
                {"Name": "Bob", "id": "bob_id"},
                {"Name": "Charlie", "id": "charlie_id"},
            ]
        }
    ]
    
    result = build_player_stats_for_matchday(lineup_json, stats_df, all_teams)
    
    # Check Alice
    assert "alice_id" in result, "Alice should be in result"
    assert result["alice_id"]["gp"] == 1, "Alice should have 1 GP"
    assert result["alice_id"]["g"] == 2, "Alice should have 2 goals"
    assert result["alice_id"]["a"] == 1, "Alice should have 1 assist"
    assert result["alice_id"]["pts"] == 3, "Alice should have 3 points"
    
    # Check Bob
    assert "bob_id" in result, "Bob should be in result"
    assert result["bob_id"]["gp"] == 1, "Bob should have 1 GP"
    assert result["bob_id"]["g"] == 1, "Bob should have 1 goal"
    assert "a" not in result["bob_id"] or result["bob_id"]["a"] == 0, "Bob should have 0 assists"
    
    # Check Charlie (goalie)
    assert "charlie_id" in result, "Charlie should be in result"
    assert result["charlie_id"]["gp"] == 1, "Charlie should have 1 GP"
    assert result["charlie_id"]["gs"] == 1, "Charlie should have 1 GS"
    assert result["charlie_id"]["pos"] == "G", "Charlie should be pos G"
    
    print("✅ test_build_player_stats passed")
    print(f"   Result: {len(result)} players tracked")


if __name__ == "__main__":
    print("🧪 Running Player Stats Export unit tests...\n")
    
    test_collect_gp_from_lineup()
    test_merge_stats()
    test_build_player_stats()
    
    print("\n✅ All player stats tests passed!")
