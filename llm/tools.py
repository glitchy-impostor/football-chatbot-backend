"""
Tool Definitions

Defines the tools (pipelines) available to Claude for function calling.
"""

from typing import Dict, List, Any


# Tool definitions in Anthropic's format
PIPELINE_TOOLS = [
    {
        "name": "get_team_profile",
        "description": "Get a comprehensive profile of an NFL team including offensive/defensive EPA, pass rates, tendencies, strengths and weaknesses. Use this when users ask about a specific team's performance or characteristics.",
        "input_schema": {
            "type": "object",
            "properties": {
                "team": {
                    "type": "string",
                    "description": "Team abbreviation (e.g., KC, SF, BAL, BUF, PHI)"
                },
                "season": {
                    "type": "integer",
                    "description": "Season year (2016-2024)",
                    "default": 2025
                }
            },
            "required": ["team"]
        }
    },
    {
        "name": "compare_teams",
        "description": "Compare two NFL teams head-to-head on offense, defense, tendencies, and identify matchup advantages. Use this when users want to compare teams or analyze a matchup.",
        "input_schema": {
            "type": "object",
            "properties": {
                "team1": {
                    "type": "string",
                    "description": "First team abbreviation"
                },
                "team2": {
                    "type": "string",
                    "description": "Second team abbreviation"
                },
                "season": {
                    "type": "integer",
                    "description": "Season year",
                    "default": 2025
                }
            },
            "required": ["team1", "team2"]
        }
    },
    {
        "name": "get_team_tendencies",
        "description": "Get detailed play-calling tendencies for a team, optionally filtered by situation. Shows pass rates, formation usage, and how they deviate from league average.",
        "input_schema": {
            "type": "object",
            "properties": {
                "team": {
                    "type": "string",
                    "description": "Team abbreviation"
                },
                "down": {
                    "type": "integer",
                    "description": "Filter by down (1-4)",
                    "minimum": 1,
                    "maximum": 4
                },
                "distance": {
                    "type": "integer",
                    "description": "Filter by yards to go"
                },
                "season": {
                    "type": "integer",
                    "description": "Season year",
                    "default": 2025
                }
            },
            "required": ["team"]
        }
    },
    {
        "name": "analyze_situation",
        "description": "Analyze a game situation to determine whether running or passing has higher expected points. Provides EPA estimates for both options with a recommendation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "down": {
                    "type": "integer",
                    "description": "Current down (1-4)",
                    "minimum": 1,
                    "maximum": 4
                },
                "distance": {
                    "type": "integer",
                    "description": "Yards to first down",
                    "minimum": 1
                },
                "yardline": {
                    "type": "integer",
                    "description": "Yards from opponent's end zone (1-99)",
                    "minimum": 1,
                    "maximum": 99,
                    "default": 50
                },
                "quarter": {
                    "type": "integer",
                    "description": "Quarter (1-5, 5=OT)",
                    "default": 2
                },
                "score_differential": {
                    "type": "integer",
                    "description": "Your score minus opponent's score",
                    "default": 0
                },
                "team": {
                    "type": "string",
                    "description": "Team for context-adjusted analysis (optional)"
                }
            },
            "required": ["down", "distance"]
        }
    },
    {
        "name": "fourth_down_decision",
        "description": "Analyze a 4th down decision using Monte Carlo simulation. Compares expected points for going for it vs kicking (field goal or punt). Use this for any 4th down go-for-it questions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "distance": {
                    "type": "integer",
                    "description": "Yards to first down",
                    "minimum": 1
                },
                "yardline": {
                    "type": "integer",
                    "description": "Yards from opponent's end zone",
                    "minimum": 1,
                    "maximum": 99
                },
                "score_differential": {
                    "type": "integer",
                    "description": "Your score minus opponent's score",
                    "default": 0
                }
            },
            "required": ["distance", "yardline"]
        }
    },
    {
        "name": "get_player_rankings",
        "description": "Get top players at a position ranked by EPA or other metrics. Uses Bayesian shrinkage to account for sample size differences.",
        "input_schema": {
            "type": "object",
            "properties": {
                "position": {
                    "type": "string",
                    "description": "Position: QB, RB, WR, or TE",
                    "enum": ["QB", "RB", "WR", "TE"]
                },
                "count": {
                    "type": "integer",
                    "description": "Number of players to return",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 50
                },
                "metric": {
                    "type": "string",
                    "description": "Metric to rank by",
                    "default": "epa",
                    "enum": ["epa", "yards", "success_rate"]
                },
                "min_attempts": {
                    "type": "integer",
                    "description": "Minimum attempts/targets to qualify",
                    "default": 30
                }
            },
            "required": ["position"]
        }
    },
    {
        "name": "simulate_drive",
        "description": "Simulate a drive from a given field position to estimate expected points and scoring probabilities. Uses Monte Carlo simulation with historical play distributions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "yardline": {
                    "type": "integer",
                    "description": "Starting yards from opponent's end zone",
                    "minimum": 1,
                    "maximum": 99
                }
            },
            "required": ["yardline"]
        }
    }
]


def get_tool_by_name(name: str) -> Dict:
    """Get a specific tool definition by name."""
    for tool in PIPELINE_TOOLS:
        if tool["name"] == name:
            return tool
    return None


def get_all_tools() -> List[Dict]:
    """Get all tool definitions."""
    return PIPELINE_TOOLS


def get_tool_names() -> List[str]:
    """Get list of available tool names."""
    return [tool["name"] for tool in PIPELINE_TOOLS]


# Mapping from tool names to pipeline types
TOOL_TO_PIPELINE = {
    "get_team_profile": "team_profile",
    "compare_teams": "team_comparison",
    "get_team_tendencies": "team_tendencies",
    "analyze_situation": "situation_epa",
    "fourth_down_decision": "decision_analysis",
    "get_player_rankings": "player_rankings",
    "simulate_drive": "drive_simulation",
}


def tool_name_to_pipeline(tool_name: str) -> str:
    """Convert tool name to pipeline type."""
    return TOOL_TO_PIPELINE.get(tool_name, "unknown")
