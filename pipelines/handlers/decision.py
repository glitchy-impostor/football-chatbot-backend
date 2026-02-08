"""
Decision Handler

Handles play calling decision queries using the EPA model and drive simulator.
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class DecisionHandler:
    """Handler for play decision queries."""
    
    def __init__(self, db_conn, models: Dict):
        """
        Initialize handler.
        
        Args:
            db_conn: Database connection
            models: Dictionary containing epa_model and drive_simulator
        """
        self.db_conn = db_conn
        self.models = models
        self.epa_model = models.get('epa_model')
        self.simulator = models.get('drive_simulator')
        self.profiler = models.get('team_profiler')
    
    def analyze_decision(self, down: int, ydstogo: int, yardline_100: int,
                        quarter: int = 2, score_differential: int = 0,
                        team: str = None, half_seconds: int = 900,
                        **kwargs) -> Dict:
        """
        Analyze run vs pass decision.
        
        Args:
            down: Current down (1-4)
            ydstogo: Yards to first down
            yardline_100: Yards from opponent's end zone
            quarter: Quarter (1-5)
            score_differential: Offense score - defense score
            team: Offensive team (for team-specific adjustments)
            half_seconds: Seconds remaining in half
            
        Returns:
            Decision analysis
        """
        logger.info(f"Analyzing decision: {down}&{ydstogo} at {yardline_100}")
        
        result = {
            'situation': {
                'down': down,
                'ydstogo': ydstogo,
                'yardline_100': yardline_100,
                'quarter': quarter,
                'score_differential': score_differential,
            },
            'sources': []
        }
        
        # Get team adjustments if available
        team_pass_adj = 0.0
        team_run_adj = 0.0
        
        if team and self.profiler:
            key = f"{team}_2023"  # TODO: make season configurable
            profile = self.profiler.profiles.get(key)
            if profile:
                overall = profile.get('overall', {})
                avg_epa = overall.get('epa_per_play', 0)
                team_pass_adj = overall.get('pass_epa', 0) - avg_epa
                team_run_adj = overall.get('rush_epa', 0) - avg_epa
                result['team'] = team
                result['team_adjustments'] = {
                    'pass_adjustment': round(team_pass_adj, 4),
                    'run_adjustment': round(team_run_adj, 4),
                }
        
        # Use EPA model for run vs pass recommendation
        if self.epa_model:
            try:
                comparison = self.epa_model.compare_play_types(
                    down=down,
                    ydstogo=ydstogo,
                    yardline_100=yardline_100,
                    quarter=quarter,
                    score_differential=score_differential,
                    half_seconds_remaining=half_seconds,
                    is_home=1,
                    team_pass_adjustment=team_pass_adj,
                    team_run_adjustment=team_run_adj,
                )
                result['run_vs_pass'] = comparison
                result['sources'].append('epa_model')
            except Exception as e:
                logger.warning(f"EPA model failed: {e}")
                result['run_vs_pass'] = {'error': str(e)}
        else:
            # Simple fallback logic
            if down == 4:
                result['run_vs_pass'] = {
                    'note': 'Fourth down - consider go for it, kick, or punt',
                    'recommendation': 'depends on situation'
                }
            elif ydstogo <= 3:
                result['run_vs_pass'] = {
                    'recommendation': 'run',
                    'confidence': 0.6,
                    'note': 'Short yardage favors running'
                }
            elif ydstogo >= 10:
                result['run_vs_pass'] = {
                    'recommendation': 'pass',
                    'confidence': 0.6,
                    'note': 'Long distance favors passing'
                }
            else:
                result['run_vs_pass'] = {
                    'recommendation': 'neutral',
                    'confidence': 0.5,
                    'note': 'Balanced situation'
                }
        
        return result
    
    def analyze_fourth_down(self, ydstogo: int, yardline_100: int,
                           quarter: int = 4, score_differential: int = 0,
                           n_simulations: int = 2000, **kwargs) -> Dict:
        """
        Analyze fourth down decision: go for it, kick, or punt.
        
        Args:
            ydstogo: Yards to first down
            yardline_100: Yards from opponent's end zone
            quarter: Quarter
            score_differential: Offense score - defense score
            n_simulations: Number of simulations to run
            
        Returns:
            Fourth down decision analysis
        """
        logger.info(f"Analyzing 4th&{ydstogo} at {yardline_100}")
        
        result = {
            'situation': {
                'down': 4,
                'ydstogo': ydstogo,
                'yardline_100': yardline_100,
                'quarter': quarter,
                'score_differential': score_differential,
            },
            'sources': []
        }
        
        # Use drive simulator if available
        if self.simulator and self.simulator.is_loaded:
            try:
                sim_result = self.simulator.simulate_decision(
                    down=4,
                    ydstogo=ydstogo,
                    yardline=yardline_100,
                    n_simulations=n_simulations
                )
                result['simulation'] = sim_result
                result['recommendation'] = sim_result['recommendation']
                result['confidence'] = sim_result['confidence']
                result['sources'].append('drive_simulator')
            except Exception as e:
                logger.warning(f"Simulator failed: {e}")
                result['simulation'] = {'error': str(e)}
        else:
            # Load simulator on demand
            if self.simulator:
                try:
                    self.simulator.load_distributions(self.db_conn)
                    sim_result = self.simulator.simulate_decision(
                        down=4,
                        ydstogo=ydstogo,
                        yardline=yardline_100,
                        n_simulations=n_simulations
                    )
                    result['simulation'] = sim_result
                    result['recommendation'] = sim_result['recommendation']
                    result['confidence'] = sim_result['confidence']
                    result['sources'].append('drive_simulator')
                except Exception as e:
                    logger.warning(f"Simulator load failed: {e}")
        
        # Add heuristic recommendations as fallback
        if 'recommendation' not in result:
            fg_distance = yardline_100 + 17
            
            if yardline_100 <= 2:
                result['recommendation'] = 'go_for_it'
                result['confidence'] = 0.8
                result['reason'] = 'Goal line situation - high TD probability'
            elif fg_distance <= 35 and ydstogo > 3:
                result['recommendation'] = 'field_goal'
                result['confidence'] = 0.7
                result['reason'] = 'Makeable field goal range'
            elif ydstogo <= 2:
                result['recommendation'] = 'go_for_it'
                result['confidence'] = 0.65
                result['reason'] = 'Short yardage - good conversion odds'
            elif yardline_100 >= 60:
                result['recommendation'] = 'punt'
                result['confidence'] = 0.7
                result['reason'] = 'Deep in own territory'
            else:
                # Neutral zone - depends on game situation
                if score_differential < -10 and quarter >= 4:
                    result['recommendation'] = 'go_for_it'
                    result['confidence'] = 0.6
                    result['reason'] = 'Behind late - need to be aggressive'
                elif score_differential > 14:
                    result['recommendation'] = 'punt' if yardline_100 > 40 else 'field_goal'
                    result['confidence'] = 0.6
                    result['reason'] = 'Comfortable lead - play it safe'
                else:
                    result['recommendation'] = 'go_for_it' if ydstogo <= 4 else 'punt'
                    result['confidence'] = 0.5
                    result['reason'] = 'Close call - depends on risk tolerance'
        
        return result
    
    def get_situation_context(self, down: int, ydstogo: int, 
                             yardline_100: int, season: int = 2023) -> Dict:
        """
        Get league context for a situation.
        
        Args:
            down: Current down
            ydstogo: Yards to first down
            yardline_100: Yards from opponent's end zone
            season: Season year
            
        Returns:
            Situation context with league averages
        """
        cursor = self.db_conn.cursor()
        
        # Determine distance bucket
        if ydstogo <= 3:
            distance_bucket = 'short'
        elif ydstogo <= 7:
            distance_bucket = 'medium'
        else:
            distance_bucket = 'long'
        
        # Get league average for this situation
        cursor.execute("""
            SELECT pass_rate, epa_avg, success_rate, sample_size
            FROM situational_tendencies
            WHERE season = %s 
              AND team IS NULL 
              AND down = %s 
              AND distance_bucket = %s
            LIMIT 1
        """, (season, down, distance_bucket))
        
        row = cursor.fetchone()
        
        context = {
            'situation': {
                'down': down,
                'ydstogo': ydstogo,
                'yardline_100': yardline_100,
                'distance_bucket': distance_bucket,
            },
            'season': season,
            'sources': ['situational_tendencies']
        }
        
        if row:
            context['league_average'] = {
                'pass_rate': float(row[0]) if row[0] else 0,
                'epa_avg': float(row[1]) if row[1] else 0,
                'success_rate': float(row[2]) if row[2] else 0,
                'sample_size': int(row[3]) if row[3] else 0,
            }
            
            # Add interpretation
            pass_rate = context['league_average']['pass_rate']
            if pass_rate > 0.7:
                context['tendency'] = 'pass_heavy'
                context['note'] = f'Teams pass {pass_rate:.0%} of the time in this situation'
            elif pass_rate < 0.4:
                context['tendency'] = 'run_heavy'
                context['note'] = f'Teams run {1-pass_rate:.0%} of the time in this situation'
            else:
                context['tendency'] = 'balanced'
                context['note'] = 'Balanced situation with mix of run and pass'
        
        return context
