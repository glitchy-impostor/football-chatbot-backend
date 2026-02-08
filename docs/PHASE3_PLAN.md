# Phase 3: Pipeline Infrastructure — Implementation Plan

## Overview

Phase 3 builds the routing and API layer that connects your analytical models to the chatbot interface. This is the "brain" that decides how to handle each query.

## Architecture

```
User Query
    ↓
┌─────────────────────────────────────────────────────────┐
│                    QUERY ROUTER                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │
│  │  Explicit   │  │   Mapped    │  │  LLM Fallback   │ │
│  │  Pipeline   │→ │   Query     │→ │  (Claude API)   │ │
│  │  Matching   │  │   Patterns  │  │                 │ │
│  └─────────────┘  └─────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│                   PIPELINE EXECUTOR                     │
│  • Team Analysis    • Player Comparison                 │
│  • Situation EPA    • Decision Analysis                 │
│  • Tendencies       • Drive Simulation                  │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│                 RESPONSE FORMATTER                      │
│  Model Output → Natural Language + Data                 │
└─────────────────────────────────────────────────────────┘
    ↓
User Response
```

## Three-Tier Routing Strategy

### Tier 1: Explicit Pipeline Matching
Pattern-matched queries that map directly to a pipeline.

| Pattern | Pipeline | Example |
|---------|----------|---------|
| "team profile for {team}" | team_profile | "team profile for KC" |
| "{team} vs {team}" | team_comparison | "KC vs SF matchup" |
| "should I run or pass on {down} and {distance}" | situation_epa | "should I run or pass on 3rd and 5" |
| "go for it on 4th and {distance}" | decision_analysis | "should I go for it on 4th and 2" |
| "top {position} by {metric}" | player_rankings | "top RBs by EPA" |

### Tier 2: Mapped Query Patterns
Fuzzy matching for common question types.

| Intent | Keywords | Pipeline |
|--------|----------|----------|
| team_tendency | "how often", "tendency", "likely to" | situational_tendencies |
| player_compare | "better", "vs", "compare" | player_comparison |
| game_situation | "what play", "best call", "recommend" | situation_epa |
| historical | "last season", "in 2023", "history" | historical_query |

### Tier 3: LLM Fallback
For complex or ambiguous queries, use Claude to:
1. Parse the intent
2. Extract entities (teams, players, situations)
3. Select appropriate pipeline
4. Generate natural language response

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /chat | Main chat endpoint |
| GET | /teams/{team}/profile | Team profile |
| GET | /teams/{team}/tendencies | Team tendencies |
| POST | /teams/compare | Compare teams |
| GET | /players/{id}/stats | Player stats |
| POST | /players/compare | Compare players |
| POST | /situation/analyze | Analyze game situation |
| POST | /decision/fourth-down | 4th down decision |
| GET | /health | Health check |

## Dependencies

```
fastapi>=0.100.0
uvicorn>=0.23.0
pydantic>=2.0.0
```
