"""
Pipeline Executor

Executes analysis pipelines and coordinates model calls.
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging
import psycopg2
import pandas as pd

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.epa_model import EPAPredictor
from models.team_profiles import TeamProfiler
from models.player_effectiveness import PlayerEffectivenessModel
from models.drive_simulator import DriveSimulator
from pipelines.router import PipelineType, RouteResult

logger = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://127.0.0.1:5432/football_analytics")
MODEL_DIR = Path("data/models")


class PipelineExecutor:
    """
    Executes analysis pipelines using trained models.
    """
    
    def __init__(self, model_dir: Path = MODEL_DIR):
        self.model_dir = model_dir
        self._epa_model = None
        self._team_profiler = None
        self._player_model = None
        self._drive_simulator = None
        self._db_conn = None
    
    @property
    def epa_model(self) -> EPAPredictor:
        """Lazy load EPA model."""
        if self._epa_model is None:
            model_path = self.model_dir / "epa_model.joblib"
            if model_path.exists():
                self._epa_model = EPAPredictor.load(str(model_path))
            else:
                raise FileNotFoundError(f"EPA model not found at {model_path}")
        return self._epa_model
    
    @property
    def team_profiler(self) -> TeamProfiler:
        """Lazy load team profiler."""
        if self._team_profiler is None:
            profile_path = self.model_dir / "team_profiles.json"
            if profile_path.exists():
                self._team_profiler = TeamProfiler.load(str(profile_path))
            else:
                raise FileNotFoundError(f"Team profiles not found at {profile_path}")
        return self._team_profiler
    
    @property
    def player_model(self) -> PlayerEffectivenessModel:
        """Lazy load player model."""
        if self._player_model is None:
            model_path = self.model_dir / "player_estimates.json"
            if model_path.exists():
                self._player_model = PlayerEffectivenessModel.load(str(model_path))
            else:
                raise FileNotFoundError(f"Player model not found at {model_path}")
        return self._player_model
    
    @property
    def drive_simulator(self) -> DriveSimulator:
        """Lazy load drive simulator."""
        if self._drive_simulator is None:
            self._drive_simulator = DriveSimulator()
            conn = self._get_db_connection()
            self._drive_simulator.load_distributions(conn)
        return self._drive_simulator
    
    def _get_db_connection(self):
        """Get database connection."""
        if self._db_conn is None or self._db_conn.closed:
            self._db_conn = psycopg2.connect(DATABASE_URL)
        return self._db_conn
    
    def execute(self, route: RouteResult) -> Dict[str, Any]:
        """
        Execute a pipeline based on routing result.
        
        Args:
            route: RouteResult from QueryRouter
            
        Returns:
            Dictionary with analysis results
        """
        pipeline = route.pipeline
        params = route.extracted_params
        
        try:
            if pipeline == PipelineType.TEAM_PROFILE:
                return self._execute_team_profile(params)
            
            elif pipeline == PipelineType.TEAM_COMPARISON:
                return self._execute_team_comparison(params)
            
            elif pipeline == PipelineType.TEAM_TENDENCIES:
                return self._execute_team_tendencies(params)
            
            elif pipeline == PipelineType.SITUATION_EPA:
                return self._execute_situation_epa(params)
            
            elif pipeline == PipelineType.DECISION_ANALYSIS:
                return self._execute_decision_analysis(params)
            
            elif pipeline == PipelineType.PLAYER_RANKINGS:
                return self._execute_player_rankings(params)
            
            elif pipeline == PipelineType.PLAYER_COMPARISON:
                return self._execute_player_comparison(params)
            
            elif pipeline == PipelineType.DRIVE_SIMULATION:
                return self._execute_drive_simulation(params)
            
            elif pipeline == PipelineType.GENERAL_QUERY:
                return self._execute_general_query(params)
            
            else:
                return {
                    'success': False,
                    'error': f"Unknown pipeline: {pipeline}",
                    'pipeline': pipeline.value
                }
                
        except Exception as e:
            logger.error(f"Pipeline execution error: {e}")
            return {
                'success': False,
                'error': str(e),
                'pipeline': pipeline.value
            }
    
    def _execute_team_profile(self, params: Dict) -> Dict:
        """Execute team profile analysis."""
        team = params.get('team')
        season = params.get('season', 2025)
        
        if not team:
            return {
                'success': False,
                'error': 'No team specified',
                'pipeline': 'team_profile'
            }
        
        # Get profile
        profile = self.team_profiler.get_profile(team, season)
        
        if not profile:
            return {
                'success': False,
                'error': f'No profile found for {team} in {season}',
                'pipeline': 'team_profile'
            }
        
        return {
            'success': True,
            'pipeline': 'team_profile',
            'data': {
                'team': team,
                'season': season,
                'profile': profile
            }
        }
    
    def _execute_team_comparison(self, params: Dict) -> Dict:
        """Execute team comparison analysis."""
        team1 = params.get('team1') or params.get('team')
        team2 = params.get('team2')
        season = params.get('season', 2025)
        
        if not team1 or not team2:
            return {
                'success': False,
                'error': 'Two teams required for comparison',
                'pipeline': 'team_comparison'
            }
        
        # Normalize team names to uppercase
        team1 = team1.upper()
        team2 = team2.upper()
        
        try:
            # Check if profiles exist first
            profile1 = self.team_profiler.get_profile(team1, season)
            profile2 = self.team_profiler.get_profile(team2, season)
            
            if not profile1 or not profile2:
                # Try to identify which team is missing
                missing = []
                if not profile1:
                    missing.append(team1)
                if not profile2:
                    missing.append(team2)
                
                # List available teams for debugging
                available = list(set(k.split('_')[0] for k in self.team_profiler.profiles.keys()))
                
                return {
                    'success': False,
                    'error': f"Profile not found for: {', '.join(missing)}. Available teams: {', '.join(sorted(available)[:10])}...",
                    'pipeline': 'team_comparison'
                }
            
            comparison = self.team_profiler.compare_teams(team1, team2, season)
            
            return {
                'success': True,
                'pipeline': 'team_comparison',
                'data': {
                    'team1': team1,
                    'team2': team2,
                    'season': season,
                    'comparison': comparison,
                    'profile1': profile1,
                    'profile2': profile2
                }
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'pipeline': 'team_comparison'
            }
    
    def _execute_team_tendencies(self, params: Dict) -> Dict:
        """Execute team tendencies analysis."""
        team = params.get('team')
        season = params.get('season', 2025)
        down = params.get('down')
        distance = params.get('distance')
        
        if not team:
            return {
                'success': False,
                'error': 'No team specified',
                'pipeline': 'team_tendencies'
            }
        
        profile = self.team_profiler.get_profile(team, season)
        
        if not profile:
            return {
                'success': False,
                'error': f'No profile found for {team}',
                'pipeline': 'team_tendencies'
            }
        
        # Get specific situational data if down/distance provided
        situational = None
        if down:
            distance_bucket = 'short' if distance and distance <= 3 else 'medium' if distance and distance <= 7 else 'long'
            situational = self.team_profiler.get_situational_recommendation(
                team, season, down, distance_bucket
            )
        
        return {
            'success': True,
            'pipeline': 'team_tendencies',
            'data': {
                'team': team,
                'season': season,
                'overall_tendencies': {
                    'pass_rate': profile['overall']['pass_rate'],
                    'shotgun_rate': profile['overall']['shotgun_rate'],
                    'no_huddle_rate': profile['overall']['no_huddle_rate'],
                },
                'deviations': profile['deviations'],
                'situational': profile['situational'],
                'specific_situation': situational
            }
        }
    
    def _execute_situation_epa(self, params: Dict) -> Dict:
        """Execute situation EPA analysis."""
        down = params.get('down')
        distance = params.get('distance')
        yardline = params.get('yardline', 50)  # Default to midfield
        quarter = params.get('quarter', 2)
        score_diff = params.get('score_differential', 0)
        team = params.get('team')
        season = params.get('season', 2025)
        defenders_in_box = params.get('defenders_in_box')  # Optional defensive context
        
        if not down or not distance:
            return {
                'success': False,
                'error': 'Down and distance required',
                'pipeline': 'situation_epa'
            }
        
        # Get team adjustments if team specified
        team_pass_adj = 0.0
        team_run_adj = 0.0
        
        if team:
            profile = self.team_profiler.get_profile(team, season)
            if profile:
                team_pass_adj = profile['overall'].get('pass_epa', 0) - profile['overall'].get('epa_per_play', 0)
                team_run_adj = profile['overall'].get('rush_epa', 0) - profile['overall'].get('epa_per_play', 0)
        
        # Get EPA comparison (now with optional defenders_in_box)
        result = self.epa_model.compare_play_types(
            down=down,
            ydstogo=distance,
            yardline_100=yardline,
            quarter=quarter,
            score_differential=score_diff,
            team_pass_adjustment=team_pass_adj,
            team_run_adjustment=team_run_adj,
            defenders_in_box=defenders_in_box
        )
        
        # Build situation dict
        situation = {
            'down': down,
            'distance': distance,
            'yardline': yardline,
            'quarter': quarter,
            'score_differential': score_diff,
        }
        
        # Add defensive context if provided
        if defenders_in_box is not None:
            situation['defenders_in_box'] = defenders_in_box
        
        return {
            'success': True,
            'pipeline': 'situation_epa',
            'data': {
                'situation': situation,
                'team': team,
                'analysis': result,
                'team_adjustments': {
                    'pass_adjustment': round(team_pass_adj, 4),
                    'run_adjustment': round(team_run_adj, 4)
                } if team else None
            }
        }
    
    def _execute_decision_analysis(self, params: Dict) -> Dict:
        """Execute 4th down decision analysis."""
        down = params.get('down', 4)
        distance = params.get('distance')
        yardline = params.get('yardline') or 35  # Default to 35 if None or missing
        
        if not distance:
            return {
                'success': False,
                'error': 'Distance required for decision analysis',
                'pipeline': 'decision_analysis'
            }
        
        # Run simulation
        result = self.drive_simulator.simulate_decision(
            down=down,
            ydstogo=distance,
            yardline=yardline,
            n_simulations=5000
        )
        
        return {
            'success': True,
            'pipeline': 'decision_analysis',
            'data': result
        }
    
    def _execute_player_rankings(self, params: Dict) -> Dict:
        """Execute player rankings query."""
        position = params.get('position', 'RB')
        count = params.get('count', 10)
        metric = params.get('metric', 'epa')
        season = params.get('season', 2025)
        
        # Map position to stat type
        stat_type_map = {
            'QB': 'passing',
            'RB': 'rushing',
            'WR': 'receiving',
            'TE': 'receiving'
        }
        
        stat_type = stat_type_map.get(position, 'rushing')
        
        # Handle different metrics
        if metric.lower() in ['yards', 'yard', 'yardage', 'touchdowns', 'td', 'tds']:
            # Use direct database query for yards/TDs
            return self._execute_player_rankings_by_stats(position, stat_type, metric, count, season)
        
        # Default: Use EPA-based rankings from model
        metric_name = 'epa_per_play' if stat_type != 'receiving' else 'epa_per_target'
        
        # Get top players
        top_players = self.player_model.get_top_players(
            stat_type=stat_type,
            metric=metric_name,
            min_attempts=30,
            n=count
        )
        
        # Enrich with player names from database
        top_players = self._add_player_names(top_players)
        
        return {
            'success': True,
            'pipeline': 'player_rankings',
            'data': {
                'position': position,
                'stat_type': stat_type,
                'metric': metric_name,
                'count': len(top_players),
                'players': top_players
            }
        }
    
    def _execute_player_rankings_by_stats(self, position: str, stat_type: str, 
                                          metric: str, count: int, season: int) -> Dict:
        """Execute player rankings by traditional stats (yards, TDs)."""
        try:
            conn = self._get_db_connection()
            
            # Determine which columns to use based on stat type and metric
            if stat_type == 'passing':
                if 'td' in metric.lower():
                    order_col = 'pass_td'
                    metric_label = 'Passing TDs'
                else:
                    order_col = 'pass_yards'
                    metric_label = 'Passing Yards'
                min_filter = 'pass_attempts >= 100'
            elif stat_type == 'rushing':
                if 'td' in metric.lower():
                    order_col = 'rush_td'
                    metric_label = 'Rushing TDs'
                else:
                    order_col = 'rush_yards'
                    metric_label = 'Rushing Yards'
                min_filter = 'rush_attempts >= 50'
            else:  # receiving
                if 'td' in metric.lower():
                    order_col = 'rec_td'
                    metric_label = 'Receiving TDs'
                else:
                    order_col = 'rec_yards'
                    metric_label = 'Receiving Yards'
                min_filter = 'targets >= 30'
            
            query = f"""
                SELECT player_id, player_name, team, position,
                       {order_col} as stat_value,
                       pass_yards, pass_td, rush_yards, rush_td, rec_yards, rec_td
                FROM player_season_stats
                WHERE season = %s 
                  AND {min_filter}
                  AND player_name IS NOT NULL
                ORDER BY {order_col} DESC
                LIMIT %s
            """
            
            df = pd.read_sql(query, conn, params=[season, count])
            
            players = []
            for _, row in df.iterrows():
                players.append({
                    'player_id': row['player_id'],
                    'player_name': row['player_name'],
                    'team': row['team'],
                    'position': row['position'],
                    'stat_value': int(row['stat_value']) if pd.notna(row['stat_value']) else 0
                })
            
            return {
                'success': True,
                'pipeline': 'player_rankings',
                'data': {
                    'position': position,
                    'stat_type': stat_type,
                    'metric': metric_label,
                    'count': len(players),
                    'players': players
                }
            }
            
        except Exception as e:
            logger.error(f"Error fetching player rankings by stats: {e}")
            return {
                'success': False,
                'error': str(e),
                'pipeline': 'player_rankings'
            }
    
    def _add_player_names(self, players: list) -> list:
        """Add player names from database."""
        if not players:
            return players
        
        try:
            conn = self._get_db_connection()
            player_ids = [p['player_id'] for p in players]
            
            # Query player names from rosters or player_season_stats
            query = """
                SELECT DISTINCT player_id, player_name, position, team
                FROM player_season_stats
                WHERE player_id = ANY(%s) AND player_name IS NOT NULL
            """
            names_df = pd.read_sql(query, conn, params=[player_ids])
            
            # Create lookup dict
            name_lookup = {}
            for _, row in names_df.iterrows():
                name_lookup[row['player_id']] = {
                    'name': row['player_name'],
                    'position': row['position'],
                    'team': row['team']
                }
            
            # Enrich players
            for player in players:
                pid = player['player_id']
                if pid in name_lookup:
                    player['player_name'] = name_lookup[pid]['name']
                    player['team'] = name_lookup[pid].get('team')
                else:
                    player['player_name'] = pid  # Fallback to ID
                    
        except Exception as e:
            logger.warning(f"Could not fetch player names: {e}")
            # Fallback - just use IDs
            for player in players:
                player['player_name'] = player['player_id']
        
        return players
    
    def _execute_player_comparison(self, params: Dict) -> Dict:
        """Execute player comparison."""
        player1 = params.get('player1')
        player2 = params.get('player2')
        
        if not player1 or not player2:
            return {
                'success': False,
                'error': 'Two player IDs required',
                'pipeline': 'player_comparison'
            }
        
        comparison = self.player_model.compare_players(player1, player2)
        
        return {
            'success': True,
            'pipeline': 'player_comparison',
            'data': comparison
        }
    
    def _execute_drive_simulation(self, params: Dict) -> Dict:
        """Execute drive simulation."""
        yardline = params.get('yardline', 75)
        n_simulations = params.get('n_simulations', 5000)
        
        result = self.drive_simulator.simulate_scenario(
            yardline=yardline,
            n_simulations=n_simulations
        )
        
        return {
            'success': True,
            'pipeline': 'drive_simulation',
            'data': result
        }
    
    def _execute_general_query(self, params: Dict) -> Dict:
        """Handle general queries - returns available info for LLM to process."""
        teams = params.get('teams', [])
        season = params.get('season', 2025)
        
        data = {
            'teams_mentioned': teams,
            'season': season,
            'available_data': []
        }
        
        for team in teams[:2]:  # Limit to 2 teams
            profile = self.team_profiler.get_profile(team, season)
            if profile:
                data['available_data'].append({
                    'team': team,
                    'profile_summary': {
                        'epa_per_play': profile['overall']['epa_per_play'],
                        'pass_rate': profile['overall']['pass_rate'],
                        'strengths': profile.get('strengths', []),
                        'weaknesses': profile.get('weaknesses', [])
                    }
                })
        
        return {
            'success': True,
            'pipeline': 'general_query',
            'data': data,
            'needs_llm': True
        }
    
    def close(self):
        """Close database connection."""
        if self._db_conn and not self._db_conn.closed:
            self._db_conn.close()
