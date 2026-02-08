#!/usr/bin/env python3
"""
Debug script to find EXACTLY which row/column causes the overflow error.
Inserts rows one-by-one to find the culprit.
"""

import os
import sys
import math
import pandas as pd
import numpy as np
import psycopg2
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.ingest_pbp import process_dataframe, COLUMN_MAPPING

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:password@127.0.0.1:5432/football_analytics')

def find_overflow():
    filepath = Path("data/raw/play_by_play_2025.parquet")
    if not filepath.exists():
        print(f"File not found: {filepath}")
        return
    
    print(f"Loading {filepath}...")
    df = pd.read_parquet(filepath)
    df = process_dataframe(df)
    print(f"Processed {len(df):,} plays")
    
    # Check for NaN values AFTER processing
    print("\nChecking for NaN/None values after processing...")
    print("=" * 60)
    
    # Integer columns in schema
    int_columns = ['season', 'week', 'quarter', 'down', 'ydstogo', 
                   'yardline_100', 'posteam_score', 'defteam_score', 'score_differential',
                   'pass', 'rush', 'yards_gained', 'defenders_in_box', 'shotgun', 
                   'no_huddle', 'success', 'touchdown', 'interception', 'fumble', 'first_down',
                   'time_remaining_half']
    
    for col in int_columns:
        if col not in df.columns:
            continue
        
        # Check for problematic values
        for idx, val in enumerate(df[col]):
            if val is not None:
                # Check if it's a float NaN
                if isinstance(val, float):
                    if np.isnan(val) or np.isinf(val):
                        print(f"❌ {col}[{idx}] = {val} (float NaN/inf)")
                        print(f"   Type: {type(val)}")
                        break
                # Check if it's outside integer range
                if isinstance(val, (int, float, np.integer, np.floating)):
                    if val > 2147483647 or val < -2147483648:
                        print(f"❌ {col}[{idx}] = {val} (overflow)")
                        break
        else:
            # Count None values
            none_count = sum(1 for v in df[col] if v is None)
            nan_count = sum(1 for v in df[col] if isinstance(v, float) and np.isnan(v))
            print(f"✓ {col}: {none_count} None values, {nan_count} NaN values")
    
    # Also check the first few rows
    print("\n\nFirst 3 rows after processing:")
    print("=" * 60)
    for idx in range(min(3, len(df))):
        print(f"\nRow {idx}:")
        for col in df.columns:
            val = df.iloc[idx][col]
            val_type = type(val).__name__
            is_nan = isinstance(val, float) and np.isnan(val) if val is not None else False
            flag = " ⚠️ NaN!" if is_nan else ""
            print(f"  {col}: {val} ({val_type}){flag}")
    
    # Connect to database
    print("\n\nTrying to insert first row...")
    print("=" * 60)
    
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    # Build insert SQL
    columns = list(df.columns)
    placeholders = ', '.join(['%s'] * len(columns))
    insert_sql = f"""
        INSERT INTO plays ({', '.join(columns)})
        VALUES ({placeholders})
        ON CONFLICT (game_id, play_id) DO NOTHING
    """
    
    # Convert to Python native types at insertion time
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
    
    # Get first row and convert
    row = df.iloc[0]
    values = tuple(to_native(v) for v in row)
    
    # Print values being inserted
    print("Values being inserted (after native conversion):")
    for col_name, val in zip(columns, values):
        val_type = type(val).__name__
        print(f"  {col_name}: {val} ({val_type})")
    
    try:
        cursor.execute(insert_sql, values)
        conn.commit()
        print("\n✅ First row inserted successfully!")
    except psycopg2.Error as e:
        print(f"\n❌ INSERT FAILED!")
        print(f"   Error: {e}")
        conn.rollback()
    
    cursor.close()
    conn.close()


if __name__ == "__main__":
    find_overflow()