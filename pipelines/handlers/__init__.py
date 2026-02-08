"""
Pipeline Handlers

Each handler is responsible for a specific type of analysis:
- TeamStatsHandler: Team statistics and rankings
- PlayerStatsHandler: Player performance and rankings
- SituationalHandler: Down/distance/field zone analysis
- ComparisonHandler: Team and player comparisons
- DecisionHandler: Play calling recommendations
"""

from .team_stats import TeamStatsHandler
from .player_stats import PlayerStatsHandler
from .situational import SituationalHandler
from .comparison import ComparisonHandler
from .decision import DecisionHandler

__all__ = [
    'TeamStatsHandler',
    'PlayerStatsHandler',
    'SituationalHandler',
    'ComparisonHandler',
    'DecisionHandler',
]
