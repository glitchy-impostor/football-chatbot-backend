# Updating to Current Season Data

This guide explains how to add 2025 season data (or any new season) to the football chatbot.

## Quick Start

```bash
# 1. Download and ingest 2025 data
python scripts/ingest_pbp.py --seasons 2025

# 2. Rebuild derived tables
python scripts/build_derived_tables.py

# 3. Retrain all models with new data
python training/train_all_models.py

# 4. Restart the API
uvicorn api.main:app --reload
```

## Detailed Steps

### Step 1: Download Play-by-Play Data

The chatbot uses nflfastR data, which is updated throughout the NFL season.

```bash
# Download just 2025
python scripts/ingest_pbp.py --seasons 2025

# Or download multiple seasons
python scripts/ingest_pbp.py --seasons 2023 2025

# Force re-download if data exists
python scripts/ingest_pbp.py --seasons 2025 --force
```

**Note:** During the season, data is typically updated within 24 hours of games ending.

### Step 2: Build Derived Tables

This aggregates play-level data into team and player statistics:

```bash
python scripts/build_derived_tables.py
```

This creates/updates:
- `team_season_stats` - Team-level aggregates
- `player_season_stats` - Player-level stats with names

### Step 3: Retrain Models

Rebuild the statistical models with the new data:

```bash
python training/train_all_models.py
```

This generates:
- `data/models/team_profiles.json` - Team profiles for all seasons
- `data/models/player_estimates.json` - Player effectiveness estimates
- `data/models/epa_model.pkl` - EPA prediction model
- `data/models/drive_simulator.pkl` - Drive simulation model

### Step 4: Update Default Season

To make queries default to 2025, update the router:

```python
# In pipelines/router.py, line ~530
params['season'] = context.get('season', 2025)  # Change from 2023

# In pipelines/executor.py, update defaults
season = params.get('season', 2025)  # Multiple locations
```

Or let users specify the season in their query:
- "Chiefs 2025 profile"
- "Top RBs in 2025"

## Data Freshness

| Source | Update Frequency |
|--------|-----------------|
| Play-by-play | Within 24 hours of game end |
| Rosters | Weekly during season |
| Injuries | Not included (use external API) |

## Checking Data Status

Run the diagnostic script:

```bash
python scripts/check_team_profiles.py
```

This shows:
- Which seasons have data
- Which teams are available
- Player count by position

## Automating Updates

For production, set up a cron job:

```bash
# Weekly update during season (Sunday night after games)
0 23 * * 0 cd /path/to/football-chatbot && ./scripts/weekly_update.sh
```

Create `scripts/weekly_update.sh`:

```bash
#!/bin/bash
set -e

echo "Updating football chatbot data..."

# Download latest data
python scripts/ingest_pbp.py --seasons 2025 --force

# Rebuild derived tables
python scripts/build_derived_tables.py

# Retrain models
python training/train_all_models.py

echo "Update complete!"

# Optionally restart API (if using systemd)
# sudo systemctl restart football-chatbot
```

## Troubleshooting

### "Season data not found"

nflfastR data may not be available yet:
- Regular season: Available throughout season
- Playoffs: Added after games
- New season: Available after Week 1

### "Model training failed"

Check you have enough data:
- Need at least 1000 plays per team for reliable stats
- Early season data may be sparse

### "Player names missing"

Roster data may not be linked:
```bash
# Re-run with roster refresh
python scripts/build_derived_tables.py --refresh-rosters
```

## Multi-Season Analysis

The chatbot supports querying specific seasons:

```
"Chiefs 2023 profile"
"Compare 2022 Bills to 2023 Bills"
"Top QBs in 2025"
```

To enable cross-season comparison, ensure both seasons are ingested:

```bash
python scripts/ingest_pbp.py --seasons 2022 2023 2025
python scripts/build_derived_tables.py
python training/train_all_models.py
```
