#!/usr/bin/env python3
"""
Debug script for team comparison issues.

Run this to trace exactly what's happening with a team comparison query.
"""

import os
import sys
import json
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def debug_team_comparison():
    """Debug the Eagles vs Dallas query."""
    print("=" * 60)
    print("TEAM COMPARISON DEBUG")
    print("=" * 60)
    
    query = "How do the Eagles match up against Dallas"
    print(f"\nQuery: {query}")
    
    # Step 1: Router
    print("\n--- Step 1: Router ---")
    from pipelines.router import QueryRouter
    router = QueryRouter()
    
    route_result = router.route_with_suggestions(query)
    route = route_result['route']
    
    print(f"Pipeline: {route.pipeline.value}")
    print(f"Confidence: {route.confidence}")
    print(f"Tier: {route.tier}")
    print(f"Params: {route.extracted_params}")
    
    team1 = route.extracted_params.get('team1')
    team2 = route.extracted_params.get('team2')
    season = route.extracted_params.get('season', 2025)
    
    print(f"\nExtracted: team1={team1}, team2={team2}, season={season}")
    
    # Step 2: Check team profiles
    print("\n--- Step 2: Team Profiles ---")
    profile_path = Path("data/models/team_profiles.json")
    
    if not profile_path.exists():
        print(f"❌ Profile file not found: {profile_path}")
        return
    
    with open(profile_path, 'r') as f:
        data = json.load(f)
    
    profiles = data.get('profiles', {})
    print(f"Total profiles: {len(profiles)}")
    
    # Check the exact keys
    print(f"\nLooking for keys:")
    key1 = f"{team1}_{season}"
    key2 = f"{team2}_{season}"
    
    print(f"  {key1}: {'✅ Found' if key1 in profiles else '❌ NOT FOUND'}")
    print(f"  {key2}: {'✅ Found' if key2 in profiles else '❌ NOT FOUND'}")
    
    # Try uppercase
    key1_upper = f"{team1.upper() if team1 else 'None'}_{season}"
    key2_upper = f"{team2.upper() if team2 else 'None'}_{season}"
    
    if key1 != key1_upper or key2 != key2_upper:
        print(f"\nTrying uppercase:")
        print(f"  {key1_upper}: {'✅ Found' if key1_upper in profiles else '❌ NOT FOUND'}")
        print(f"  {key2_upper}: {'✅ Found' if key2_upper in profiles else '❌ NOT FOUND'}")
    
    # Show sample keys from profiles
    print(f"\nSample profile keys: {list(profiles.keys())[:10]}")
    
    # Step 3: Executor
    print("\n--- Step 3: Executor ---")
    try:
        from pipelines.executor import PipelineExecutor
        executor = PipelineExecutor()
        
        result = executor.execute(route)
        print(f"Success: {result.get('success')}")
        
        if result.get('error'):
            print(f"Error: {result.get('error')}")
        
        if result.get('data'):
            print(f"Data keys: {list(result['data'].keys())}")
    except Exception as e:
        print(f"Executor error: {e}")
    
    print("\n" + "=" * 60)


def list_all_profile_keys():
    """List all available profile keys."""
    print("\n" + "=" * 60)
    print("ALL PROFILE KEYS")
    print("=" * 60)
    
    profile_path = Path("data/models/team_profiles.json")
    
    if not profile_path.exists():
        print(f"❌ Profile file not found: {profile_path}")
        return
    
    with open(profile_path, 'r') as f:
        data = json.load(f)
    
    profiles = data.get('profiles', {})
    
    # Group by season
    by_season = {}
    for key in sorted(profiles.keys()):
        parts = key.split('_')
        if len(parts) == 2:
            team, season = parts
            if season not in by_season:
                by_season[season] = []
            by_season[season].append(team)
    
    for season in sorted(by_season.keys()):
        teams = sorted(by_season[season])
        print(f"\n{season}: {', '.join(teams)}")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    debug_team_comparison()
    list_all_profile_keys()
