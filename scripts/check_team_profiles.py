#!/usr/bin/env python3
"""
Diagnostic script to check team profiles data.

Run this if team comparisons are failing with "profiles not found".
"""

import os
import sys
import json
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

MODEL_DIR = Path("data/models")

def load_env():
    """Try multiple ways to load environment variables."""
    # Try dotenv
    try:
        from dotenv import load_dotenv
        # Try multiple possible .env locations
        env_paths = [
            Path('.env'),
            Path(__file__).parent.parent / '.env',
            Path.home() / '.env',
        ]
        for env_path in env_paths:
            if env_path.exists():
                load_dotenv(env_path)
                print(f"   Loaded .env from: {env_path}")
                return True
    except ImportError:
        pass
    return False


def check_team_profiles():
    """Check team profiles JSON file."""
    profile_path = MODEL_DIR / "team_profiles.json"
    
    print("=" * 60)
    print("TEAM PROFILES DIAGNOSTIC")
    print("=" * 60)
    
    # Check if file exists
    if not profile_path.exists():
        print(f"\n❌ ERROR: Team profiles file not found at {profile_path}")
        print("\nTo fix this, run:")
        print("  python training/train_all_models.py")
        return False
    
    print(f"\n✅ Profile file found: {profile_path}")
    print(f"   File size: {profile_path.stat().st_size / 1024:.1f} KB")
    
    # Load and inspect
    with open(profile_path, 'r') as f:
        data = json.load(f)
    
    profiles = data.get('profiles', {})
    
    print(f"\n📊 Total profile entries: {len(profiles)}")
    
    # Extract teams and seasons
    teams_by_season = {}
    for key in profiles.keys():
        parts = key.split('_')
        if len(parts) == 2:
            team, season = parts
            if season not in teams_by_season:
                teams_by_season[season] = []
            teams_by_season[season].append(team)
    
    print("\n📅 Profiles by season:")
    for season in sorted(teams_by_season.keys()):
        teams = sorted(teams_by_season[season])
        print(f"   {season}: {len(teams)} teams")
    
    # Check for all 32 NFL teams in latest season
    # Note: Using 'LA' for Rams (nflfastR convention), not 'LAR'
    expected_teams = {
        'ARI', 'ATL', 'BAL', 'BUF', 'CAR', 'CHI', 'CIN', 'CLE',
        'DAL', 'DEN', 'DET', 'GB', 'HOU', 'IND', 'JAX', 'KC',
        'LA', 'LAC', 'LV', 'MIA', 'MIN', 'NE', 'NO', 'NYG',
        'NYJ', 'PHI', 'PIT', 'SEA', 'SF', 'TB', 'TEN', 'WAS'
    }
    
    # Find the latest season with data
    latest_season = max(teams_by_season.keys()) if teams_by_season else None
    
    if latest_season:
        available = set(teams_by_season[latest_season])
        missing = expected_teams - available
        extra = available - expected_teams
        
        print(f"\n🏈 Team coverage for {latest_season}:")
        print(f"   Expected: {len(expected_teams)} teams")
        print(f"   Available: {len(available)} teams")
        
        if missing:
            print(f"\n   ⚠️  Missing teams: {', '.join(sorted(missing))}")
        else:
            print(f"\n   ✅ All 32 NFL teams have profiles")
        
        if extra:
            print(f"   ℹ️  Extra teams (old abbreviations?): {', '.join(sorted(extra))}")
    
    # Check specific teams for common issues
    print("\n🔍 Checking commonly queried teams:")
    check_teams = ['KC', 'SF', 'PHI', 'DAL', 'BAL', 'BUF', 'LA']
    for team in check_teams:
        key = f"{team}_{latest_season}" if latest_season else None
        if key and key in profiles:
            print(f"   ✅ {team}: Found")
        else:
            print(f"   ❌ {team}: NOT FOUND")
    
    print("\n" + "=" * 60)
    
    return True


def check_player_stats():
    """Check player estimates JSON file."""
    player_path = MODEL_DIR / "player_estimates.json"
    
    print("\n" + "=" * 60)
    print("PLAYER ESTIMATES DIAGNOSTIC")
    print("=" * 60)
    
    if not player_path.exists():
        print(f"\n❌ ERROR: Player estimates file not found at {player_path}")
        return False
    
    print(f"\n✅ Player file found: {player_path}")
    print(f"   File size: {player_path.stat().st_size / 1024:.1f} KB")
    
    with open(player_path, 'r') as f:
        data = json.load(f)
    
    estimates = data.get('player_estimates', {})
    print(f"\n📊 Total player estimates: {len(estimates)}")
    
    # Count by stat type
    by_type = {}
    for pid, est in estimates.items():
        stat_type = est.get('stat_type', 'unknown')
        by_type[stat_type] = by_type.get(stat_type, 0) + 1
    
    print("\n📈 Players by stat type:")
    for stat_type, count in sorted(by_type.items()):
        print(f"   {stat_type}: {count}")
    
    print("\n" + "=" * 60)
    return True


def check_database_connection():
    """Check database connectivity and player names."""
    print("\n" + "=" * 60)
    print("DATABASE DIAGNOSTIC")
    print("=" * 60)
    
    # Try to load .env first
    print("\n🔍 Looking for .env file...")
    load_env()
    
    try:
        import psycopg2
        import pandas as pd
    except ImportError as e:
        print(f"\n⚠️  Missing dependency: {e}")
        return False
    
    db_url = os.getenv("DATABASE_URL")
    
    # Also check common alternative names
    if not db_url:
        db_url = os.getenv("POSTGRES_URL")
    if not db_url:
        db_url = os.getenv("DB_URL")
    
    if not db_url:
        print("\n❌ DATABASE_URL environment variable not set")
        print("   Also checked: POSTGRES_URL, DB_URL")
        print("\n   To fix, either:")
        print("   1. Create a .env file with: DATABASE_URL=postgresql://...")
        print("   2. Set the environment variable directly")
        print("   3. On Windows PowerShell: $env:DATABASE_URL = 'postgresql://...'")
        return False
    
    # Mask password in output
    display_url = db_url
    if '@' in db_url:
        parts = db_url.split('@')
        display_url = parts[0].rsplit(':', 1)[0] + ':***@' + parts[1]
    print(f"\n✅ Database URL found: {display_url}")
    
    try:
        conn = psycopg2.connect(db_url)
        print(f"   ✅ Connection successful")
        
        # Check player names
        query = """
            SELECT COUNT(*) as total,
                   COUNT(player_name) as with_names,
                   COUNT(DISTINCT player_id) as unique_players
            FROM player_season_stats
        """
        df = pd.read_sql(query, conn)
        
        print(f"\n📊 Player stats table:")
        print(f"   Total rows: {df['total'].iloc[0]}")
        print(f"   Rows with names: {df['with_names'].iloc[0]}")
        print(f"   Unique players: {df['unique_players'].iloc[0]}")
        
        # Sample some player names
        sample_query = """
            SELECT player_id, player_name, team, position
            FROM player_season_stats
            WHERE player_name IS NOT NULL
            LIMIT 5
        """
        sample = pd.read_sql(sample_query, conn)
        
        if len(sample) > 0:
            print(f"\n📋 Sample players:")
            for _, row in sample.iterrows():
                print(f"   {row['player_name']} ({row['position']}, {row['team']})")
        else:
            print(f"\n⚠️  No player names found in database!")
            print("   Player rankings will show IDs instead of names.")
            print("   To fix: Re-run data ingestion with roster data.")
        
        conn.close()
        
    except Exception as e:
        print(f"\n❌ Database error: {e}")
        return False
    
    print("\n" + "=" * 60)
    return True


if __name__ == "__main__":
    print("\n🏈 Football Chatbot Diagnostics\n")
    
    check_team_profiles()
    check_player_stats()
    check_database_connection()
    
    print("\n✨ Diagnostics complete!\n")
