"""
Player Statistics Handler

Handles queries about player performance and rankings.
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class PlayerStatsHandler:
    """Handler for player-related queries."""
    
    def __init__(self, db_conn, models: Dict):
        """
        Initialize handler.
        
        Args:
            db_conn: Database connection
            models: Dictionary containing player_model
        """
        self.db_conn = db_conn
        self.models = models
        self.player_model = models.get('player_model')
    
    def get_player_stats(self, player_id: str, season: int) -> Dict:
        """
        Get statistics for a specific player.
        
        Args:
            player_id: Player ID
            season: Season year
            
        Returns:
            Dictionary with player stats
        """
        logger.info(f"Getting stats for player {player_id} {season}")
        
        # Try shrunk estimates from model first
        if self.player_model:
            estimate = self.player_model.get_player_estimate(player_id)
            if estimate:
                return {
                    'player_id': player_id,
                    'season': estimate.get('season', season),
                    'stat_type': estimate.get('stat_type'),
                    'raw': estimate.get('raw', {}),
                    'shrunk': estimate.get('shrunk', {}),
                    'shrinkage_applied': estimate.get('shrinkage_applied', 0),
                    'sources': ['player_estimates']
                }
        
        # Fall back to database
        cursor = self.db_conn.cursor()
        
        cursor.execute("""
            SELECT 
                player_id, season, position,
                pass_attempts, pass_epa, pass_success_rate,
                rush_attempts, rush_epa, rush_success_rate,
                targets, rec_epa, rec_success_rate
            FROM player_season_stats
            WHERE player_id = %s AND season = %s
        """, (player_id, season))
        
        row = cursor.fetchone()
        
        if not row:
            return {
                'player_id': player_id,
                'season': season,
                'error': 'Player not found',
                'sources': []
            }
        
        return {
            'player_id': row[0],
            'season': row[1],
            'position': row[2],
            'passing': {
                'attempts': int(row[3]) if row[3] else 0,
                'epa_per_play': float(row[4]) if row[4] else 0,
                'success_rate': float(row[5]) if row[5] else 0,
            },
            'rushing': {
                'attempts': int(row[6]) if row[6] else 0,
                'epa_per_play': float(row[7]) if row[7] else 0,
                'success_rate': float(row[8]) if row[8] else 0,
            },
            'receiving': {
                'targets': int(row[9]) if row[9] else 0,
                'epa_per_play': float(row[10]) if row[10] else 0,
                'success_rate': float(row[11]) if row[11] else 0,
            },
            'sources': ['player_season_stats']
        }
    
    def get_top_players(self, stat_type: str, n: int = 10, 
                       season: int = 2023, min_attempts: int = 50) -> Dict:
        """
        Get top players by a statistic.
        
        Args:
            stat_type: 'rushing', 'passing', or 'receiving'
            n: Number of players to return
            season: Season year
            min_attempts: Minimum attempts/targets
            
        Returns:
            Dictionary with player rankings
        """
        logger.info(f"Getting top {n} {stat_type} players for {season}")
        
        # Try model first for shrunk estimates
        if self.player_model:
            try:
                top = self.player_model.get_top_players(
                    stat_type=stat_type,
                    metric='epa_per_play',
                    min_attempts=min_attempts,
                    n=n
                )
                
                if top:
                    return {
                        'stat_type': stat_type,
                        'season': season,
                        'min_attempts': min_attempts,
                        'players': top,
                        'note': 'Rankings use Bayesian shrinkage estimates',
                        'sources': ['player_estimates']
                    }
            except Exception as e:
                logger.warning(f"Player model query failed: {e}")
        
        # Fall back to database
        cursor = self.db_conn.cursor()
        
        if stat_type == 'rushing':
            cursor.execute("""
                SELECT player_id, rush_attempts, rush_epa, rush_success_rate
                FROM player_season_stats
                WHERE season = %s AND rush_attempts >= %s
                ORDER BY rush_epa DESC
                LIMIT %s
            """, (season, min_attempts, n))
            
            rows = cursor.fetchall()
            players = [{
                'rank': i,
                'player_id': row[0],
                'attempts': int(row[1]),
                'epa_per_play': float(row[2]) if row[2] else 0,
                'success_rate': float(row[3]) if row[3] else 0,
            } for i, row in enumerate(rows, 1)]
            
        elif stat_type == 'passing':
            cursor.execute("""
                SELECT player_id, pass_attempts, pass_epa, pass_success_rate
                FROM player_season_stats
                WHERE season = %s AND pass_attempts >= %s
                ORDER BY pass_epa DESC
                LIMIT %s
            """, (season, min_attempts, n))
            
            rows = cursor.fetchall()
            players = [{
                'rank': i,
                'player_id': row[0],
                'attempts': int(row[1]),
                'epa_per_play': float(row[2]) if row[2] else 0,
                'success_rate': float(row[3]) if row[3] else 0,
            } for i, row in enumerate(rows, 1)]
            
        else:  # receiving
            cursor.execute("""
                SELECT player_id, targets, rec_epa, rec_success_rate
                FROM player_season_stats
                WHERE season = %s AND targets >= %s
                ORDER BY rec_epa DESC
                LIMIT %s
            """, (season, min_attempts, n))
            
            rows = cursor.fetchall()
            players = [{
                'rank': i,
                'player_id': row[0],
                'targets': int(row[1]),
                'epa_per_play': float(row[2]) if row[2] else 0,
                'success_rate': float(row[3]) if row[3] else 0,
            } for i, row in enumerate(rows, 1)]
        
        return {
            'stat_type': stat_type,
            'season': season,
            'min_attempts': min_attempts,
            'players': players,
            'sources': ['player_season_stats']
        }
    
    def compare_players(self, player_id_1: str, player_id_2: str, 
                       season: int = 2023) -> Dict:
        """
        Compare two players.
        
        Args:
            player_id_1: First player ID
            player_id_2: Second player ID
            season: Season year
            
        Returns:
            Comparison dictionary
        """
        # Try model comparison first
        if self.player_model:
            try:
                comparison = self.player_model.compare_players(player_id_1, player_id_2)
                if 'error' not in comparison:
                    return {
                        **comparison,
                        'season': season,
                        'sources': ['player_estimates']
                    }
            except Exception as e:
                logger.warning(f"Model comparison failed: {e}")
        
        # Fall back to database
        p1 = self.get_player_stats(player_id_1, season)
        p2 = self.get_player_stats(player_id_2, season)
        
        return {
            'player_1': p1,
            'player_2': p2,
            'season': season,
            'sources': ['player_season_stats']
        }
