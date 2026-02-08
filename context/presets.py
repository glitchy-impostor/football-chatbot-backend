"""
Context Presets

Manages user context and preferences for personalized analysis.
Includes conversation history for follow-up questions.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
import json


@dataclass
class ConversationTurn:
    """A single turn in the conversation."""
    query: str
    pipeline: str
    params: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        d['timestamp'] = self.timestamp.isoformat()
        return d


@dataclass 
class ConversationHistory:
    """Tracks conversation context for follow-up questions."""
    
    # Last mentioned entities
    last_team: Optional[str] = None
    last_team2: Optional[str] = None  # For comparisons
    last_player: Optional[str] = None
    last_position: Optional[str] = None
    
    # Last situation context
    last_down: Optional[int] = None
    last_distance: Optional[int] = None
    last_yardline: Optional[int] = None
    
    # Last pipeline used
    last_pipeline: Optional[str] = None
    
    # Recent turns (keep last 5)
    turns: List[ConversationTurn] = field(default_factory=list)
    max_turns: int = 5
    
    def add_turn(self, query: str, pipeline: str, params: Dict[str, Any]):
        """Add a conversation turn and update context."""
        turn = ConversationTurn(query=query, pipeline=pipeline, params=params)
        self.turns.append(turn)
        
        # Keep only last N turns
        if len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns:]
        
        # Update last mentioned entities
        self.last_pipeline = pipeline
        
        if 'team' in params and params['team']:
            self.last_team = params['team']
        if 'team1' in params and params['team1']:
            self.last_team = params['team1']
        if 'team2' in params and params['team2']:
            self.last_team2 = params['team2']
        if 'position' in params and params['position']:
            self.last_position = params['position']
        if 'down' in params and params['down']:
            self.last_down = params['down']
        if 'distance' in params and params['distance']:
            self.last_distance = params['distance']
        if 'yardline' in params and params['yardline']:
            self.last_yardline = params['yardline']
    
    def get_context_for_followup(self) -> Dict[str, Any]:
        """Get context that can be used for follow-up questions."""
        return {
            'last_team': self.last_team,
            'last_team2': self.last_team2,
            'last_player': self.last_player,
            'last_position': self.last_position,
            'last_down': self.last_down,
            'last_distance': self.last_distance,
            'last_yardline': self.last_yardline,
            'last_pipeline': self.last_pipeline,
        }
    
    def clear(self):
        """Clear conversation history."""
        self.last_team = None
        self.last_team2 = None
        self.last_player = None
        self.last_position = None
        self.last_down = None
        self.last_distance = None
        self.last_yardline = None
        self.last_pipeline = None
        self.turns = []


@dataclass
class UserContext:
    """User context that affects analysis."""
    
    # Team preferences
    favorite_team: Optional[str] = None
    comparison_teams: List[str] = field(default_factory=list)
    
    # Analysis preferences
    season: int = 2025
    detail_level: str = 'normal'  # 'brief', 'normal', 'detailed'
    include_confidence: bool = True
    include_raw_data: bool = False
    
    # Situation defaults (for "what should I do" queries)
    default_quarter: int = 2
    default_score_diff: int = 0
    
    # Session info
    session_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    
    # Conversation history
    history: ConversationHistory = field(default_factory=ConversationHistory)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        d = asdict(self)
        d['created_at'] = self.created_at.isoformat()
        # Don't serialize full history
        d.pop('history', None)
        return d
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'UserContext':
        """Create from dictionary."""
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        data.pop('history', None)  # Don't restore history from dict
        return cls(**data)


class ContextManager:
    """
    Manages user contexts and presets.
    """
    
    # Preset team contexts
    TEAM_PRESETS = {
        'chiefs_fan': UserContext(
            favorite_team='KC',
            comparison_teams=['BAL', 'BUF', 'SF'],
            detail_level='detailed'
        ),
        'fantasy_focused': UserContext(
            detail_level='detailed',
            include_raw_data=True,
            include_confidence=True
        ),
        'casual': UserContext(
            detail_level='brief',
            include_confidence=False
        ),
        'analyst': UserContext(
            detail_level='detailed',
            include_raw_data=True,
            include_confidence=True
        ),
    }
    
    def __init__(self):
        self.contexts: Dict[str, UserContext] = {}
    
    def create_context(self, session_id: str, **kwargs) -> UserContext:
        """
        Create a new user context.
        
        Args:
            session_id: Unique session identifier
            **kwargs: Context parameters
            
        Returns:
            Created UserContext
        """
        context = UserContext(session_id=session_id, **kwargs)
        self.contexts[session_id] = context
        return context
    
    def get_context(self, session_id: str) -> Optional[UserContext]:
        """Get context for a session."""
        return self.contexts.get(session_id)
    
    def get_or_create(self, session_id: str, **kwargs) -> UserContext:
        """Get existing context or create new one."""
        if session_id in self.contexts:
            return self.contexts[session_id]
        return self.create_context(session_id, **kwargs)
    
    def update_context(self, session_id: str, **kwargs) -> Optional[UserContext]:
        """
        Update an existing context.
        
        Args:
            session_id: Session identifier
            **kwargs: Fields to update
            
        Returns:
            Updated context or None if not found
        """
        context = self.contexts.get(session_id)
        if not context:
            return None
        
        for key, value in kwargs.items():
            if hasattr(context, key):
                setattr(context, key, value)
        
        return context
    
    def apply_preset(self, session_id: str, preset_name: str) -> Optional[UserContext]:
        """
        Apply a preset to a session's context.
        
        Args:
            session_id: Session identifier
            preset_name: Name of preset to apply
            
        Returns:
            Updated context or None
        """
        preset = self.TEAM_PRESETS.get(preset_name)
        if not preset:
            return None
        
        context = self.get_or_create(session_id)
        
        # Apply preset values (except session_id and created_at)
        for key in ['favorite_team', 'comparison_teams', 'detail_level', 
                    'include_confidence', 'include_raw_data']:
            value = getattr(preset, key)
            if value:
                setattr(context, key, value)
        
        return context
    
    def delete_context(self, session_id: str) -> bool:
        """Delete a session's context."""
        if session_id in self.contexts:
            del self.contexts[session_id]
            return True
        return False
    
    def to_router_context(self, user_context: UserContext) -> Dict:
        """
        Convert UserContext to format expected by QueryRouter.
        
        Args:
            user_context: User context object
            
        Returns:
            Dictionary for router
        """
        return {
            'favorite_team': user_context.favorite_team,
            'season': user_context.season,
            'default_quarter': user_context.default_quarter,
            'default_score_diff': user_context.default_score_diff,
        }


# Global context manager instance
context_manager = ContextManager()


def get_context_manager() -> ContextManager:
    """Get the global context manager."""
    return context_manager
