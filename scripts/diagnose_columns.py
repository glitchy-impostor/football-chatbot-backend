"""
Comprehensive diagnostic - check ALL columns in the parquet file.
"""

import pandas as pd
import numpy as np
from pathlib import Path

# Load one season
filepath = Path("data/raw/play_by_play_2016.parquet")
df = pd.read_parquet(filepath)

INT_LIMIT = 2147483647  # PostgreSQL INTEGER max

print(f"Total columns in parquet: {len(df.columns)}")
print(f"Total rows: {len(df)}")
print()
print("Scanning ALL columns for out-of-range values...")
print("=" * 70)

problems = []

for col in df.columns:
    dtype = df[col].dtype
    dtype_str = str(dtype).lower()
    
    # Skip obvious string columns
    if 'string' in dtype_str or 'object' in dtype_str or 'category' in dtype_str:
        continue
    
    # Check numeric columns
    try:
        values = df[col].dropna()
        
        if len(values) == 0:
            continue
        
        # Convert to float for comparison
        numeric_vals = pd.to_numeric(values, errors='coerce').dropna()
        
        if len(numeric_vals) == 0:
            continue
        
        min_val = numeric_vals.min()
        max_val = numeric_vals.max()
        
        # Check if any values exceed integer limits
        if max_val > INT_LIMIT or min_val < -INT_LIMIT:
            print(f"🚨 {col}")
            print(f"   dtype: {dtype}")
            print(f"   min: {min_val}")
            print(f"   max: {max_val}")
            problem_vals = numeric_vals[(numeric_vals > INT_LIMIT) | (numeric_vals < -INT_LIMIT)]
            print(f"   # out of range: {len(problem_vals)}")
            print(f"   examples: {problem_vals.head(3).tolist()}")
            print()
            problems.append(col)
            
    except Exception as e:
        pass

print("=" * 70)

if problems:
    print(f"\n🚨 FOUND {len(problems)} PROBLEMATIC COLUMNS:")
    for p in problems:
        print(f"   - {p}")
else:
    print("\n✅ No out-of-range integer values found in any column.")
    print("\nThe issue might be elsewhere. Let's check the actual insert...")
    print("\nShowing first row of data that would be inserted:")
    
    # Simulate what we're inserting
    COLUMN_MAPPING = {
        'game_id': 'game_id', 'play_id': 'play_id', 'season': 'season',
        'week': 'week', 'season_type': 'season_type', 'home_team': 'home_team',
        'away_team': 'away_team', 'posteam': 'posteam', 'defteam': 'defteam',
        'qtr': 'quarter', 'half_seconds_remaining': 'time_remaining_half',
        'down': 'down', 'ydstogo': 'ydstogo', 'yardline_100': 'yardline_100',
        'posteam_score': 'posteam_score', 'defteam_score': 'defteam_score',
        'score_differential': 'score_differential', 'play_type': 'play_type',
        'pass': 'pass', 'rush': 'rush', 'yards_gained': 'yards_gained',
        'offense_personnel': 'offense_personnel', 'defense_personnel': 'defense_personnel',
        'defenders_in_box': 'defenders_in_box', 'shotgun': 'shotgun',
        'no_huddle': 'no_huddle', 'epa': 'epa', 'wpa': 'wpa', 'success': 'success',
        'touchdown': 'touchdown', 'interception': 'interception', 'fumble': 'fumble',
        'first_down': 'first_down', 'passer_player_id': 'passer_player_id',
        'rusher_player_id': 'rusher_player_id', 'receiver_player_id': 'receiver_player_id',
    }
    
    available = {k: v for k, v in COLUMN_MAPPING.items() if k in df.columns}
    sample = df[list(available.keys())].iloc[0]
    
    print()
    for orig_col, new_col in available.items():
        val = sample[orig_col]
        val_type = type(val).__name__
        print(f"  {new_col}: {val} ({val_type})")