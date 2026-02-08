"""
Broader search for personnel/formation columns in nflfastR data.
"""

import pandas as pd
from pathlib import Path

filepath = Path("data/raw/play_by_play_2023.parquet")
df = pd.read_parquet(filepath)

print(f"Total columns: {len(df.columns)}")
print()

# Broader keyword search
keywords = ['pers', 'form', 'shotgun', 'huddle', 'box', 'men', 'rb', 'te', 'wr', 
            'off_', 'def_', 'n_', 'number']

print("Potentially relevant columns:")
print("=" * 70)

found = []
for col in sorted(df.columns):
    col_lower = col.lower()
    if any(kw in col_lower for kw in keywords):
        non_null = df[col].notna().sum()
        pct = non_null / len(df) * 100
        if pct > 5:  # Only show columns with >5% data
            found.append((col, pct, df[col].dtype))

for col, pct, dtype in sorted(found, key=lambda x: -x[1]):
    sample = df[col].dropna().head(3).tolist()
    print(f"{col}: {pct:.1f}% non-null, dtype={dtype}")
    print(f"  samples: {sample[:3]}")
    print()

# Also check specifically for these common nflfastR column names
print("\n" + "=" * 70)
print("Checking specific known nflfastR columns:")
print("=" * 70)

specific_cols = [
    'offense_personnel', 'defense_personnel', 'defenders_in_box',
    'offense_formation', 'n_offense', 'n_defense',
    'number_of_pass_rushers', 'xpass', 'pass_oe',
    'shotgun', 'no_huddle', 'qb_dropback'
]

for col in specific_cols:
    if col in df.columns:
        non_null = df[col].notna().sum()
        pct = non_null / len(df) * 100
        sample = df[col].dropna().head(3).tolist()
        print(f"✅ {col}: {pct:.1f}% non-null")
        print(f"   samples: {sample}")
    else:
        print(f"❌ {col}: NOT FOUND")
    print()