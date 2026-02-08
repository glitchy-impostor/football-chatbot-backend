"""
Play-by-play data ingestion from nflfastR.
Downloads parquet files and loads into PostgreSQL.

Usage:
    python scripts/ingest_pbp.py
    python scripts/ingest_pbp.py --seasons 2023 2024
    python scripts/ingest_pbp.py --force  # Re-download existing files
"""

import math
import pandas as pd
import numpy as np
import psycopg2
from psycopg2.extras import execute_values
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
NFLFASTR_PBP_URL = "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.parquet"
DEFAULT_SEASONS = list(range(2016, 2025))  # 2016-2024

# Load from environment or .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://127.0.0.1:5432/football_analytics")

# Columns to keep from nflfastR (mapped to our schema)
COLUMN_MAPPING = {
    'game_id': 'game_id',
    'play_id': 'play_id',
    'season': 'season',
    'week': 'week',
    'season_type': 'season_type',
    'home_team': 'home_team',
    'away_team': 'away_team',
    'posteam': 'posteam',
    'defteam': 'defteam',
    'qtr': 'quarter',
    'half_seconds_remaining': 'time_remaining_half',
    'down': 'down',
    'ydstogo': 'ydstogo',
    'yardline_100': 'yardline_100',
    'posteam_score': 'posteam_score',
    'defteam_score': 'defteam_score',
    'score_differential': 'score_differential',
    'play_type': 'play_type',
    'pass': 'pass',
    'rush': 'rush',
    'yards_gained': 'yards_gained',
    'offense_personnel': 'offense_personnel',
    'defense_personnel': 'defense_personnel',
    'defenders_in_box': 'defenders_in_box',
    'shotgun': 'shotgun',
    'no_huddle': 'no_huddle',
    'epa': 'epa',
    'wpa': 'wpa',
    'success': 'success',
    'touchdown': 'touchdown',
    'interception': 'interception',
    'fumble': 'fumble',
    'first_down': 'first_down',
    'passer_player_id': 'passer_player_id',
    'rusher_player_id': 'rusher_player_id',
    'receiver_player_id': 'receiver_player_id',
}


def download_season(season: int, data_dir: Path, force: bool = False) -> Path:
    """Download a single season's play-by-play data."""
    url = NFLFASTR_PBP_URL.format(season=season)
    filepath = data_dir / f"play_by_play_{season}.parquet"
    
    if filepath.exists() and not force:
        logger.info(f"Season {season} already downloaded, skipping (use --force to re-download)")
        return filepath
    
    logger.info(f"Downloading season {season} from {url}...")
    
    try:
        df = pd.read_parquet(url)
        df.to_parquet(filepath)
        logger.info(f"Downloaded {len(df):,} plays for {season}")
        return filepath
    except Exception as e:
        logger.error(f"Failed to download season {season}: {e}")
        raise


def process_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Process and clean the dataframe for insertion."""
    # Select and rename columns
    available_cols = {k: v for k, v in COLUMN_MAPPING.items() if k in df.columns}
    df = df[list(available_cols.keys())].copy()
    df = df.rename(columns=available_cols)
    
    # Filter to actual plays
    valid_play_types = ['pass', 'run', 'punt', 'field_goal', 'kickoff', 
                        'extra_point', 'qb_kneel', 'qb_spike']
    df = df[df['play_type'].isin(valid_play_types)].copy()
    
    # Define column types
    int_columns = ['season', 'week', 'quarter', 'down', 'ydstogo', 
                   'yardline_100', 'posteam_score', 'defteam_score', 'score_differential',
                   'pass', 'rush', 'yards_gained', 'defenders_in_box', 'shotgun', 
                   'no_huddle', 'success', 'touchdown', 'interception', 'fumble', 'first_down',
                   'time_remaining_half']
    
    bigint_columns = ['play_id']
    float_columns = ['epa', 'wpa']
    string_columns = ['game_id', 'season_type', 'home_team', 'away_team', 'posteam', 
                      'defteam', 'play_type', 'offense_personnel', 'defense_personnel',
                      'passer_player_id', 'rusher_player_id', 'receiver_player_id']
    
    INT_MAX = 2147483647
    INT_MIN = -2147483648
    
    def to_python_int(x):
        """Convert to Python int or None."""
        if x is None:
            return None
        if isinstance(x, float):
            if math.isnan(x) or math.isinf(x):
                return None
            x = int(x)
        if isinstance(x, (np.integer, np.floating)):
            if np.isnan(x) or np.isinf(x):
                return None
            x = int(x)
        if isinstance(x, int):
            if INT_MIN <= x <= INT_MAX:
                return x
            return None
        return None
    
    def to_python_bigint(x):
        """Convert to Python int (bigint) or None."""
        if x is None:
            return None
        if isinstance(x, float):
            if math.isnan(x) or math.isinf(x):
                return None
            return int(x)
        if isinstance(x, (np.integer, np.floating)):
            if np.isnan(x) or np.isinf(x):
                return None
            return int(x)
        if isinstance(x, int):
            return x
        return None
    
    def to_python_float(x):
        """Convert to Python float or None."""
        if x is None:
            return None
        if isinstance(x, (float, np.floating)):
            if math.isnan(x) or math.isinf(x):
                return None
            return float(x)
        if isinstance(x, (int, np.integer)):
            return float(x)
        return None
    
    def to_python_str(x):
        """Convert to Python str or None."""
        if x is None:
            return None
        if isinstance(x, float) and math.isnan(x):
            return None
        if isinstance(x, (np.floating,)) and np.isnan(x):
            return None
        if pd.isna(x):
            return None
        return str(x)
    
    # Apply conversions
    for col in int_columns:
        if col in df.columns:
            df[col] = df[col].apply(to_python_int)
    
    for col in bigint_columns:
        if col in df.columns:
            df[col] = df[col].apply(to_python_bigint)
    
    for col in float_columns:
        if col in df.columns:
            df[col] = df[col].apply(to_python_float)
    
    for col in string_columns:
        if col in df.columns:
            df[col] = df[col].apply(to_python_str)
    
    # Convert DataFrame to list of dicts, then back - this forces Python native types
    records = df.to_dict('records')
    df = pd.DataFrame(records)
    
    return df


def load_season_to_db(filepath: Path, conn) -> int:
    """Load a season's data into the database."""
    logger.info(f"Loading {filepath.name}...")
    
    df = pd.read_parquet(filepath)
    df = process_dataframe(df)
    
    if len(df) == 0:
        logger.warning(f"No valid plays found in {filepath.name}")
        return 0
    
    # Debug: Check ALL values for integer overflow BEFORE insert
    INT_MAX = 2147483647
    INT_MIN = -2147483648
    
    # Columns that are BIGINT in schema (safe to have large values)
    bigint_columns_in_schema = ['play_id']
    
    logger.info("Checking for integer overflow...")
    problem_columns = []
    
    for col in df.columns:
        if col in bigint_columns_in_schema:
            continue  # Skip columns that are BIGINT in schema
        
        # Get numeric values only
        try:
            numeric_vals = pd.to_numeric(df[col], errors='coerce').dropna()
            if len(numeric_vals) == 0:
                continue
                
            max_val = numeric_vals.max()
            min_val = numeric_vals.min()
            
            if max_val > INT_MAX:
                problem_columns.append((col, 'max', max_val))
                logger.warning(f"⚠️  Column '{col}' max={max_val} exceeds INTEGER")
            if min_val < INT_MIN:
                problem_columns.append((col, 'min', min_val))
                logger.warning(f"⚠️  Column '{col}' min={min_val} exceeds INTEGER")
        except Exception as e:
            pass
    
    if problem_columns:
        logger.error(f"❌ Found {len(problem_columns)} columns with INTEGER overflow:")
        for col, issue, val in problem_columns:
            logger.error(f"   - {col}: {issue}={val:,.0f}")
        logger.error("\nTO FIX:")
        logger.error("  1. Add column to bigint_columns in process_dataframe()")
        logger.error("  2. Run: ALTER TABLE plays ALTER COLUMN <name> TYPE BIGINT;")
        raise ValueError(f"Integer overflow: {[c[0] for c in problem_columns]}")
    
    logger.info(f"Inserting {len(df):,} plays...")
    
    cursor = conn.cursor()
    
    # Get column names in correct order
    columns = list(df.columns)
    
    # Build insert SQL
    placeholders = ', '.join(['%s'] * len(columns))
    insert_sql = f"""
        INSERT INTO plays ({', '.join(columns)})
        VALUES ({placeholders})
        ON CONFLICT (game_id, play_id) DO NOTHING
    """
    
    # Convert to list of tuples with PYTHON NATIVE TYPES
    # This is critical - psycopg2 can't handle numpy types
    def to_native(val):
        """Convert any value to Python native type."""
        if val is None:
            return None
        # Handle numpy/pandas NA types
        if isinstance(val, (float, np.floating)):
            if math.isnan(val) or math.isinf(val):
                return None
            return float(val)
        if isinstance(val, (np.integer,)):
            return int(val)
        if isinstance(val, (np.bool_,)):
            return bool(val)
        if pd.isna(val):
            return None
        return val
    
    values = []
    for _, row in df.iterrows():
        values.append(tuple(to_native(v) for v in row))
    
    # Insert in batches
    batch_size = 5000
    inserted = 0
    
    for i in range(0, len(values), batch_size):
        batch = values[i:i + batch_size]
        cursor.executemany(insert_sql, batch)
        conn.commit()
        inserted += cursor.rowcount
        
        if (i + batch_size) % 25000 == 0:
            logger.info(f"  Processed {i + batch_size:,} plays...")
    
    logger.info(f"Inserted {inserted:,} new plays from {filepath.name}")
    
    return inserted


def log_refresh(conn, refresh_type: str, season: int, rows: int, status: str, error: str = None):
    """Log the data refresh to the database."""
    try:
        # Rollback any failed transaction first
        conn.rollback()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO data_refresh_log (refresh_type, season, rows_affected, status, error_message, completed_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (refresh_type, season, rows, status, error, datetime.now()))
        conn.commit()
    except Exception as e:
        logger.warning(f"Could not log refresh: {e}")
        conn.rollback()
    conn.commit()


def main():
    parser = argparse.ArgumentParser(description='Ingest nflfastR play-by-play data')
    parser.add_argument('--seasons', nargs='+', type=int, default=DEFAULT_SEASONS,
                        help='Seasons to ingest (default: 2016-2024)')
    parser.add_argument('--force', action='store_true',
                        help='Force re-download of existing files')
    parser.add_argument('--data-dir', type=str, default='data/raw',
                        help='Directory to store downloaded files')
    args = parser.parse_args()
    
    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info("=" * 50)
    logger.info("nflfastR Data Ingestion")
    logger.info("=" * 50)
    logger.info(f"Seasons: {args.seasons}")
    logger.info(f"Data directory: {data_dir}")
    logger.info("")
    
    # Connect to database
    try:
        conn = psycopg2.connect(DATABASE_URL)
        logger.info("Connected to database")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        sys.exit(1)
    
    total_inserted = 0
    successful_seasons = []
    failed_seasons = []
    
    for season in args.seasons:
        try:
            filepath = download_season(season, data_dir, args.force)
            inserted = load_season_to_db(filepath, conn)
            total_inserted += inserted
            successful_seasons.append(season)
            log_refresh(conn, 'pbp_ingest', season, inserted, 'success')
        except Exception as e:
            logger.error(f"Error processing season {season}: {e}")
            conn.rollback()  # Rollback failed transaction
            failed_seasons.append(season)
            log_refresh(conn, 'pbp_ingest', season, 0, 'failed', str(e))
            continue
    
    conn.close()
    
    logger.info("")
    logger.info("=" * 50)
    logger.info("Ingestion Complete")
    logger.info("=" * 50)
    logger.info(f"Total plays inserted: {total_inserted:,}")
    logger.info(f"Successful seasons: {successful_seasons}")
    if failed_seasons:
        logger.warning(f"Failed seasons: {failed_seasons}")
    
    return len(failed_seasons) == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)