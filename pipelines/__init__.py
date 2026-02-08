"""
Pipeline Infrastructure

Query routing and execution for the football analytics chatbot.
"""

from .router import QueryRouter, PipelineType, RouteResult
from .executor import PipelineExecutor

__all__ = [
    'QueryRouter',
    'PipelineType', 
    'RouteResult',
    'PipelineExecutor',
]
