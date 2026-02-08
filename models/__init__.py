"""
Football Analytics Chatbot - Core Models

This package contains the analytical models that power the chatbot:

- EPAPredictor: Predicts expected points added for plays
- TeamProfiler: Builds team identity profiles relative to league average
- PlayerEffectivenessModel: Shrunk player performance estimates
- DriveSimulator: Monte Carlo simulation of drive outcomes
"""

from .epa_model import EPAPredictor
from .team_profiles import TeamProfiler
from .player_effectiveness import PlayerEffectivenessModel
from .drive_simulator import DriveSimulator

__all__ = [
    'EPAPredictor',
    'TeamProfiler', 
    'PlayerEffectivenessModel',
    'DriveSimulator',
]
