"""
Team Statistics Handler

Handles queries about team performance, rankings, and tendencies.
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class TeamStatsHandler:
    """Handler for team-related queries."""
    
    def __init__(self, db_conn, models: Dict):
        """
        Initialize handler.
        
        Args:
            db_conn: Database connection
            models: Dictionary containing team_profiler
        """
        self.db_conn = db_conn
        self.models = models
        self.profiler = models.get('team_profiler')
    
    def get_team_stats(self, team: str, season: int) -> Dict:
        """
        Get comprehensive team statistics.
        
        Args:
            team: Team abbreviation
            season: Season year
            
        Returns:
            Dictionary with team stats
        """
        logger.info(f"Getting stats for {team} {season}")
        
        # Try to get from profiler first
        if self.profiler:
            key = f"{team}_{season}"
            profile = self.profiler.profiles.get(key)
            if profile:
                return {
                    'team': team,
                    'season': season,
                    'overall': profile['overall'],
                    'defense': profile['defense'],
                    'strengths': profile.get('strengths', []),
                    'weaknesses': profile.get('weaknesses', []),
                    'sources': ['team_profiles']
                }
        
        # Fall back to database query
        cursor = self.db_conn.cursor()
        
        cursor.execute("""
            SELECT 
                team, season,
                off_epa_per_play, def_epa_per_play,
                off_success_rate, def_success_rate,
                pass_rate, total_plays
            FROM team_season_stats
            WHERE team = %s AND season = %s
        """, (team, season))
        
        row = cursor.fetchone()
        
        if not row:
            return {
                'team': team,
                'season': season,
                'error': 'Team not found',
                'sources': []
            }
        
        return {
            'team': row[0],
            'season': row[1],
            'overall': {
                'off_epa_per_play': float(row[2]) if row[2] else 0,
                'def_epa_per_play': float(row[3]) if row[3] else 0,
                'off_success_rate': float(row[4]) if row[4] else 0,
                'def_success_rate': float(row[5]) if row[5] else 0,
                'pass_rate': float(row[6]) if row[6] else 0,
                'total_plays': int(row[7]) if row[7] else 0,
            },
            'sources': ['team_season_stats']
        }
    
    def get_team_ranking(self, team: str, season: int, side: str = 'offense') -> Dict:
        """
        Get team's ranking among all teams.
        
        Args:
            team: Team abbreviation
            season: Season year
            side: 'offense' or 'defense'
            
        Returns:
            Dictionary with ranking info
        """
        logger.info(f"Getting {side} ranking for {team} {season}")
        
        cursor = self.db_conn.cursor()
        
        if side == 'offense':
            # Rank by offensive EPA (higher is better)
            cursor.execute("""
                WITH ranked AS (
                    SELECT 
                        team, season, off_epa_per_play,
                        RANK() OVER (ORDER BY off_epa_per_play DESC) as rank,
                        COUNT(*) OVER () as total_teams
                    FROM team_season_stats
                    WHERE season = %s
                )
                SELECT team, off_epa_per_play, rank, total_teams
                FROM ranked
                WHERE team = %s
            """, (season, team))
        else:
            # Rank by defensive EPA (lower is better for defense)
            cursor.execute("""
                WITH ranked AS (
                    SELECT 
                        team, season, def_epa_per_play,
                        RANK() OVER (ORDER BY def_epa_per_play ASC) as rank,
                        COUNT(*) OVER () as total_teams
                    FROM team_season_stats
                    WHERE season = %s
                )
                SELECT team, def_epa_per_play, rank, total_teams
                FROM ranked
                WHERE team = %s
            """, (season, team))
        
        row = cursor.fetchone()
        
        if not row:
            return {
                'team': team,
                'season': season,
                'side': side,
                'error': 'Team not found',
                'sources': []
            }
        
        return {
            'team': row[0],
            'season': season,
            'side': side,
            'epa_per_play': float(row[1]) if row[1] else 0,
            'rank': int(row[2]),
            'total_teams': int(row[3]),
            'percentile': round((1 - (int(row[2]) - 1) / int(row[3])) * 100, 1),
            'sources': ['team_season_stats']
        }
    
    def get_all_team_rankings(self, season: int, side: str = 'offense', limit: int = 10) -> Dict:
        """
        Get top teams by ranking.
        
        Args:
            season: Season year
            side: 'offense' or 'defense'
            limit: Number of teams to return
            
        Returns:
            Dictionary with rankings
        """
        cursor = self.db_conn.cursor()
        
        if side == 'offense':
            cursor.execute("""
                SELECT team, off_epa_per_play, off_success_rate, pass_rate
                FROM team_season_stats
                WHERE season = %s
                ORDER BY off_epa_per_play DESC
                LIMIT %s
            """, (season, limit))
        else:
            cursor.execute("""
                SELECT team, def_epa_per_play, def_success_rate
                FROM team_season_stats
                WHERE season = %s
                ORDER BY def_epa_per_play ASC
                LIMIT %s
            """, (season, limit))
        
        rows = cursor.fetchall()
        
        rankings = []
        for i, row in enumerate(rows, 1):
            if side == 'offense':
                rankings.append({
                    'rank': i,
                    'team': row[0],
                    'epa_per_play': float(row[1]) if row[1] else 0,
                    'success_rate': float(row[2]) if row[2] else 0,
                    'pass_rate': float(row[3]) if row[3] else 0,
                })
            else:
                rankings.append({
                    'rank': i,
                    'team': row[0],
                    'epa_per_play': float(row[1]) if row[1] else 0,
                    'success_rate': float(row[2]) if row[2] else 0,
                })
        
        return {
            'season': season,
            'side': side,
            'rankings': rankings,
            'sources': ['team_season_stats']
        }
