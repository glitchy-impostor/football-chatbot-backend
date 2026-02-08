#!/usr/bin/env python3
"""
Phase 1 Validation Script
Run this to verify Phase 1 is complete and ready for Phase 2.

Usage:
    python tests/phase1/run_phase1_validation.py
"""

import psycopg2
import os
import sys
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://127.0.0.1:5432/football_analytics")

# Store all checks
CHECKS = []


def check(name):
    """Decorator to register a check."""
    def decorator(func):
        CHECKS.append((name, func))
        return func
    return decorator


# =============================================================================
# DATABASE CHECKS
# =============================================================================

@check("Database Connection")
def check_db_connection(cursor):
    cursor.execute("SELECT 1")
    return cursor.fetchone()[0] == 1


@check("Plays Table Exists")
def check_plays_table(cursor):
    cursor.execute("""
        SELECT COUNT(*) FROM information_schema.tables 
        WHERE table_name = 'plays'
    """)
    return cursor.fetchone()[0] == 1


@check("All Required Tables Exist")
def check_all_tables(cursor):
    required = ['plays', 'games', 'rosters', 'team_season_stats', 
                'situational_tendencies', 'player_season_stats']
    cursor.execute("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'public'
    """)
    existing = [row[0] for row in cursor.fetchall()]
    missing = [t for t in required if t not in existing]
    return len(missing) == 0, f"Missing: {missing}" if missing else "All present"


# =============================================================================
# DATA VOLUME CHECKS
# =============================================================================

@check("Plays Table Has Data (>400k rows)")
def check_plays_data(cursor):
    cursor.execute("SELECT COUNT(*) FROM plays")
    count = cursor.fetchone()[0]
    return count >= 400000, f"Found {count:,} plays"


@check("All Seasons Present (2016-2024)")
def check_seasons(cursor):
    cursor.execute("SELECT DISTINCT season FROM plays ORDER BY season")
    seasons = [row[0] for row in cursor.fetchall()]
    expected = list(range(2016, 2025))
    missing = [s for s in expected if s not in seasons]
    return len(missing) == 0, f"Missing: {missing}" if missing else f"All present: {seasons}"


@check("32 Teams Present (2023 season)")
def check_teams(cursor):
    cursor.execute("""
        SELECT COUNT(DISTINCT posteam) FROM plays 
        WHERE season = 2023 AND posteam IS NOT NULL
    """)
    count = cursor.fetchone()[0]
    return count == 32, f"Found {count} teams"


@check("Reasonable Plays Per Season")
def check_plays_per_season(cursor):
    cursor.execute("""
        SELECT season, COUNT(*) as plays
        FROM plays
        GROUP BY season
        ORDER BY season
    """)
    results = cursor.fetchall()
    issues = []
    for season, plays in results:
        if plays < 40000:
            issues.append(f"{season}: {plays} (too few)")
    return len(issues) == 0, f"Issues: {issues}" if issues else "All seasons OK"


# =============================================================================
# DATA QUALITY CHECKS
# =============================================================================

@check("EPA Values Reasonable (-15 to 15)")
def check_epa(cursor):
    cursor.execute("SELECT MIN(epa), MAX(epa), AVG(epa) FROM plays WHERE epa IS NOT NULL")
    min_epa, max_epa, avg_epa = cursor.fetchone()
    ok = min_epa > -15 and max_epa < 15 and -0.5 < avg_epa < 0.5
    return ok, f"Range: [{min_epa:.2f}, {max_epa:.2f}], Avg: {avg_epa:.3f}"


@check("No Duplicate Plays")
def check_duplicates(cursor):
    cursor.execute("""
        SELECT COUNT(*) FROM (
            SELECT game_id, play_id FROM plays 
            GROUP BY game_id, play_id HAVING COUNT(*) > 1
        ) dups
    """)
    count = cursor.fetchone()[0]
    return count == 0, f"Found {count} duplicates" if count > 0 else "No duplicates"


@check("Personnel Data Available (>80% for 2016+)")
def check_personnel(cursor):
    cursor.execute("""
        SELECT 
            COUNT(offense_personnel)::float / NULLIF(COUNT(*), 0)
        FROM plays WHERE season >= 2016
    """)
    ratio = cursor.fetchone()[0] or 0
    return ratio >= 0.8, f"{ratio:.1%} have personnel data"


@check("Play Type Distribution Reasonable")
def check_play_types(cursor):
    cursor.execute("""
        SELECT play_type, COUNT(*) as cnt
        FROM plays
        WHERE play_type IS NOT NULL
        GROUP BY play_type
        ORDER BY cnt DESC
    """)
    results = dict(cursor.fetchall())
    pass_plays = results.get('pass', 0)
    run_plays = results.get('run', 0)
    total = pass_plays + run_plays
    if total == 0:
        return False, "No pass/run plays found"
    pass_rate = pass_plays / total
    return 0.5 < pass_rate < 0.7, f"Pass rate: {pass_rate:.1%}"


# =============================================================================
# DERIVED TABLE CHECKS
# =============================================================================

@check("Team Season Stats Populated (>250 records)")
def check_team_stats(cursor):
    cursor.execute("SELECT COUNT(*) FROM team_season_stats")
    count = cursor.fetchone()[0]
    return count >= 250, f"Found {count} records"


@check("Team Stats Values Reasonable")
def check_team_stats_values(cursor):
    cursor.execute("""
        SELECT MIN(off_epa_per_play), MAX(off_epa_per_play)
        FROM team_season_stats
    """)
    min_epa, max_epa = cursor.fetchone()
    if min_epa is None:
        return False, "No data"
    ok = -0.5 < min_epa < 0 and 0 < max_epa < 0.5
    return ok, f"Team EPA range: [{min_epa:.3f}, {max_epa:.3f}]"


@check("Situational Tendencies Populated (>5000 records)")
def check_tendencies(cursor):
    cursor.execute("SELECT COUNT(*) FROM situational_tendencies")
    count = cursor.fetchone()[0]
    return count >= 5000, f"Found {count} records"


@check("League Averages Exist (team IS NULL)")
def check_league_avg(cursor):
    cursor.execute("SELECT COUNT(*) FROM situational_tendencies WHERE team IS NULL")
    count = cursor.fetchone()[0]
    return count >= 100, f"Found {count} league avg records"


@check("Player Stats Populated (>3000 records)")
def check_player_stats(cursor):
    cursor.execute("SELECT COUNT(*) FROM player_season_stats")
    count = cursor.fetchone()[0]
    return count >= 3000, f"Found {count} records"


@check("Pass Rate Values Valid (0-1)")
def check_pass_rates(cursor):
    cursor.execute("""
        SELECT MIN(pass_rate), MAX(pass_rate)
        FROM situational_tendencies
        WHERE pass_rate IS NOT NULL
    """)
    min_rate, max_rate = cursor.fetchone()
    if min_rate is None:
        return False, "No data"
    ok = min_rate >= 0 and max_rate <= 1
    return ok, f"Pass rate range: [{min_rate:.3f}, {max_rate:.3f}]"


# =============================================================================
# PERFORMANCE CHECKS
# =============================================================================

@check("Indexes Created (>5 on plays table)")
def check_indexes(cursor):
    cursor.execute("SELECT COUNT(*) FROM pg_indexes WHERE tablename = 'plays'")
    count = cursor.fetchone()[0]
    return count >= 5, f"Found {count} indexes"


@check("Query Performance: Team Profile (<100ms)")
def check_query_performance(cursor):
    import time
    start = time.time()
    cursor.execute("""
        SELECT team, season, off_epa_per_play, def_epa_per_play
        FROM team_season_stats
        WHERE team = 'KC' AND season = 2023
    """)
    cursor.fetchone()
    elapsed = time.time() - start
    return elapsed < 0.1, f"Query took {elapsed*1000:.1f}ms"


# =============================================================================
# RUNNER
# =============================================================================

def run_validation():
    """Run all validation checks."""
    print("=" * 70)
    print("PHASE 1 VALIDATION - Football Analytics Chatbot")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()
    
    # Connect to database
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        print(f"✅ Connected to database")
        print(f"   URL: {DATABASE_URL[:50]}...")
        print()
    except Exception as e:
        print(f"❌ Cannot connect to database: {e}")
        print()
        print("Please check:")
        print("  1. PostgreSQL is running")
        print("  2. DATABASE_URL environment variable is set correctly")
        print("  3. Database 'football_analytics' exists")
        return False
    
    passed = 0
    failed = 0
    
    print("-" * 70)
    print("Running checks...")
    print("-" * 70)
    print()
    
    for name, check_func in CHECKS:
        try:
            result = check_func(cursor)
            if isinstance(result, tuple):
                ok, detail = result
            else:
                ok, detail = result, ""
            
            if ok:
                status = "✅ PASS"
                passed += 1
            else:
                status = "❌ FAIL"
                failed += 1
            
            detail_str = f" → {detail}" if detail else ""
            print(f"  {status} | {name}{detail_str}")
            
        except Exception as e:
            print(f"  ❌ FAIL | {name} → Error: {e}")
            failed += 1
    
    cursor.close()
    conn.close()
    
    print()
    print("=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)
    
    if failed == 0:
        print()
        print("🎉 PHASE 1 COMPLETE!")
        print()
        print("You're ready to proceed to Phase 2: Core Models")
        print()
        print("Next steps:")
        print("  1. Review the implementation plan for Phase 2")
        print("  2. Set up the model training environment")
        print("  3. Start building the EPA prediction model")
        print()
        return True
    else:
        print()
        print("⚠️  Phase 1 has failures. Please fix before proceeding.")
        print()
        print("Common fixes:")
        print("  - If data is missing: Run 'python scripts/ingest_pbp.py'")
        print("  - If derived tables empty: Run 'python scripts/build_derived_tables.py'")
        print("  - If indexes missing: Run 'psql $DATABASE_URL -f database/indexes.sql'")
        print()
        return False


if __name__ == "__main__":
    success = run_validation()
    sys.exit(0 if success else 1)
