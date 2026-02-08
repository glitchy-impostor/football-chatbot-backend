"""
Intent Classification

Classifies user queries into predefined intent categories for Tier 2 routing.
Uses keyword matching and simple heuristics (no ML required).
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class Intent:
    """Classified intent with confidence and extracted entities."""
    intent_type: str
    confidence: float
    entities: Dict[str, any]
    raw_query: str


class IntentClassifier:
    """
    Simple keyword-based intent classifier.
    
    Intent types:
    - team_profile: General team information
    - team_stats: Specific team statistics
    - team_ranking: How a team ranks
    - player_stats: Player statistics
    - top_players: Rankings of players
    - situational: Down/distance/field position analysis
    - comparison: Compare teams or players
    - decision: Play calling decisions
    - general: Catch-all for unclassified
    """
    
    # Keywords that indicate each intent type
    INTENT_KEYWORDS = {
        'team_profile': [
            'tell me about', 'profile', 'overview', 'summary', 
            'what can you tell me', 'describe', 'who are'
        ],
        'team_stats': [
            'stats', 'statistics', 'numbers', 'metrics',
            'epa', 'efficiency', 'success rate', 'pass rate'
        ],
        'team_ranking': [
            'rank', 'ranking', 'how does', 'where does',
            'best', 'worst', 'top', 'bottom', 'leading'
        ],
        'player_stats': [
            'player', 'stats for', 'how is', 'how has',
            'performance', 'doing this season'
        ],
        'top_players': [
            'top rushers', 'top passers', 'top receivers',
            'best rushers', 'best passers', 'best receivers',
            'leading rushers', 'leading passers', 'who leads',
            'rushing leaders', 'passing leaders', 'receiving leaders'
        ],
        'situational': [
            'on 3rd', 'on 4th', 'on first', 'on second',
            'third down', 'fourth down', 'red zone', 'goal line',
            'when losing', 'when winning', 'when tied',
            'late in', 'two minute', '2 minute', 'end of half'
        ],
        'comparison': [
            'compare', 'versus', ' vs ', ' vs.', 'against',
            'better than', 'worse than', 'difference between',
            'head to head', 'matchup'
        ],
        'decision': [
            'should i', 'should we', 'should they',
            'run or pass', 'pass or run', 'go for it',
            'kick field goal', 'punt', 'what play',
            'what should', 'recommend'
        ],
    }
    
    # Patterns to extract entities
    ENTITY_PATTERNS = {
        'team': r'\b(chiefs?|niners?|49ers?|ravens?|bills?|cowboys?|eagles?|lions?|dolphins?|packers?|bengals?|browns?|steelers?|texans?|colts?|jaguars?|jags?|titans?|broncos?|raiders?|chargers?|rams?|seahawks?|cardinals?|saints?|falcons?|panthers?|buccaneers?|bucs?|bears?|vikings?|giants?|jets?|commanders?|patriots?|KC|SF|BAL|BUF|DAL|PHI|DET|MIA|GB|CIN|CLE|PIT|HOU|IND|JAX|TEN|DEN|LV|LAC|LA|SEA|ARI|NO|ATL|CAR|TB|CHI|MIN|NYG|NYJ|WAS|NE)\b',
        'down': r'(\d)(?:st|nd|rd|th)\s*(?:down|and)',
        'distance': r'(?:and|&)\s*(\d+)',
        'season': r'(20\d{2})\s*(?:season)?',
        'stat_type': r'\b(rushing|passing|receiving|offense|defense|epa|success)\b',
    }
    
    def __init__(self):
        # Compile patterns for efficiency
        self.entity_patterns = {
            name: re.compile(pattern, re.IGNORECASE)
            for name, pattern in self.ENTITY_PATTERNS.items()
        }
    
    def _extract_entities(self, query: str) -> Dict:
        """Extract entities from the query."""
        entities = {}
        
        for entity_name, pattern in self.entity_patterns.items():
            matches = pattern.findall(query)
            if matches:
                if entity_name == 'team' and len(matches) >= 2:
                    entities['team1'] = matches[0]
                    entities['team2'] = matches[1]
                elif entity_name == 'team' and len(matches) == 1:
                    entities['team'] = matches[0]
                elif entity_name in ['down', 'distance', 'season']:
                    entities[entity_name] = int(matches[0])
                else:
                    entities[entity_name] = matches[0]
        
        return entities
    
    def _score_intent(self, query: str, intent_type: str) -> float:
        """Score how well a query matches an intent type."""
        query_lower = query.lower()
        keywords = self.INTENT_KEYWORDS[intent_type]
        
        # Count matching keywords
        matches = 0
        for keyword in keywords:
            if keyword in query_lower:
                matches += 1
        
        if matches == 0:
            return 0.0
        
        # Base score from keyword matches
        score = min(0.9, 0.5 + (matches * 0.15))
        
        # Boost for strong signals
        strong_signals = {
            'team_profile': ['tell me about', 'profile', 'overview'],
            'team_ranking': ['how does', 'rank', 'ranking'],
            'top_players': ['top', 'leading', 'best'],
            'comparison': ['compare', ' vs ', 'versus'],
            'decision': ['should', 'run or pass', 'go for it'],
            'situational': ['on 3rd', 'on 4th', 'red zone', 'third down'],
        }
        
        if intent_type in strong_signals:
            for signal in strong_signals[intent_type]:
                if signal in query_lower:
                    score = min(0.95, score + 0.1)
        
        return score
    
    def classify(self, query: str) -> Intent:
        """
        Classify a query into an intent.
        
        Args:
            query: User's natural language query
            
        Returns:
            Intent object with type, confidence, and entities
        """
        # Score all intent types
        scores = {}
        for intent_type in self.INTENT_KEYWORDS.keys():
            scores[intent_type] = self._score_intent(query, intent_type)
        
        # Get best match
        best_intent = max(scores, key=scores.get)
        best_score = scores[best_intent]
        
        # Extract entities
        entities = self._extract_entities(query)
        
        # If no good match, return general
        if best_score < 0.3:
            return Intent(
                intent_type='general',
                confidence=0.2,
                entities=entities,
                raw_query=query
            )
        
        return Intent(
            intent_type=best_intent,
            confidence=best_score,
            entities=entities,
            raw_query=query
        )
    
    def get_all_scores(self, query: str) -> Dict[str, float]:
        """Get scores for all intent types (useful for debugging)."""
        scores = {}
        for intent_type in self.INTENT_KEYWORDS.keys():
            scores[intent_type] = self._score_intent(query, intent_type)
        return dict(sorted(scores.items(), key=lambda x: -x[1]))
