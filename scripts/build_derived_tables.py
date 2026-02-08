"""
Build derived/aggregated tables from play-by-play data.

Usage:
    python scripts/build_derived_tables.py
    python scripts/build_derived_tables.py --table team_stats
    python scripts/build_derived_tables.py --season 2023
"""

import psycopg2
import os
import sys
import argparse
from datetime import datetime
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://127.0.0.1:5432/football_analytics")


def build_team_season_stats(conn, season: int = None):
    """Build team_season_stats table."""
    logger.info("Building team_season_stats...")
    
    cursor = conn.cursor()
    
    # Clear existing data (optionally by season)
    if season:
        cursor.execute("DELETE FROM team_season_stats WHERE season = %s", (season,))
    else:
        cursor.execute("DELETE FROM team_season_stats")
    
    season_filter = f"AND p.season = {season}" if season else ""
    
    sql = f"""
    INSERT INTO team_season_stats (
        team, season,
        off_plays, off_epa_total, off_epa_per_play, off_pass_rate, off_success_rate, off_explosive_rate,
        def_plays, def_epa_total, def_epa_per_play, def_success_rate,
        early_down_pass_rate, third_down_conv_rate, red_zone_td_rate
    )
    SELECT 
        o.team,
        o.season,
        o.off_plays,
        o.off_epa_total,
        o.off_epa_per_play,
        o.off_pass_rate,
        o.off_success_rate,
        o.off_explosive_rate,
        d.def_plays,
        d.def_epa_total,
        d.def_epa_per_play,
        d.def_success_rate,
        ed.early_down_pass_rate,
        td.third_down_conv_rate,
        rz.red_zone_td_rate
    FROM (
        SELECT 
            posteam as team,
            season,
            COUNT(*) as off_plays,
            SUM(epa) as off_epa_total,
            AVG(epa) as off_epa_per_play,
            AVG(CASE WHEN pass = 1 THEN 1.0 ELSE 0.0 END) as off_pass_rate,
            AVG(COALESCE(success, 0)::float) as off_success_rate,
            AVG(CASE WHEN yards_gained >= 20 THEN 1.0 ELSE 0.0 END) as off_explosive_rate
        FROM plays p
        WHERE play_type IN ('pass', 'run')
          AND posteam IS NOT NULL
          {season_filter}
        GROUP BY posteam, season
    ) o
    JOIN (
        SELECT 
            defteam as team,
            season,
            COUNT(*) as def_plays,
            SUM(epa) as def_epa_total,
            AVG(epa) as def_epa_per_play,
            AVG(COALESCE(success, 0)::float) as def_success_rate
        FROM plays p
        WHERE play_type IN ('pass', 'run')
          AND defteam IS NOT NULL
          {season_filter}
        GROUP BY defteam, season
    ) d ON o.team = d.team AND o.season = d.season
    LEFT JOIN (
        SELECT 
            posteam as team,
            season,
            AVG(CASE WHEN pass = 1 THEN 1.0 ELSE 0.0 END) as early_down_pass_rate
        FROM plays p
        WHERE play_type IN ('pass', 'run')
          AND down IN (1, 2)
          {season_filter}
        GROUP BY posteam, season
    ) ed ON o.team = ed.team AND o.season = ed.season
    LEFT JOIN (
        SELECT 
            posteam as team,
            season,
            AVG(CASE WHEN first_down = 1 OR touchdown = 1 THEN 1.0 ELSE 0.0 END) as third_down_conv_rate
        FROM plays p
        WHERE down = 3
          AND play_type IN ('pass', 'run')
          {season_filter}
        GROUP BY posteam, season
    ) td ON o.team = td.team AND o.season = td.season
    LEFT JOIN (
        SELECT 
            posteam as team,
            season,
            AVG(CASE WHEN touchdown = 1 THEN 1.0 ELSE 0.0 END) as red_zone_td_rate
        FROM plays p
        WHERE yardline_100 <= 20
          AND play_type IN ('pass', 'run')
          {season_filter}
        GROUP BY posteam, season
    ) rz ON o.team = rz.team AND o.season = rz.season
    """
    
    cursor.execute(sql)
    conn.commit()
    
    cursor.execute("SELECT COUNT(*) FROM team_season_stats")
    count = cursor.fetchone()[0]
    logger.info(f"Built {count} team-season records")
    
    return count


def build_situational_tendencies(conn, season: int = None):
    """Build situational_tendencies table."""
    logger.info("Building situational_tendencies...")
    
    cursor = conn.cursor()
    
    # Clear existing data
    if season:
        cursor.execute("DELETE FROM situational_tendencies WHERE season = %s", (season,))
    else:
        cursor.execute("DELETE FROM situational_tendencies")
    
    season_filter = f"AND season = {season}" if season else ""
    
    # Team-specific tendencies
    sql_teams = f"""
    INSERT INTO situational_tendencies (
        team, season, down, distance_bucket, field_zone, score_bucket,
        sample_size, pass_rate, run_rate, epa_avg, success_rate, play_type_dist
    )
    SELECT 
        posteam as team,
        season,
        down,
        CASE 
            WHEN ydstogo <= 3 THEN 'short'
            WHEN ydstogo <= 7 THEN 'medium'
            ELSE 'long'
        END as distance_bucket,
        CASE 
            WHEN yardline_100 > 80 THEN 'own_deep'
            WHEN yardline_100 > 50 THEN 'own_territory'
            WHEN yardline_100 > 20 THEN 'opp_territory'
            ELSE 'red_zone'
        END as field_zone,
        CASE 
            WHEN score_differential <= -14 THEN 'losing_big'
            WHEN score_differential < 0 THEN 'losing'
            WHEN score_differential = 0 THEN 'tied'
            WHEN score_differential <= 14 THEN 'winning'
            ELSE 'winning_big'
        END as score_bucket,
        COUNT(*) as sample_size,
        AVG(CASE WHEN pass = 1 THEN 1.0 ELSE 0.0 END) as pass_rate,
        AVG(CASE WHEN rush = 1 THEN 1.0 ELSE 0.0 END) as run_rate,
        AVG(epa) as epa_avg,
        AVG(COALESCE(success, 0)::float) as success_rate,
        jsonb_build_object(
            'pass', SUM(CASE WHEN pass = 1 THEN 1 ELSE 0 END),
            'rush', SUM(CASE WHEN rush = 1 THEN 1 ELSE 0 END)
        ) as play_type_dist
    FROM plays
    WHERE play_type IN ('pass', 'run')
      AND down IS NOT NULL
      AND down BETWEEN 1 AND 4
      AND posteam IS NOT NULL
      {season_filter}
    GROUP BY 
        posteam, season, down,
        CASE 
            WHEN ydstogo <= 3 THEN 'short'
            WHEN ydstogo <= 7 THEN 'medium'
            ELSE 'long'
        END,
        CASE 
            WHEN yardline_100 > 80 THEN 'own_deep'
            WHEN yardline_100 > 50 THEN 'own_territory'
            WHEN yardline_100 > 20 THEN 'opp_territory'
            ELSE 'red_zone'
        END,
        CASE 
            WHEN score_differential <= -14 THEN 'losing_big'
            WHEN score_differential < 0 THEN 'losing'
            WHEN score_differential = 0 THEN 'tied'
            WHEN score_differential <= 14 THEN 'winning'
            ELSE 'winning_big'
        END
    HAVING COUNT(*) >= 10
    """
    
    cursor.execute(sql_teams)
    team_count = cursor.rowcount
    
    # League averages (team = NULL)
    sql_league = f"""
    INSERT INTO situational_tendencies (
        team, season, down, distance_bucket, field_zone, score_bucket,
        sample_size, pass_rate, run_rate, epa_avg, success_rate, play_type_dist
    )
    SELECT 
        NULL as team,
        season,
        down,
        CASE 
            WHEN ydstogo <= 3 THEN 'short'
            WHEN ydstogo <= 7 THEN 'medium'
            ELSE 'long'
        END as distance_bucket,
        CASE 
            WHEN yardline_100 > 80 THEN 'own_deep'
            WHEN yardline_100 > 50 THEN 'own_territory'
            WHEN yardline_100 > 20 THEN 'opp_territory'
            ELSE 'red_zone'
        END as field_zone,
        CASE 
            WHEN score_differential <= -14 THEN 'losing_big'
            WHEN score_differential < 0 THEN 'losing'
            WHEN score_differential = 0 THEN 'tied'
            WHEN score_differential <= 14 THEN 'winning'
            ELSE 'winning_big'
        END as score_bucket,
        COUNT(*) as sample_size,
        AVG(CASE WHEN pass = 1 THEN 1.0 ELSE 0.0 END) as pass_rate,
        AVG(CASE WHEN rush = 1 THEN 1.0 ELSE 0.0 END) as run_rate,
        AVG(epa) as epa_avg,
        AVG(COALESCE(success, 0)::float) as success_rate,
        jsonb_build_object(
            'pass', SUM(CASE WHEN pass = 1 THEN 1 ELSE 0 END),
            'rush', SUM(CASE WHEN rush = 1 THEN 1 ELSE 0 END)
        ) as play_type_dist
    FROM plays
    WHERE play_type IN ('pass', 'run')
      AND down IS NOT NULL
      AND down BETWEEN 1 AND 4
      {season_filter}
    GROUP BY 
        season, down,
        CASE 
            WHEN ydstogo <= 3 THEN 'short'
            WHEN ydstogo <= 7 THEN 'medium'
            ELSE 'long'
        END,
        CASE 
            WHEN yardline_100 > 80 THEN 'own_deep'
            WHEN yardline_100 > 50 THEN 'own_territory'
            WHEN yardline_100 > 20 THEN 'opp_territory'
            ELSE 'red_zone'
        END,
        CASE 
            WHEN score_differential <= -14 THEN 'losing_big'
            WHEN score_differential < 0 THEN 'losing'
            WHEN score_differential = 0 THEN 'tied'
            WHEN score_differential <= 14 THEN 'winning'
            ELSE 'winning_big'
        END
    """
    
    cursor.execute(sql_league)
    league_count = cursor.rowcount
    
    conn.commit()
    
    cursor.execute("SELECT COUNT(*) FROM situational_tendencies")
    total = cursor.fetchone()[0]
    logger.info(f"Built {total} situational tendency records ({team_count} team, {league_count} league avg)")
    
    return total


def build_player_season_stats(conn, season: int = None):
    """Build player_season_stats table."""
    logger.info("Building player_season_stats...")
    
    cursor = conn.cursor()
    
    # Clear existing data
    if season:
        cursor.execute("DELETE FROM player_season_stats WHERE season = %s", (season,))
    else:
        cursor.execute("DELETE FROM player_season_stats")
    
    season_filter = f"AND season = {season}" if season else ""
    
    # Passing stats
    sql_passing = f"""
    INSERT INTO player_season_stats (
        player_id, season, pass_attempts, completions, pass_yards, pass_td, interceptions, pass_epa
    )
    SELECT 
        passer_player_id as player_id,
        season,
        COUNT(*) as pass_attempts,
        SUM(CASE WHEN yards_gained > 0 AND play_type = 'pass' THEN 1 ELSE 0 END) as completions,
        SUM(CASE WHEN play_type = 'pass' THEN COALESCE(yards_gained, 0) ELSE 0 END) as pass_yards,
        SUM(CASE WHEN touchdown = 1 AND play_type = 'pass' THEN 1 ELSE 0 END) as pass_td,
        SUM(COALESCE(interception, 0)) as interceptions,
        SUM(CASE WHEN play_type = 'pass' THEN COALESCE(epa, 0) ELSE 0 END) as pass_epa
    FROM plays
    WHERE passer_player_id IS NOT NULL
      AND play_type = 'pass'
      {season_filter}
    GROUP BY passer_player_id, season
    ON CONFLICT (player_id, season) DO UPDATE SET
        pass_attempts = EXCLUDED.pass_attempts,
        completions = EXCLUDED.completions,
        pass_yards = EXCLUDED.pass_yards,
        pass_td = EXCLUDED.pass_td,
        interceptions = EXCLUDED.interceptions,
        pass_epa = EXCLUDED.pass_epa,
        updated_at = CURRENT_TIMESTAMP
    """
    
    cursor.execute(sql_passing)
    pass_count = cursor.rowcount
    
    # Rushing stats
    sql_rushing = f"""
    INSERT INTO player_season_stats (
        player_id, season, rush_attempts, rush_yards, rush_td, rush_epa
    )
    SELECT 
        rusher_player_id as player_id,
        season,
        COUNT(*) as rush_attempts,
        SUM(COALESCE(yards_gained, 0)) as rush_yards,
        SUM(CASE WHEN touchdown = 1 THEN 1 ELSE 0 END) as rush_td,
        SUM(COALESCE(epa, 0)) as rush_epa
    FROM plays
    WHERE rusher_player_id IS NOT NULL
      AND play_type = 'run'
      {season_filter}
    GROUP BY rusher_player_id, season
    ON CONFLICT (player_id, season) DO UPDATE SET
        rush_attempts = EXCLUDED.rush_attempts,
        rush_yards = EXCLUDED.rush_yards,
        rush_td = EXCLUDED.rush_td,
        rush_epa = EXCLUDED.rush_epa,
        updated_at = CURRENT_TIMESTAMP
    """
    
    cursor.execute(sql_rushing)
    rush_count = cursor.rowcount
    
    # Receiving stats
    sql_receiving = f"""
    INSERT INTO player_season_stats (
        player_id, season, targets, receptions, rec_yards, rec_td, rec_epa
    )
    SELECT 
        receiver_player_id as player_id,
        season,
        COUNT(*) as targets,
        SUM(CASE WHEN yards_gained > 0 THEN 1 ELSE 0 END) as receptions,
        SUM(COALESCE(yards_gained, 0)) as rec_yards,
        SUM(CASE WHEN touchdown = 1 THEN 1 ELSE 0 END) as rec_td,
        SUM(COALESCE(epa, 0)) as rec_epa
    FROM plays
    WHERE receiver_player_id IS NOT NULL
      AND play_type = 'pass'
      {season_filter}
    GROUP BY receiver_player_id, season
    ON CONFLICT (player_id, season) DO UPDATE SET
        targets = EXCLUDED.targets,
        receptions = EXCLUDED.receptions,
        rec_yards = EXCLUDED.rec_yards,
        rec_td = EXCLUDED.rec_td,
        rec_epa = EXCLUDED.rec_epa,
        updated_at = CURRENT_TIMESTAMP
    """
    
    cursor.execute(sql_receiving)
    rec_count = cursor.rowcount
    
    conn.commit()
    
    cursor.execute("SELECT COUNT(*) FROM player_season_stats")
    total = cursor.fetchone()[0]
    logger.info(f"Built {total} player-season records")
    
    return total


def main():
    parser = argparse.ArgumentParser(description='Build derived tables')
    parser.add_argument('--table', choices=['team_stats', 'tendencies', 'player_stats', 'all'],
                        default='all', help='Which table to build')
    parser.add_argument('--season', type=int, help='Build for specific season only')
    args = parser.parse_args()
    
    logger.info("=" * 50)
    logger.info("Building Derived Tables")
    logger.info("=" * 50)
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
        logger.info("Connected to database")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        sys.exit(1)
    
    try:
        if args.table in ['team_stats', 'all']:
            build_team_season_stats(conn, args.season)
        
        if args.table in ['tendencies', 'all']:
            build_situational_tendencies(conn, args.season)
        
        if args.table in ['player_stats', 'all']:
            build_player_season_stats(conn, args.season)
        
        logger.info("")
        logger.info("All derived tables built successfully!")
        
    except Exception as e:
        logger.error(f"Error building derived tables: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
