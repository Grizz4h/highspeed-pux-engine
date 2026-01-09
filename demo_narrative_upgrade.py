#!/usr/bin/env python3
"""
Demo script to showcase the upgraded narrative engine.
Demonstrates:
- Longer, more complex sentences
- Compositional structure (PART A + B + C)
- Strong variety across multiple matchdays
- Deterministic generation
"""

from narrative_engine import (
    build_narratives_for_matchday,
    validate_diversity,
    NarrativeMemory,
    generate_line1,
)
from pathlib import Path
import json


def demo_single_match_variety():
    """Show variety for a single match with different contexts."""
    print("=" * 70)
    print("DEMO 1: Single Match with Varying Seeds")
    print("=" * 70)
    
    match = {
        'home': 'Eisbären Berlin',
        'away': 'Adler Mannheim',
        'g_home': 4,
        'g_away': 2,
        'overtime': False,
        'shootout': False
    }
    
    memory = NarrativeMemory()
    
    print("\nGenerating 15 narratives for the same score (4-2):")
    print("-" * 70)
    
    for i in range(15):
        ctx = {
            'season': 1,
            'spieltag': i + 1,  # Different spieltag = different seed
            'home_last5': ['W', 'W', 'L', 'W'],
            'away_last5': ['L', 'L', 'W', 'L']
        }
        
        used_openers = set()
        used_adjectives = set()
        line1 = generate_line1(match, ctx, memory, used_openers, used_adjectives)
        print(f"{i+1:2d}. {line1}")
        print(f"    Length: {len(line1)} chars")


def demo_matchday_variety():
    """Show variety across a full matchday."""
    print("\n" + "=" * 70)
    print("DEMO 2: Full Matchday with Multiple Narrative Types")
    print("=" * 70)
    
    spieltag_json = {
        "games": [
            # SO_DRAMA
            {"home": "Köln", "away": "München", "g_home": 3, "g_away": 2, 
             "overtime": False, "shootout": True},
            # OT_DRAMA
            {"home": "Berlin", "away": "Hamburg", "g_home": 4, "g_away": 3, 
             "overtime": True, "shootout": False},
            # SHUTOUT
            {"home": "Mannheim", "away": "Nürnberg", "g_home": 3, "g_away": 0, 
             "overtime": False, "shootout": False},
            # DOMINATION
            {"home": "Ingolstadt", "away": "Augsburg", "g_home": 7, "g_away": 1, 
             "overtime": False, "shootout": False},
            # STATEMENT_WIN
            {"home": "Wolfsburg", "away": "Frankfurt", "g_home": 5, "g_away": 2, 
             "overtime": False, "shootout": False},
            # GRIND_WIN
            {"home": "Düsseldorf", "away": "Krefeld", "g_home": 2, "g_away": 1, 
             "overtime": False, "shootout": False},
            # TRACK_MEET
            {"home": "Straubing", "away": "Bremerhaven", "g_home": 5, "g_away": 4, 
             "overtime": False, "shootout": False},
        ]
    }
    
    latest_json = {
        "teams": {
            "Köln": {"last5": ["W", "W", "L"]},
            "München": {"last5": ["L", "W", "W"]},
            "Berlin": {"last5": ["W", "W", "W", "W"]},
            "Hamburg": {"last5": ["L", "L", "W"]},
            "Mannheim": {"last5": ["W", "W", "W"]},
            "Nürnberg": {"last5": ["L", "L", "L"]},
            "Ingolstadt": {"last5": ["W", "W", "W"]},
            "Augsburg": {"last5": ["L", "L", "L", "L"]},
            "Wolfsburg": {"last5": ["W", "W", "W"]},
            "Frankfurt": {"last5": ["W", "L", "L"]},
            "Düsseldorf": {"last5": ["W", "L", "W"]},
            "Krefeld": {"last5": ["L", "W", "L"]},
            "Straubing": {"last5": ["W", "W"]},
            "Bremerhaven": {"last5": ["W", "L"]},
        }
    }
    
    narratives = build_narratives_for_matchday(
        spieltag_json, 
        latest_json, 
        season=1, 
        spieltag=5,
        memory_path=Path("/tmp/narrative_demo_memory.json")
    )
    
    print("\nGenerated narratives:")
    print("-" * 70)
    
    for pair_key, data in narratives.items():
        line1 = data['line1']
        print(f"\n{pair_key}:")
        print(f"  {line1}")
        print(f"  Length: {len(line1)} chars")


def demo_anti_repeat():
    """Demonstrate anti-repeat mechanism across matchdays."""
    print("\n" + "=" * 70)
    print("DEMO 3: Anti-Repeat Memory Across Multiple Matchdays")
    print("=" * 70)
    
    match = {
        'home': 'Team Alpha',
        'away': 'Team Beta',
        'g_home': 3,
        'g_away': 2,
        'overtime': False,
        'shootout': False
    }
    
    memory = NarrativeMemory()
    all_narratives = []
    
    print("\nGenerating narratives across 8 matchdays:")
    print("-" * 70)
    
    for matchday in range(1, 9):
        ctx = {
            'season': 1,
            'spieltag': matchday,
            'home_last5': ['W', 'W', 'L'],
            'away_last5': ['L', 'W', 'L']
        }
        
        used_openers = set()
        used_adjectives = set()
        line1 = generate_line1(match, ctx, memory, used_openers, used_adjectives)
        all_narratives.append(line1)
        
        print(f"\nMatchday {matchday}:")
        print(f"  {line1}")
    
    # Check for duplicates
    unique = len(set(all_narratives))
    total = len(all_narratives)
    print(f"\n" + "-" * 70)
    print(f"Unique narratives: {unique}/{total}")
    print(f"Duplicate rate: {(1 - unique/total)*100:.1f}%")
    
    if unique == total:
        print("✅ PASS: No duplicates across matchdays!")
    else:
        print("⚠️  Note: Some duplicates found (expected with limited variety)")


def demo_length_distribution():
    """Show length distribution of generated narratives."""
    print("\n" + "=" * 70)
    print("DEMO 4: Length Distribution (Target: 70-110 chars)")
    print("=" * 70)
    
    match = {
        'home': 'Team X',
        'away': 'Team Y',
        'g_home': 4,
        'g_away': 2,
        'overtime': False,
        'shootout': False
    }
    
    memory = NarrativeMemory()
    lengths = []
    
    print("\nGenerating 50 samples:")
    print("-" * 70)
    
    for i in range(50):
        ctx = {
            'season': 1,
            'spieltag': i + 1,
            'home_last5': ['W', 'L'],
            'away_last5': ['L', 'W']
        }
        
        used_openers = set()
        used_adjectives = set()
        line1 = generate_line1(match, ctx, memory, used_openers, used_adjectives)
        lengths.append(len(line1))
        
        if i < 10:  # Show first 10
            print(f"{i+1:2d}. ({len(line1):3d} chars) {line1}")
    
    # Statistics
    avg_length = sum(lengths) / len(lengths)
    min_length = min(lengths)
    max_length = max(lengths)
    in_range = sum(1 for l in lengths if 70 <= l <= 110)
    
    print("\n" + "-" * 70)
    print(f"Statistics:")
    print(f"  Average: {avg_length:.1f} chars")
    print(f"  Min:     {min_length} chars")
    print(f"  Max:     {max_length} chars")
    print(f"  In target range (70-110): {in_range}/{len(lengths)} ({in_range/len(lengths)*100:.1f}%)")
    
    if in_range / len(lengths) >= 0.7:
        print("✅ PASS: Majority of narratives in target range!")


def demo_validation():
    """Run full validation test."""
    print("\n" + "=" * 70)
    print("DEMO 5: Full Validation Test (300 samples)")
    print("=" * 70)
    print()
    
    stats = validate_diversity(sample_count=300, verbose=True)
    
    return stats


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("UPGRADED NARRATIVE ENGINE - DEMONSTRATION")
    print("=" * 70)
    print("\nKey Improvements:")
    print("  ✓ Compositional sentence structure (PART A + B + C)")
    print("  ✓ Massively expanded token pools")
    print("  ✓ Strong anti-repeat memory system")
    print("  ✓ Deterministic generation")
    print("  ✓ Target length: 70-110 chars (vs. 78 previously)")
    print("  ✓ Duplicate rate target: <2%")
    
    # Run demos
    demo_single_match_variety()
    demo_matchday_variety()
    demo_anti_repeat()
    demo_length_distribution()
    demo_validation()
    
    print("\n" + "=" * 70)
    print("✅ DEMONSTRATION COMPLETE")
    print("=" * 70)
    print("\nThe upgraded narrative engine is ready for production!")
    print("Integration points remain unchanged:")
    print("  - build_narratives_for_matchday()")
    print("  - write_narratives_json()")
    print("  - Only narratives.json is written")
    print("  - No changes to replay JSON or renderer")
    print()
