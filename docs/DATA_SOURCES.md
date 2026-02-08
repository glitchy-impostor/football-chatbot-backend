# NFL Data Sources Guide

This document covers data sources for the football chatbot, including nflfastR (primary) and alternatives like api-football.

---

## Primary Source: nflfastR

**Website:** https://github.com/nflverse/nflverse-data

**What it provides:**
- Play-by-play data for every NFL game since 1999
- EPA (Expected Points Added) already calculated
- Player IDs linked to roster data
- Down, distance, yardline, formation, personnel
- Free and open source

**Availability:**
- Regular season: Updated within 24 hours of game completion
- Playoffs: Updated after each round
- New season: Available after Week 1

**Current Status (2025 Season):**
The 2025 season data IS available (we downloaded 48,578 plays). The "integer out of range" error was due to `play_id` exceeding PostgreSQL INTEGER limits.

**Fix:**
```cmd
# 1. Run migration to change play_id to BIGINT
python scripts/migrations/001_play_id_bigint.py

# 2. Re-run ingestion
python scripts/ingest_pbp.py --seasons 2025
```

---

## Alternative: api-football (RapidAPI)

**Website:** https://www.api-football.com/documentation-v3#tag/American-Football

**Cost:** $0-$100+/month depending on plan

**What it provides:**
- ✅ Live scores and game status
- ✅ Standings and schedules
- ✅ Team/player basic stats
- ✅ Game results
- ❌ NO play-by-play data
- ❌ NO EPA calculations
- ❌ NO situational breakdowns
- ❌ NO formation/personnel data

**Verdict:** NOT useful for our analytics needs. Good for a scores/standings app, but lacks the granular data we need for EPA-based recommendations.

---

## Comparison: nflfastR vs api-football

| Feature | nflfastR | api-football |
|---------|----------|--------------|
| Cost | Free | $0-100+/mo |
| Play-by-play | ✅ Yes | ❌ No |
| EPA | ✅ Pre-calculated | ❌ No |
| Down/distance | ✅ Yes | ❌ No |
| Formation | ✅ Yes | ❌ No |
| Personnel | ✅ Yes | ❌ No |
| Live scores | ❌ No (delayed) | ✅ Real-time |
| Update speed | ~24 hours | Real-time |
| Historical | 1999-present | Limited |

**Bottom line:** Stick with nflfastR for analytics. api-football is only useful if you need real-time scores.

---

## Other Alternatives

### 1. ESPN Hidden API (Unofficial)
```
https://site.api.espn.com/apis/site/v2/sports/football/nfl/...
```
- Free but unofficial
- Basic stats only
- No play-by-play
- Could break at any time

### 2. Sportradar (Official NFL Partner)
- Expensive ($$$)
- Full play-by-play
- Real-time
- Enterprise-level

### 3. Pro Football Focus (PFF)
- Subscription required
- Advanced grades
- Detailed analytics
- No API access for hobbyists

### 4. NFL's Official API
- Requires partnership
- Not available to public

---

## Recommended Architecture

For a hobby/portfolio project, use this tiered approach:

```
┌─────────────────────────────────────────┐
│           User Interface                │
├─────────────────────────────────────────┤
│         Football Chatbot API            │
├──────────────┬──────────────────────────┤
│  Historical  │      Real-Time           │
│   Analysis   │      (Optional)          │
├──────────────┼──────────────────────────┤
│   nflfastR   │   api-football or        │
│   (Free)     │   ESPN hidden API        │
│              │   (for live scores)      │
└──────────────┴──────────────────────────┘
```

**Core analytics:** nflfastR (detailed, free, reliable)
**Live scores (optional):** api-football or ESPN hidden API

---

## If nflfastR Data is Delayed

Sometimes there's a delay in nflfastR publishing new season data. Workarounds:

### Option 1: Use Previous Season
The chatbot works fine with 2024 data. Just update the default:
```python
# In router.py, executor.py, etc.
season = params.get('season', 2024)  # Use last complete season
```

### Option 2: Wait for Update
nflfastR is maintained by volunteers. New seasons typically appear within a week of Week 1.

Check status: https://github.com/nflverse/nflverse-data/releases

### Option 3: Build from Raw Data
If desperate, you can build EPA yourself from NFL's game book data, but this is complex and not recommended for a portfolio project.

---

## Troubleshooting 2025 Data

### Error: "integer out of range"
**Cause:** play_id values in 2025 exceed PostgreSQL INTEGER max (2,147,483,647)

**Fix:**
```cmd
# Run migration
python scripts/migrations/001_play_id_bigint.py

# Re-ingest
python scripts/ingest_pbp.py --seasons 2025 --force
```

### Error: "File not found"
**Cause:** Season data not yet published

**Check:** Visit https://github.com/nflverse/nflverse-data/releases/tag/pbp

### Error: "No valid plays found"
**Cause:** Offseason - only preseason data available

**Fix:** Wait for regular season or use previous year's data

---

## Summary

| Need | Use |
|------|-----|
| EPA & play-by-play analytics | nflfastR ✅ |
| Live scores | api-football (paid) or ESPN API (free/risky) |
| Basic standings | Either |
| Real-time updates | api-football |
| Historical analysis | nflfastR |

**For this chatbot:** nflfastR is the correct choice. The 2025 data works after fixing the INTEGER overflow issue.
