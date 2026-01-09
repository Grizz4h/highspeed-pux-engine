#!/usr/bin/env python3
"""
Test backward compatibility with LigageneratorV2's data format.
"""

from narrative_engine import build_narratives_for_matchday
from pathlib import Path


def test_old_format():
    """Test with old tabelle_nord/tabelle_sued format."""
    print("Testing backward compatibility with old format...")
    print("=" * 70)
    
    spieltag_json = {
        "games": [
            {
                "home": "Berlin",
                "away": "München",
                "g_home": 3,
                "g_away": 2,
                "overtime": False,
                "shootout": False,
            },
            {
                "home": "Hamburg",
                "away": "Köln",
                "g_home": 4,
                "g_away": 1,
                "overtime": False,
                "shootout": False,
            },
        ]
    }
    
    # Old format used by LigageneratorV2
    latest_for_narrative = {
        "tabelle_nord": [
            {"Team": "Berlin", "last5": ["W", "W", "L", "W"]},
            {"Team": "Hamburg", "last5": ["W", "L", "W"]},
        ],
        "tabelle_sued": [
            {"Team": "München", "last5": ["L", "L", "W"]},
            {"Team": "Köln", "last5": ["L", "L", "L", "L"]},
        ],
    }
    
    # Generate narratives
    narratives = build_narratives_for_matchday(
        spieltag_json,
        latest_for_narrative,
        season=1,
        spieltag=1,
        memory_path=Path("/tmp/test_compat_memory.json")
    )
    
    # Verify
    assert "Berlin-München" in narratives, "Should have Berlin-München narrative"
    assert "Hamburg-Köln" in narratives, "Should have Hamburg-Köln narrative"
    
    print("\nGenerated narratives:")
    print("-" * 70)
    for pair_key, data in narratives.items():
        print(f"\n{pair_key}:")
        print(f"  {data['line1']}")
        print(f"  Length: {len(data['line1'])} chars")
        assert len(data['line1']) > 0, "Line1 should not be empty"
        assert len(data['line1']) <= 110, "Line1 should not exceed 110 chars"
        assert data['line2'] == "", "Line2 should be empty"
    
    print("\n" + "=" * 70)
    print("✅ Backward compatibility test PASSED!")
    print("=" * 70)


def test_new_format():
    """Test with new teams dict format."""
    print("\n\nTesting new format...")
    print("=" * 70)
    
    spieltag_json = {
        "games": [
            {
                "home": "Berlin",
                "away": "München",
                "g_home": 3,
                "g_away": 2,
                "overtime": False,
                "shootout": False,
            },
        ]
    }
    
    # New format
    latest_json = {
        "teams": {
            "Berlin": {"last5": ["W", "W", "L", "W"]},
            "München": {"last5": ["L", "L", "W"]},
        }
    }
    
    # Generate narratives
    narratives = build_narratives_for_matchday(
        spieltag_json,
        latest_json,
        season=1,
        spieltag=2,
        memory_path=Path("/tmp/test_new_format_memory.json")
    )
    
    # Verify
    assert "Berlin-München" in narratives
    
    print("\nGenerated narrative:")
    print("-" * 70)
    for pair_key, data in narratives.items():
        print(f"\n{pair_key}:")
        print(f"  {data['line1']}")
        print(f"  Length: {len(data['line1'])} chars")
    
    print("\n" + "=" * 70)
    print("✅ New format test PASSED!")
    print("=" * 70)


if __name__ == "__main__":
    test_old_format()
    test_new_format()
    print("\n" + "=" * 70)
    print("✅ ALL COMPATIBILITY TESTS PASSED!")
    print("=" * 70)
    print("\nThe narrative engine is fully backward compatible with LigageneratorV2!")
    print()
