"""
Team Identity Profiles

Quantifies how each team differs from league average in tendencies and effectiveness.
Used to provide team-specific recommendations and context.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
import json
import logging

logger = logging.getLogger(__name__)


# Situation buckets for profiling
DISTANCE_BUCKETS = {
    'short': (1, 3),
    'medium': (4, 7),
    'long': (8, 99),
}

FIELD_ZONES = {
    'own_deep': (80, 100),
    'own_territory': (51, 79),
    'opp_territory': (21, 50),
    'red_zone': (1, 20),
}

SCORE_BUCKETS = {
    'losing_big': (-99, -15),
    'losing': (-14, -1),
    'tied': (0, 0),
    'winning': (1, 14),
    'winning_big': (15, 99),
}


class TeamProfiler:
    """
    Builds and manages team identity profiles.
    """
    
    def __init__(self):
        self.profiles: Dict[str, Dict] = {}  # {team_season: profile}
        self.league_averages: Dict[str, Dict] = {}  # {season: averages}
        
    def _get_distance_bucket(self, ydstogo: int) -> str:
        """Categorize yards to go."""
        for bucket, (low, high) in DISTANCE_BUCKETS.items():
            if low <= ydstogo <= high:
                return bucket
        return 'long'
    
    def _get_field_zone(self, yardline_100: int) -> str:
        """Categorize field position."""
        for zone, (low, high) in FIELD_ZONES.items():
            if low <= yardline_100 <= high:
                return zone
        return 'own_territory'
    
    def _get_score_bucket(self, score_diff: int) -> str:
        """Categorize score differential."""
        for bucket, (low, high) in SCORE_BUCKETS.items():
            if low <= score_diff <= high:
                return bucket
        return 'tied'
    
    def build_league_averages(self, conn, season: int) -> Dict:
        """
        Calculate league-wide averages for a season.
        
        Args:
            conn: Database connection
            season: Season year
            
        Returns:
            Dictionary of league averages
        """
        logger.info(f"Building league averages for {season}...")
        
        # Overall stats
        overall_query = """
            SELECT 
                AVG(CASE WHEN pass = 1 THEN 1.0 ELSE 0.0 END) as pass_rate,
                AVG(epa) as epa_per_play,
                AVG(CASE WHEN success = 1 THEN 1.0 ELSE 0.0 END) as success_rate,
                AVG(CASE WHEN shotgun = 1 THEN 1.0 ELSE 0.0 END) as shotgun_rate,
                AVG(CASE WHEN no_huddle = 1 THEN 1.0 ELSE 0.0 END) as no_huddle_rate,
                AVG(CASE WHEN yards_gained >= 20 THEN 1.0 ELSE 0.0 END) as explosive_rate,
                COUNT(*) as total_plays
            FROM plays
            WHERE season = %s AND play_type IN ('pass', 'run')
        """
        
        overall = pd.read_sql(overall_query, conn, params=[season]).iloc[0].to_dict()
        
        # Situational averages
        situational_query = """
            SELECT 
                down,
                CASE 
                    WHEN ydstogo <= 3 THEN 'short'
                    WHEN ydstogo <= 7 THEN 'medium'
                    ELSE 'long'
                END as distance_bucket,
                AVG(CASE WHEN pass = 1 THEN 1.0 ELSE 0.0 END) as pass_rate,
                AVG(epa) as epa_per_play,
                AVG(CASE WHEN success = 1 THEN 1.0 ELSE 0.0 END) as success_rate,
                COUNT(*) as sample_size
            FROM plays
            WHERE season = %s 
              AND play_type IN ('pass', 'run')
              AND down IS NOT NULL
            GROUP BY down, 
                CASE 
                    WHEN ydstogo <= 3 THEN 'short'
                    WHEN ydstogo <= 7 THEN 'medium'
                    ELSE 'long'
                END
        """
        
        situational = pd.read_sql(situational_query, conn, params=[season])
        
        # Convert to nested dict
        situational_dict = {}
        for _, row in situational.iterrows():
            key = f"down{int(row['down'])}_{row['distance_bucket']}"
            situational_dict[key] = {
                'pass_rate': float(row['pass_rate']),
                'epa_per_play': float(row['epa_per_play']),
                'success_rate': float(row['success_rate']),
                'sample_size': int(row['sample_size']),
            }
        
        averages = {
            'season': season,
            'overall': {k: float(v) if isinstance(v, (np.floating, float)) else int(v) 
                       for k, v in overall.items()},
            'situational': situational_dict,
        }
        
        self.league_averages[season] = averages
        return averages
    
    def build_team_profile(self, conn, team: str, season: int) -> Dict:
        """
        Build a complete profile for a team-season.
        
        Args:
            conn: Database connection
            team: Team abbreviation
            season: Season year
            
        Returns:
            Team profile dictionary
        """
        logger.info(f"Building profile for {team} {season}...")
        
        # Ensure we have league averages
        if season not in self.league_averages:
            self.build_league_averages(conn, season)
        
        league = self.league_averages[season]
        
        # Team overall stats
        overall_query = """
            SELECT 
                AVG(CASE WHEN pass = 1 THEN 1.0 ELSE 0.0 END) as pass_rate,
                AVG(epa) as epa_per_play,
                AVG(CASE WHEN success = 1 THEN 1.0 ELSE 0.0 END) as success_rate,
                AVG(CASE WHEN shotgun = 1 THEN 1.0 ELSE 0.0 END) as shotgun_rate,
                AVG(CASE WHEN no_huddle = 1 THEN 1.0 ELSE 0.0 END) as no_huddle_rate,
                AVG(CASE WHEN yards_gained >= 20 THEN 1.0 ELSE 0.0 END) as explosive_rate,
                AVG(CASE WHEN pass = 1 THEN epa ELSE NULL END) as pass_epa,
                AVG(CASE WHEN rush = 1 THEN epa ELSE NULL END) as rush_epa,
                COUNT(*) as total_plays
            FROM plays
            WHERE season = %s AND posteam = %s AND play_type IN ('pass', 'run')
        """
        
        team_overall = pd.read_sql(overall_query, conn, params=[season, team]).iloc[0]
        
        # Defense stats
        defense_query = """
            SELECT 
                AVG(epa) as def_epa_per_play,
                AVG(CASE WHEN success = 1 THEN 1.0 ELSE 0.0 END) as def_success_rate,
                AVG(CASE WHEN pass = 1 THEN epa ELSE NULL END) as def_pass_epa,
                AVG(CASE WHEN rush = 1 THEN epa ELSE NULL END) as def_rush_epa,
                COUNT(*) as def_plays
            FROM plays
            WHERE season = %s AND defteam = %s AND play_type IN ('pass', 'run')
        """
        
        team_defense = pd.read_sql(defense_query, conn, params=[season, team]).iloc[0]
        
        # Situational stats
        situational_query = """
            SELECT 
                down,
                CASE 
                    WHEN ydstogo <= 3 THEN 'short'
                    WHEN ydstogo <= 7 THEN 'medium'
                    ELSE 'long'
                END as distance_bucket,
                AVG(CASE WHEN pass = 1 THEN 1.0 ELSE 0.0 END) as pass_rate,
                AVG(epa) as epa_per_play,
                AVG(CASE WHEN success = 1 THEN 1.0 ELSE 0.0 END) as success_rate,
                COUNT(*) as sample_size
            FROM plays
            WHERE season = %s AND posteam = %s
              AND play_type IN ('pass', 'run')
              AND down IS NOT NULL
            GROUP BY down, 
                CASE 
                    WHEN ydstogo <= 3 THEN 'short'
                    WHEN ydstogo <= 7 THEN 'medium'
                    ELSE 'long'
                END
            HAVING COUNT(*) >= 10
        """
        
        team_situational = pd.read_sql(situational_query, conn, params=[season, team])
        
        # Calculate deviations from league average
        overall_deviations = {
            'pass_rate': float(team_overall['pass_rate']) - league['overall']['pass_rate'],
            'epa_per_play': float(team_overall['epa_per_play']) - league['overall']['epa_per_play'],
            'success_rate': float(team_overall['success_rate']) - league['overall']['success_rate'],
            'shotgun_rate': float(team_overall['shotgun_rate']) - league['overall']['shotgun_rate'],
            'explosive_rate': float(team_overall['explosive_rate']) - league['overall']['explosive_rate'],
        }
        
        # Situational deviations
        situational_deviations = {}
        for _, row in team_situational.iterrows():
            key = f"down{int(row['down'])}_{row['distance_bucket']}"
            league_sit = league['situational'].get(key, {})
            
            if league_sit:
                situational_deviations[key] = {
                    'pass_rate_vs_league': float(row['pass_rate']) - league_sit['pass_rate'],
                    'epa_vs_league': float(row['epa_per_play']) - league_sit['epa_per_play'],
                    'success_rate_vs_league': float(row['success_rate']) - league_sit['success_rate'],
                    'team_pass_rate': float(row['pass_rate']),
                    'team_epa': float(row['epa_per_play']),
                    'sample_size': int(row['sample_size']),
                }
        
        # Identify strengths and weaknesses
        strengths = []
        weaknesses = []
        
        if overall_deviations['epa_per_play'] > 0.05:
            strengths.append('offensive_efficiency')
        elif overall_deviations['epa_per_play'] < -0.05:
            weaknesses.append('offensive_efficiency')
            
        if float(team_overall['pass_epa'] or 0) > 0.1:
            strengths.append('passing_attack')
        if float(team_overall['rush_epa'] or 0) > 0.05:
            strengths.append('rushing_attack')
            
        if float(team_defense['def_epa_per_play'] or 0) < -0.05:
            strengths.append('overall_defense')
        elif float(team_defense['def_epa_per_play'] or 0) > 0.05:
            weaknesses.append('overall_defense')
        
        # Build final profile
        profile = {
            'team': team,
            'season': season,
            'overall': {
                'pass_rate': float(team_overall['pass_rate']),
                'epa_per_play': float(team_overall['epa_per_play']),
                'success_rate': float(team_overall['success_rate']),
                'shotgun_rate': float(team_overall['shotgun_rate']),
                'no_huddle_rate': float(team_overall['no_huddle_rate']),
                'explosive_rate': float(team_overall['explosive_rate']),
                'pass_epa': float(team_overall['pass_epa'] or 0),
                'rush_epa': float(team_overall['rush_epa'] or 0),
                'total_plays': int(team_overall['total_plays']),
            },
            'defense': {
                'epa_per_play': float(team_defense['def_epa_per_play'] or 0),
                'success_rate': float(team_defense['def_success_rate'] or 0),
                'pass_epa': float(team_defense['def_pass_epa'] or 0),
                'rush_epa': float(team_defense['def_rush_epa'] or 0),
            },
            'deviations': overall_deviations,
            'situational': situational_deviations,
            'strengths': strengths,
            'weaknesses': weaknesses,
        }
        
        # Cache it
        key = f"{team}_{season}"
        self.profiles[key] = profile
        
        return profile
    
    def build_all_profiles(self, conn, season: int) -> Dict[str, Dict]:
        """
        Build profiles for all teams in a season.
        
        Args:
            conn: Database connection
            season: Season year
            
        Returns:
            Dictionary of all team profiles
        """
        # Get all teams
        teams_query = """
            SELECT DISTINCT posteam FROM plays 
            WHERE season = %s AND posteam IS NOT NULL
        """
        teams = pd.read_sql(teams_query, conn, params=[season])['posteam'].tolist()
        
        logger.info(f"Building profiles for {len(teams)} teams...")
        
        profiles = {}
        for team in teams:
            profile = self.build_team_profile(conn, team, season)
            profiles[team] = profile
        
        return profiles
    
    def get_profile(self, team: str, season: int) -> Optional[Dict]:
        """Get a cached team profile."""
        key = f"{team}_{season}"
        return self.profiles.get(key)
    
    def compare_teams(self, team1: str, team2: str, season: int) -> Dict:
        """
        Compare two teams' profiles.
        
        Args:
            team1: First team abbreviation
            team2: Second team abbreviation
            season: Season year
            
        Returns:
            Comparison dictionary
        """
        p1 = self.get_profile(team1, season)
        p2 = self.get_profile(team2, season)
        
        if not p1 or not p2:
            raise ValueError("One or both team profiles not found")
        
        comparison = {
            'teams': [team1, team2],
            'season': season,
            'offense': {
                'epa_per_play': [p1['overall']['epa_per_play'], p2['overall']['epa_per_play']],
                'pass_rate': [p1['overall']['pass_rate'], p2['overall']['pass_rate']],
                'success_rate': [p1['overall']['success_rate'], p2['overall']['success_rate']],
            },
            'defense': {
                'epa_per_play': [p1['defense']['epa_per_play'], p2['defense']['epa_per_play']],
            },
            'matchup_notes': [],
        }
        
        # Generate matchup notes
        if p1['overall']['pass_epa'] > 0.1 and p2['defense']['pass_epa'] > 0:
            comparison['matchup_notes'].append(
                f"{team1}'s strong passing attack vs {team2}'s weak pass defense"
            )
        
        if p1['overall']['rush_epa'] > 0.05 and p2['defense']['rush_epa'] > 0:
            comparison['matchup_notes'].append(
                f"{team1}'s effective run game vs {team2}'s poor run defense"
            )
        
        return comparison
    
    def get_situational_recommendation(self, team: str, season: int,
                                       down: int, distance_bucket: str) -> Dict:
        """
        Get team-specific recommendation for a situation.
        
        Args:
            team: Team abbreviation
            season: Season year
            down: Down number
            distance_bucket: 'short', 'medium', or 'long'
            
        Returns:
            Recommendation dictionary
        """
        profile = self.get_profile(team, season)
        if not profile:
            return {'error': 'Profile not found'}
        
        key = f"down{down}_{distance_bucket}"
        sit_data = profile['situational'].get(key)
        
        if not sit_data:
            return {
                'situation': key,
                'recommendation': 'neutral',
                'note': 'Insufficient data for this situation'
            }
        
        # Check if team deviates significantly from league
        pass_diff = sit_data['pass_rate_vs_league']
        epa_diff = sit_data['epa_vs_league']
        
        if pass_diff > 0.1 and epa_diff > 0:
            tendency = 'pass_heavy_effective'
            note = f"{team} passes more than average here (+{pass_diff:.0%}) and it's working (+{epa_diff:.2f} EPA)"
        elif pass_diff > 0.1 and epa_diff < 0:
            tendency = 'pass_heavy_ineffective'
            note = f"{team} passes more than average here (+{pass_diff:.0%}) but it's not working ({epa_diff:.2f} EPA)"
        elif pass_diff < -0.1 and epa_diff > 0:
            tendency = 'run_heavy_effective'
            note = f"{team} runs more than average here ({pass_diff:.0%} pass rate vs league) and it's working"
        elif pass_diff < -0.1 and epa_diff < 0:
            tendency = 'run_heavy_ineffective'
            note = f"{team} runs more than average here but it's not working"
        else:
            tendency = 'balanced'
            note = f"{team} is close to league average in this situation"
        
        return {
            'team': team,
            'situation': key,
            'tendency': tendency,
            'team_pass_rate': sit_data['team_pass_rate'],
            'pass_rate_vs_league': sit_data['pass_rate_vs_league'],
            'epa_vs_league': sit_data['epa_vs_league'],
            'sample_size': sit_data['sample_size'],
            'note': note,
        }
    
    def save(self, filepath: str):
        """Save all profiles to JSON file."""
        data = {
            'profiles': self.profiles,
            'league_averages': self.league_averages,
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Profiles saved to {filepath}")
    
    @classmethod
    def load(cls, filepath: str) -> 'TeamProfiler':
        """Load profiles from JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        profiler = cls()
        profiler.profiles = data['profiles']
        profiler.league_averages = data['league_averages']
        
        logger.info(f"Loaded {len(profiler.profiles)} profiles from {filepath}")
        return profiler
