# Phase 4: LLM Integration — Implementation Plan

## Overview

Phase 4 integrates Claude to handle complex queries that don't fit explicit pipelines, generate natural language responses, and provide conversational context awareness.

## Architecture

```
User Query
    ↓
┌─────────────────────────────────────────────────────────┐
│                    QUERY ROUTER                         │
│         Tier 1 → Tier 2 → Tier 3 (LLM)                 │
└─────────────────────────────────────────────────────────┘
    ↓                                    ↓
┌──────────────┐                ┌──────────────────────┐
│   Pipeline   │                │    LLM Handler       │
│   Executor   │                │  • Intent parsing    │
│              │                │  • Entity extraction │
│              │                │  • Response gen      │
└──────────────┘                └──────────────────────┘
    ↓                                    ↓
┌─────────────────────────────────────────────────────────┐
│                 RESPONSE GENERATOR                      │
│         Combines data + LLM for natural output          │
└─────────────────────────────────────────────────────────┘
    ↓
User Response
```

## LLM Use Cases

### 1. Intent Parsing (Tier 3 Fallback)
When query doesn't match explicit patterns, use Claude to:
- Identify what the user is asking
- Extract entities (teams, players, situations)
- Route to appropriate pipeline

### 2. Natural Language Generation
- Convert structured analysis to conversational responses
- Add context and explanations
- Handle follow-up questions

### 3. Complex Queries
- Multi-part questions
- Comparative analysis across multiple dimensions
- "What if" scenarios
- Strategic recommendations

## System Prompt Design

The LLM receives:
1. **Role**: Football analytics assistant
2. **Available Tools**: List of pipelines it can call
3. **Data Context**: Current season, available teams
4. **User Context**: Favorite team, preferences
5. **Conversation History**: Recent exchanges

## Phase 4 Directory Structure

```
football-chatbot/
├── llm/
│   ├── __init__.py
│   ├── client.py           # Claude API client
│   ├── prompts.py          # System prompts
│   ├── tools.py            # Tool definitions for function calling
│   └── handler.py          # LLM request handler
├── api/
│   └── main.py             # Updated with LLM endpoints
└── tests/phase4/
    ├── __init__.py
    ├── test_llm_handler.py
    └── run_phase4_validation.py
```

## Tool Definitions

Claude will have access to these "tools" (pipelines):

```python
tools = [
    {
        "name": "get_team_profile",
        "description": "Get a team's overall profile including EPA, tendencies, strengths",
        "parameters": {"team": "string", "season": "integer"}
    },
    {
        "name": "compare_teams",
        "description": "Compare two teams head-to-head",
        "parameters": {"team1": "string", "team2": "string"}
    },
    {
        "name": "analyze_situation",
        "description": "Analyze run vs pass for a game situation",
        "parameters": {"down": "integer", "distance": "integer", "yardline": "integer"}
    },
    {
        "name": "fourth_down_decision",
        "description": "Analyze whether to go for it, kick, or punt on 4th down",
        "parameters": {"distance": "integer", "yardline": "integer"}
    },
    {
        "name": "get_player_rankings",
        "description": "Get top players by position and metric",
        "parameters": {"position": "string", "count": "integer"}
    }
]
```

## Conversation Flow

```
User: "I'm a Chiefs fan. How do we match up against the Ravens?"

→ Router: Tier 3 (general query with context)
→ LLM parses: team comparison, KC vs BAL
→ Calls: compare_teams(team1="KC", team2="BAL")
→ Gets: structured comparison data
→ LLM generates: natural language response with KC fan perspective
```

## Dependencies

```
anthropic>=0.18.0
```

## API Key Setup

```bash
# .env file
ANTHROPIC_API_KEY=sk-ant-...
```
