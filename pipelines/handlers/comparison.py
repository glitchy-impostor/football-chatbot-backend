"""
Comparison Handler

Handles queries comparing teams or players.
"""

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class ComparisonHandler:
    """Handler for comparison queries."""
    
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
    
    def compare_teams(self, team1: str, team2: str, season: int = 2023) -> Dict:
        """
        Compare two teams.
        
        Args:
            team1: First team abbreviation
            team2: Second team abbreviation
            season: Season year
            
        Returns:
            Comparison dictionary
        """
        logger.info(f"Comparing {team1} vs {team2} for {season}")
        
        # Try profiler first
        if self.profiler:
            try:
                comparison = self.profiler.compare_teams(team1, team2, season)
                comparison['sources'] = ['team_profiles']
                return comparison
            except Exception as e:
                logger.warning(f"Profiler comparison failed: {e}")
        
        # Fall back to database
        cursor = self.db_conn.cursor()
        
        cursor.execute("""
            SELECT 
                team,
                off_epa_per_play, def_epa_per_play,
                off_success_rate, def_success_rate,
                pass_rate, total_plays
            FROM team_season_stats
            WHERE season = %s AND team IN (%s, %s)
        """, (season, team1, team2))
        
        rows = cursor.fetchall()
        
        if len(rows) < 2:
            return {
                'team1': team1,
                'team2': team2,
                'season': season,
                'error': 'One or both teams not found',
                'sources': []
            }
        
        # Build comparison
        teams_data = {}
        for row in rows:
            teams_data[row[0]] = {
                'off_epa_per_play': float(row[1]) if row[1] else 0,
                'def_epa_per_play': float(row[2]) if row[2] else 0,
                'off_success_rate': float(row[3]) if row[3] else 0,
                'def_success_rate': float(row[4]) if row[4] else 0,
                'pass_rate': float(row[5]) if row[5] else 0,
                'total_plays': int(row[6]) if row[6] else 0,
            }
        
        t1 = teams_data.get(team1, {})
        t2 = teams_data.get(team2, {})
        
        # Calculate differences
        comparison = {
            'teams': [team1, team2],
            'season': season,
            'team1_stats': t1,
            'team2_stats': t2,
            'differences': {
                'off_epa': round(t1.get('off_epa_per_play', 0) - t2.get('off_epa_per_play', 0), 4),
                'def_epa': round(t1.get('def_epa_per_play', 0) - t2.get('def_epa_per_play', 0), 4),
                'pass_rate': round(t1.get('pass_rate', 0) - t2.get('pass_rate', 0), 3),
            },
            'advantages': [],
            'sources': ['team_season_stats']
        }
        
        # Determine advantages
        if comparison['differences']['off_epa'] > 0.02:
            comparison['advantages'].append(f"{team1} has better offense (+{comparison['differences']['off_epa']:.3f} EPA/play)")
        elif comparison['differences']['off_epa'] < -0.02:
            comparison['advantages'].append(f"{team2} has better offense (+{-comparison['differences']['off_epa']:.3f} EPA/play)")
        
        # For defense, lower EPA is better
        if comparison['differences']['def_epa'] < -0.02:
            comparison['advantages'].append(f"{team1} has better defense ({comparison['differences']['def_epa']:.3f} EPA/play)")
        elif comparison['differences']['def_epa'] > 0.02:
            comparison['advantages'].append(f"{team2} has better defense ({-comparison['differences']['def_epa']:.3f} EPA/play)")
        
        return comparison
    
    def compare_situational(self, team1: str, team2: str, 
                           down: int, ydstogo: int, season: int = 2023) -> Dict:
        """
        Compare two teams in a specific situation.
        
        Args:
            team1: First team abbreviation
            team2: Second team abbreviation
            down: Down number
            ydstogo: Yards to first down
            season: Season year
            
        Returns:
            Situational comparison
        """
        cursor = self.db_conn.cursor()
        
        # Determine distance bucket
        if ydstogo <= 3:
            distance_bucket = 'short'
        elif ydstogo <= 7:
            distance_bucket = 'medium'
        else:
            distance_bucket = 'long'
        
        cursor.execute("""
            SELECT 
                team,
                pass_rate, epa_avg, success_rate, sample_size
            FROM situational_tendencies
            WHERE season = %s 
              AND down = %s 
              AND distance_bucket = %s
              AND team IN (%s, %s)
        """, (season, down, distance_bucket, team1, team2))
        
        rows = cursor.fetchall()
        
        teams_data = {}
        for row in rows:
            teams_data[row[0]] = {
                'pass_rate': float(row[1]) if row[1] else 0,
                'epa_avg': float(row[2]) if row[2] else 0,
                'success_rate': float(row[3]) if row[3] else 0,
                'sample_size': int(row[4]) if row[4] else 0,
            }
        
        return {
            'teams': [team1, team2],
            'season': season,
            'situation': {
                'down': down,
                'ydstogo': ydstogo,
                'distance_bucket': distance_bucket,
            },
            'team1_stats': teams_data.get(team1, {}),
            'team2_stats': teams_data.get(team2, {}),
            'sources': ['situational_tendencies']
        }
    
    def get_matchup_analysis(self, offense_team: str, defense_team: str, 
                            season: int = 2023) -> Dict:
        """
        Analyze offensive vs defensive matchup.
        
        Args:
            offense_team: Offensive team
            defense_team: Defensive team
            season: Season year
            
        Returns:
            Matchup analysis
        """
        cursor = self.db_conn.cursor()
        
        # Get offense stats
        cursor.execute("""
            SELECT off_epa_per_play, off_success_rate, pass_rate
            FROM team_season_stats
            WHERE team = %s AND season = %s
        """, (offense_team, season))
        
        off_row = cursor.fetchone()
        
        # Get defense stats
        cursor.execute("""
            SELECT def_epa_per_play, def_success_rate
            FROM team_season_stats
            WHERE team = %s AND season = %s
        """, (defense_team, season))
        
        def_row = cursor.fetchone()
        
        if not off_row or not def_row:
            return {
                'offense': offense_team,
                'defense': defense_team,
                'season': season,
                'error': 'Teams not found',
                'sources': []
            }
        
        # Analyze matchup
        off_epa = float(off_row[0]) if off_row[0] else 0
        def_epa = float(def_row[0]) if def_row[0] else 0
        
        # Combined expected EPA (rough estimate)
        # If offense is +0.1 and defense is -0.05, expected is around +0.05
        combined_epa = (off_epa + def_epa) / 2
        
        analysis = {
            'offense': offense_team,
            'defense': defense_team,
            'season': season,
            'offense_stats': {
                'epa_per_play': off_epa,
                'success_rate': float(off_row[1]) if off_row[1] else 0,
                'pass_rate': float(off_row[2]) if off_row[2] else 0,
            },
            'defense_stats': {
                'epa_allowed': def_epa,
                'success_rate_allowed': float(def_row[1]) if def_row[1] else 0,
            },
            'expected_epa': round(combined_epa, 4),
            'matchup_notes': [],
            'sources': ['team_season_stats']
        }
        
        # Generate matchup notes
        if off_epa > 0.1 and def_epa > 0:
            analysis['matchup_notes'].append(
                f"{offense_team}'s strong offense vs {defense_team}'s below-average defense favors the offense"
            )
        elif off_epa < -0.05 and def_epa < -0.1:
            analysis['matchup_notes'].append(
                f"{defense_team}'s strong defense vs {offense_team}'s struggling offense favors the defense"
            )
        
        return analysis
