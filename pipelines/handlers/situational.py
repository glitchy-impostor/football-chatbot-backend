"""
Situational Analysis Handler

Handles queries about down/distance/field position tendencies.
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class SituationalHandler:
    """Handler for situational analysis queries."""
    
    DISTANCE_BUCKETS = {
        'short': (1, 3),
        'medium': (4, 7),
        'long': (8, 99),
    }
    
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
    
    def _get_distance_bucket(self, ydstogo: int) -> str:
        """Get distance bucket for yards to go."""
        for bucket, (low, high) in self.DISTANCE_BUCKETS.items():
            if low <= ydstogo <= high:
                return bucket
        return 'long'
    
    def get_situational_stats(self, down: int = None, ydstogo: int = None,
                             team: str = None, season: int = 2023,
                             zone: str = None, **kwargs) -> Dict:
        """
        Get situational statistics.
        
        Args:
            down: Down number (1-4)
            ydstogo: Yards to first down
            team: Team abbreviation (None for league average)
            season: Season year
            zone: Field zone ('red_zone', 'goal_line', etc.)
            
        Returns:
            Dictionary with situational stats
        """
        logger.info(f"Getting situational stats: down={down}, ydstogo={ydstogo}, team={team}")
        
        cursor = self.db_conn.cursor()
        
        # Build query conditions
        conditions = ["season = %s"]
        params = [season]
        
        if team:
            conditions.append("team = %s")
            params.append(team)
        else:
            conditions.append("team IS NULL")  # League average
        
        if down:
            conditions.append("down = %s")
            params.append(down)
        
        if ydstogo:
            distance_bucket = self._get_distance_bucket(ydstogo)
            conditions.append("distance_bucket = %s")
            params.append(distance_bucket)
        
        if zone:
            conditions.append("field_zone = %s")
            params.append(zone)
        
        query = f"""
            SELECT 
                down, distance_bucket, field_zone, score_bucket,
                pass_rate, epa_avg, success_rate, sample_size
            FROM situational_tendencies
            WHERE {' AND '.join(conditions)}
            ORDER BY sample_size DESC
            LIMIT 20
        """
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        if not rows:
            # Try without team for comparison
            return {
                'team': team,
                'season': season,
                'down': down,
                'ydstogo': ydstogo,
                'situations': [],
                'note': 'No data found for this situation',
                'sources': ['situational_tendencies']
            }
        
        situations = []
        for row in rows:
            situations.append({
                'down': int(row[0]) if row[0] else None,
                'distance_bucket': row[1],
                'field_zone': row[2],
                'score_bucket': row[3],
                'pass_rate': float(row[4]) if row[4] else 0,
                'epa_avg': float(row[5]) if row[5] else 0,
                'success_rate': float(row[6]) if row[6] else 0,
                'sample_size': int(row[7]) if row[7] else 0,
            })
        
        # Get league average for comparison if team specified
        league_avg = None
        if team:
            league_conditions = ["season = %s", "team IS NULL"]
            league_params = [season]
            
            if down:
                league_conditions.append("down = %s")
                league_params.append(down)
            
            if ydstogo:
                league_conditions.append("distance_bucket = %s")
                league_params.append(distance_bucket)
            
            league_query = f"""
                SELECT AVG(pass_rate), AVG(epa_avg), AVG(success_rate), SUM(sample_size)
                FROM situational_tendencies
                WHERE {' AND '.join(league_conditions)}
            """
            
            cursor.execute(league_query, league_params)
            league_row = cursor.fetchone()
            
            if league_row and league_row[0]:
                league_avg = {
                    'pass_rate': float(league_row[0]),
                    'epa_avg': float(league_row[1]) if league_row[1] else 0,
                    'success_rate': float(league_row[2]) if league_row[2] else 0,
                    'sample_size': int(league_row[3]) if league_row[3] else 0,
                }
        
        result = {
            'team': team,
            'season': season,
            'down': down,
            'ydstogo': ydstogo,
            'distance_bucket': self._get_distance_bucket(ydstogo) if ydstogo else None,
            'situations': situations,
            'sources': ['situational_tendencies']
        }
        
        if league_avg:
            result['league_average'] = league_avg
            
            # Calculate deviation from league
            if situations:
                team_pass_rate = situations[0]['pass_rate']
                result['pass_rate_vs_league'] = round(team_pass_rate - league_avg['pass_rate'], 3)
        
        return result
    
    def get_third_down_analysis(self, team: str = None, season: int = 2023) -> Dict:
        """
        Get third down analysis for a team.
        
        Args:
            team: Team abbreviation (None for league)
            season: Season year
            
        Returns:
            Third down analysis
        """
        cursor = self.db_conn.cursor()
        
        if team:
            cursor.execute("""
                SELECT 
                    distance_bucket,
                    pass_rate, epa_avg, success_rate, sample_size
                FROM situational_tendencies
                WHERE season = %s AND team = %s AND down = 3
                ORDER BY 
                    CASE distance_bucket 
                        WHEN 'short' THEN 1 
                        WHEN 'medium' THEN 2 
                        ELSE 3 
                    END
            """, (season, team))
        else:
            cursor.execute("""
                SELECT 
                    distance_bucket,
                    AVG(pass_rate), AVG(epa_avg), AVG(success_rate), SUM(sample_size)
                FROM situational_tendencies
                WHERE season = %s AND team IS NULL AND down = 3
                GROUP BY distance_bucket
                ORDER BY 
                    CASE distance_bucket 
                        WHEN 'short' THEN 1 
                        WHEN 'medium' THEN 2 
                        ELSE 3 
                    END
            """, (season,))
        
        rows = cursor.fetchall()
        
        analysis = {
            'team': team,
            'season': season,
            'down': 3,
            'by_distance': {},
            'sources': ['situational_tendencies']
        }
        
        for row in rows:
            analysis['by_distance'][row[0]] = {
                'pass_rate': float(row[1]) if row[1] else 0,
                'epa_avg': float(row[2]) if row[2] else 0,
                'success_rate': float(row[3]) if row[3] else 0,
                'sample_size': int(row[4]) if row[4] else 0,
            }
        
        return analysis
    
    def get_red_zone_analysis(self, team: str = None, season: int = 2023) -> Dict:
        """
        Get red zone analysis for a team.
        
        Args:
            team: Team abbreviation (None for league)
            season: Season year
            
        Returns:
            Red zone analysis
        """
        cursor = self.db_conn.cursor()
        
        if team:
            cursor.execute("""
                SELECT 
                    down,
                    pass_rate, epa_avg, success_rate, sample_size
                FROM situational_tendencies
                WHERE season = %s AND team = %s AND field_zone = 'red_zone'
                ORDER BY down
            """, (season, team))
        else:
            cursor.execute("""
                SELECT 
                    down,
                    AVG(pass_rate), AVG(epa_avg), AVG(success_rate), SUM(sample_size)
                FROM situational_tendencies
                WHERE season = %s AND team IS NULL AND field_zone = 'red_zone'
                GROUP BY down
                ORDER BY down
            """, (season,))
        
        rows = cursor.fetchall()
        
        analysis = {
            'team': team,
            'season': season,
            'zone': 'red_zone',
            'by_down': {},
            'sources': ['situational_tendencies']
        }
        
        for row in rows:
            down = int(row[0]) if row[0] else 0
            analysis['by_down'][down] = {
                'pass_rate': float(row[1]) if row[1] else 0,
                'epa_avg': float(row[2]) if row[2] else 0,
                'success_rate': float(row[3]) if row[3] else 0,
                'sample_size': int(row[4]) if row[4] else 0,
            }
        
        return analysis
