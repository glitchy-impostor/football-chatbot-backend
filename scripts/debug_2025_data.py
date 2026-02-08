#!/usr/bin/env python3
"""Debug 2025 data ingestion issue."""

import pandas as pd
from pathlib import Path

# Load the 2025 parquet file
filepath = Path("data/raw/play_by_play_2025.parquet")
if not filepath.exists():
    print(f"File not found: {filepath}")
    exit(1)

df = pd.read_parquet(filepath)
print(f"Total rows: {len(df)}")
print(f"Columns: {len(df.columns)}")

# Check integer columns for overflow
INT_MAX = 2147483647
INT_MIN = -2147483648

suspect_columns = ['play_id', 'game_id', 'old_game_id', 'season', 'week']

for col in suspect_columns:
    if col in df.columns:
        # Convert to numeric, ignoring errors
        numeric_col = pd.to_numeric(df[col], errors='coerce')
        max_val = numeric_col.max()
        min_val = numeric_col.min()
        
        overflow = False
        if pd.notna(max_val) and max_val > INT_MAX:
            overflow = True
        if pd.notna(min_val) and min_val < INT_MIN:
            overflow = True
            
        print(f"\n{col}:")
        print(f"  Type: {df[col].dtype}")
        print(f"  Min: {min_val}")
        print(f"  Max: {max_val}")
        print(f"  Sample: {df[col].head(3).tolist()}")
        if overflow:
            print(f"  ⚠️  OVERFLOW DETECTED - exceeds INTEGER range!")
        else:
            print(f"  ✅ Within INTEGER range")

# Check all numeric columns
print("\n\nChecking ALL columns for large values...")
for col in df.columns:
    try:
        numeric_col = pd.to_numeric(df[col], errors='coerce')
        max_val = numeric_col.max()
        if pd.notna(max_val) and max_val > INT_MAX:
            print(f"⚠️  {col}: max = {max_val} (OVERFLOW)")
    except:
        pass
