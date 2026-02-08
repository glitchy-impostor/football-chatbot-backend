#!/usr/bin/env python3
"""
Migration: Fix integer overflow columns

nflfastR play_id values in 2025+ seasons exceed PostgreSQL INTEGER range.
This script checks and fixes all columns that need BIGINT.

Usage:
    python scripts/migrations/001_play_id_bigint.py
"""

import os
import psycopg2

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:password@127.0.0.1:5432/football_analytics')

# Columns that might need BIGINT (based on nflfastR data analysis)
COLUMNS_TO_CHECK = ['play_id']  # Add more if debug script finds them

def run_migration():
    print("Migration: Fix INTEGER overflow columns")
    print("=" * 60)
    
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    try:
        for column_name in COLUMNS_TO_CHECK:
            # Check current type
            cur.execute("""
                SELECT data_type 
                FROM information_schema.columns 
                WHERE table_name = 'plays' AND column_name = %s
            """, (column_name,))
            result = cur.fetchone()
            
            if not result:
                print(f"⚠️  Column '{column_name}' not found in plays table")
                continue
                
            current_type = result[0]
            print(f"\n{column_name}:")
            print(f"  Current type: {current_type}")
            
            if current_type == 'bigint':
                print(f"  ✅ Already BIGINT")
                continue
            
            if current_type == 'integer':
                print(f"  🔄 Altering to BIGINT...")
                cur.execute(f"ALTER TABLE plays ALTER COLUMN {column_name} TYPE BIGINT")
                conn.commit()
                print(f"  ✅ Changed to BIGINT")
            else:
                print(f"  ⚠️  Unexpected type: {current_type}")
        
        print("\n" + "=" * 60)
        print("✅ Migration complete!")
        
        # Verify
        print("\nVerifying schema:")
        for column_name in COLUMNS_TO_CHECK:
            cur.execute("""
                SELECT data_type 
                FROM information_schema.columns 
                WHERE table_name = 'plays' AND column_name = %s
            """, (column_name,))
            result = cur.fetchone()
            if result:
                print(f"  {column_name}: {result[0]}")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Migration failed: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    run_migration()