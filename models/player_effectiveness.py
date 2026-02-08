"""
Player Effectiveness Model with Bayesian Shrinkage

Addresses the small sample size problem in player statistics by shrinking
individual estimates toward archetype/position averages.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
import json
import logging

logger = logging.getLogger(__name__)


# Player archetypes by position
ARCHETYPES = {
    'QB': ['pocket_passer', 'dual_threat', 'game_manager'],
    'RB': ['power_back', 'speed_back', 'receiving_back', 'committee'],
    'WR': ['outside_x', 'slot', 'deep_threat', 'possession'],
    'TE': ['blocking', 'receiving', 'hybrid'],
}

# Minimum samples for reliable estimates
MIN_SAMPLES_INDIVIDUAL = 20
MIN_SAMPLES_ARCHETYPE = 100

# Default shrinkage strength (higher = more shrinkage toward prior)
DEFAULT_SHRINKAGE_K = 30


class PlayerEffectivenessModel:
    """
    Estimates player effectiveness with Bayesian shrinkage.
    
    The core idea: For players with small sample sizes, we "shrink" their
    estimates toward the average for similar players. This prevents
    extreme estimates from small samples while still capturing signal
    from players with lots of data.
    """
    
    def __init__(self, shrinkage_k: float = DEFAULT_SHRINKAGE_K):
        """
        Initialize the model.
        
        Args:
            shrinkage_k: Shrinkage strength. Higher = more shrinkage.
                        With n samples, weight on player = n/(n+k)
        """
        self.shrinkage_k = shrinkage_k
        self.position_priors: Dict[str, Dict] = {}  # Position-level priors
        self.archetype_priors: Dict[str, Dict] = {}  # Archetype-level priors
        self.player_estimates: Dict[str, Dict] = {}  # Player estimates
        
    def _calculate_shrunk_estimate(self, 
                                   player_mean: float,
                                   player_n: int,
                                   prior_mean: float,
                                   prior_var: float = 0.1) -> Tuple[float, float, float]:
        """
        Calculate shrinkage estimate using empirical Bayes.
        
        Args:
            player_mean: Player's raw mean
            player_n: Player's sample size
            prior_mean: Prior mean (from archetype/position)
            prior_var: Prior variance
            
        Returns:
            Tuple of (shrunk_estimate, confidence_lower, confidence_upper)
        """
        # Weight on player's data vs prior
        weight = player_n / (player_n + self.shrinkage_k)
        
        # Shrunk estimate
        shrunk = weight * player_mean + (1 - weight) * prior_mean
        
        # Approximate confidence interval
        # Wider when sample is small (more shrinkage applied)
        se = np.sqrt(prior_var / player_n) if player_n > 0 else np.sqrt(prior_var)
        confidence_width = 1.96 * se * (1 + (1 - weight))  # Wider with more shrinkage
        
        lower = shrunk - confidence_width
        upper = shrunk + confidence_width
        
        return shrunk, lower, upper
    
    def build_position_priors(self, conn, season: int) -> Dict[str, Dict]:
        """
        Build position-level priors from data.
        
        Args:
            conn: Database connection
            season: Season year
            
        Returns:
            Dictionary of position priors
        """
        logger.info(f"Building position priors for {season}...")
        
        # Rushing priors (RBs primarily)
        rush_query = """
            SELECT 
                AVG(epa) as mean_epa,
                STDDEV(epa) as std_epa,
                AVG(yards_gained) as mean_yards,
                AVG(CASE WHEN success = 1 THEN 1.0 ELSE 0.0 END) as success_rate,
                COUNT(*) as total_plays
            FROM plays
            WHERE season = %s 
              AND play_type = 'run'
              AND rusher_player_id IS NOT NULL
        """
        rush_stats = pd.read_sql(rush_query, conn, params=[season]).iloc[0]
        
        # Passing priors (QBs)
        pass_query = """
            SELECT 
                AVG(epa) as mean_epa,
                STDDEV(epa) as std_epa,
                AVG(yards_gained) as mean_yards,
                AVG(CASE WHEN success = 1 THEN 1.0 ELSE 0.0 END) as success_rate,
                COUNT(*) as total_plays
            FROM plays
            WHERE season = %s 
              AND play_type = 'pass'
              AND passer_player_id IS NOT NULL
        """
        pass_stats = pd.read_sql(pass_query, conn, params=[season]).iloc[0]
        
        # Receiving priors (WR/TE/RB)
        rec_query = """
            SELECT 
                AVG(epa) as mean_epa,
                STDDEV(epa) as std_epa,
                AVG(yards_gained) as mean_yards,
                AVG(CASE WHEN success = 1 THEN 1.0 ELSE 0.0 END) as success_rate,
                COUNT(*) as total_plays
            FROM plays
            WHERE season = %s 
              AND play_type = 'pass'
              AND receiver_player_id IS NOT NULL
        """
        rec_stats = pd.read_sql(rec_query, conn, params=[season]).iloc[0]
        
        self.position_priors = {
            'season': season,
            'rushing': {
                'mean_epa': float(rush_stats['mean_epa'] or 0),
                'std_epa': float(rush_stats['std_epa'] or 0.5),
                'mean_yards': float(rush_stats['mean_yards'] or 4),
                'success_rate': float(rush_stats['success_rate'] or 0.4),
                'total_plays': int(rush_stats['total_plays']),
            },
            'passing': {
                'mean_epa': float(pass_stats['mean_epa'] or 0),
                'std_epa': float(pass_stats['std_epa'] or 0.8),
                'mean_yards': float(pass_stats['mean_yards'] or 6),
                'success_rate': float(pass_stats['success_rate'] or 0.45),
                'total_plays': int(pass_stats['total_plays']),
            },
            'receiving': {
                'mean_epa': float(rec_stats['mean_epa'] or 0),
                'std_epa': float(rec_stats['std_epa'] or 0.8),
                'mean_yards': float(rec_stats['mean_yards'] or 7),
                'success_rate': float(rec_stats['success_rate'] or 0.5),
                'total_plays': int(rec_stats['total_plays']),
            },
        }
        
        return self.position_priors
    
    def build_player_estimates(self, conn, season: int) -> Dict[str, Dict]:
        """
        Build shrunk estimates for all players.
        
        Args:
            conn: Database connection
            season: Season year
            
        Returns:
            Dictionary of player estimates
        """
        if not self.position_priors or self.position_priors.get('season') != season:
            self.build_position_priors(conn, season)
        
        logger.info(f"Building player estimates for {season}...")
        
        # Rushing estimates
        rush_query = """
            SELECT 
                rusher_player_id as player_id,
                AVG(epa) as raw_epa,
                AVG(yards_gained) as raw_yards,
                AVG(CASE WHEN success = 1 THEN 1.0 ELSE 0.0 END) as raw_success,
                COUNT(*) as attempts
            FROM plays
            WHERE season = %s 
              AND play_type = 'run'
              AND rusher_player_id IS NOT NULL
            GROUP BY rusher_player_id
            HAVING COUNT(*) >= 5
        """
        rushers = pd.read_sql(rush_query, conn, params=[season])
        
        rush_prior = self.position_priors['rushing']
        
        for _, row in rushers.iterrows():
            player_id = row['player_id']
            
            # Shrink EPA estimate
            epa_shrunk, epa_low, epa_high = self._calculate_shrunk_estimate(
                player_mean=float(row['raw_epa']),
                player_n=int(row['attempts']),
                prior_mean=rush_prior['mean_epa'],
                prior_var=rush_prior['std_epa'] ** 2
            )
            
            # Shrink success rate
            success_shrunk, _, _ = self._calculate_shrunk_estimate(
                player_mean=float(row['raw_success']),
                player_n=int(row['attempts']),
                prior_mean=rush_prior['success_rate'],
                prior_var=0.1
            )
            
            shrinkage_weight = int(row['attempts']) / (int(row['attempts']) + self.shrinkage_k)
            
            self.player_estimates[player_id] = {
                'player_id': player_id,
                'stat_type': 'rushing',
                'season': season,
                'raw': {
                    'epa_per_play': float(row['raw_epa']),
                    'yards_per_carry': float(row['raw_yards']),
                    'success_rate': float(row['raw_success']),
                    'attempts': int(row['attempts']),
                },
                'shrunk': {
                    'epa_per_play': round(epa_shrunk, 4),
                    'epa_ci_lower': round(epa_low, 4),
                    'epa_ci_upper': round(epa_high, 4),
                    'success_rate': round(success_shrunk, 4),
                },
                'shrinkage_applied': round(1 - shrinkage_weight, 3),
            }
        
        # Passing estimates (QBs)
        pass_query = """
            SELECT 
                passer_player_id as player_id,
                AVG(epa) as raw_epa,
                AVG(yards_gained) as raw_yards,
                AVG(CASE WHEN success = 1 THEN 1.0 ELSE 0.0 END) as raw_success,
                COUNT(*) as attempts
            FROM plays
            WHERE season = %s 
              AND play_type = 'pass'
              AND passer_player_id IS NOT NULL
            GROUP BY passer_player_id
            HAVING COUNT(*) >= 10
        """
        passers = pd.read_sql(pass_query, conn, params=[season])
        
        pass_prior = self.position_priors['passing']
        
        for _, row in passers.iterrows():
            player_id = row['player_id']
            
            epa_shrunk, epa_low, epa_high = self._calculate_shrunk_estimate(
                player_mean=float(row['raw_epa']),
                player_n=int(row['attempts']),
                prior_mean=pass_prior['mean_epa'],
                prior_var=pass_prior['std_epa'] ** 2
            )
            
            success_shrunk, _, _ = self._calculate_shrunk_estimate(
                player_mean=float(row['raw_success']),
                player_n=int(row['attempts']),
                prior_mean=pass_prior['success_rate'],
                prior_var=0.1
            )
            
            shrinkage_weight = int(row['attempts']) / (int(row['attempts']) + self.shrinkage_k)
            
            # If already has rushing stats, merge
            if player_id in self.player_estimates:
                self.player_estimates[player_id]['passing'] = {
                    'raw_epa': float(row['raw_epa']),
                    'shrunk_epa': round(epa_shrunk, 4),
                    'attempts': int(row['attempts']),
                }
            else:
                self.player_estimates[player_id] = {
                    'player_id': player_id,
                    'stat_type': 'passing',
                    'season': season,
                    'raw': {
                        'epa_per_play': float(row['raw_epa']),
                        'yards_per_attempt': float(row['raw_yards']),
                        'success_rate': float(row['raw_success']),
                        'attempts': int(row['attempts']),
                    },
                    'shrunk': {
                        'epa_per_play': round(epa_shrunk, 4),
                        'epa_ci_lower': round(epa_low, 4),
                        'epa_ci_upper': round(epa_high, 4),
                        'success_rate': round(success_shrunk, 4),
                    },
                    'shrinkage_applied': round(1 - shrinkage_weight, 3),
                }
        
        # Receiving estimates
        rec_query = """
            SELECT 
                receiver_player_id as player_id,
                AVG(epa) as raw_epa,
                AVG(yards_gained) as raw_yards,
                AVG(CASE WHEN success = 1 THEN 1.0 ELSE 0.0 END) as raw_success,
                COUNT(*) as targets
            FROM plays
            WHERE season = %s 
              AND play_type = 'pass'
              AND receiver_player_id IS NOT NULL
            GROUP BY receiver_player_id
            HAVING COUNT(*) >= 10
        """
        receivers = pd.read_sql(rec_query, conn, params=[season])
        
        rec_prior = self.position_priors['receiving']
        
        for _, row in receivers.iterrows():
            player_id = row['player_id']
            
            epa_shrunk, epa_low, epa_high = self._calculate_shrunk_estimate(
                player_mean=float(row['raw_epa']),
                player_n=int(row['targets']),
                prior_mean=rec_prior['mean_epa'],
                prior_var=rec_prior['std_epa'] ** 2
            )
            
            shrinkage_weight = int(row['targets']) / (int(row['targets']) + self.shrinkage_k)
            
            # Add receiving stats
            if player_id in self.player_estimates:
                self.player_estimates[player_id]['receiving'] = {
                    'raw_epa': float(row['raw_epa']),
                    'shrunk_epa': round(epa_shrunk, 4),
                    'targets': int(row['targets']),
                }
            else:
                self.player_estimates[player_id] = {
                    'player_id': player_id,
                    'stat_type': 'receiving',
                    'season': season,
                    'raw': {
                        'epa_per_target': float(row['raw_epa']),
                        'yards_per_target': float(row['raw_yards']),
                        'success_rate': float(row['raw_success']),
                        'targets': int(row['targets']),
                    },
                    'shrunk': {
                        'epa_per_target': round(epa_shrunk, 4),
                        'epa_ci_lower': round(epa_low, 4),
                        'epa_ci_upper': round(epa_high, 4),
                    },
                    'shrinkage_applied': round(1 - shrinkage_weight, 3),
                }
        
        logger.info(f"Built estimates for {len(self.player_estimates)} players")
        return self.player_estimates
    
    def get_player_estimate(self, player_id: str) -> Optional[Dict]:
        """Get estimate for a specific player."""
        return self.player_estimates.get(player_id)
    
    def get_top_players(self, stat_type: str = 'rushing', 
                        metric: str = 'epa_per_play',
                        min_attempts: int = 50,
                        n: int = 10) -> List[Dict]:
        """
        Get top players by shrunk estimate.
        
        Args:
            stat_type: 'rushing', 'passing', or 'receiving'
            metric: Metric to rank by
            min_attempts: Minimum attempts/targets
            n: Number of players to return
            
        Returns:
            List of player estimates
        """
        eligible = []
        
        for player_id, estimate in self.player_estimates.items():
            if estimate.get('stat_type') != stat_type:
                continue
            
            attempts = estimate['raw'].get('attempts', 0) or estimate['raw'].get('targets', 0)
            if attempts < min_attempts:
                continue
            
            shrunk_value = estimate['shrunk'].get(metric)
            if shrunk_value is not None:
                eligible.append({
                    'player_id': player_id,
                    'shrunk_value': shrunk_value,
                    'raw_value': estimate['raw'].get(metric.replace('_per_play', '_per_play').replace('_per_target', '_per_target')),
                    'attempts': attempts,
                    'shrinkage_applied': estimate['shrinkage_applied'],
                    **estimate['shrunk'],
                })
        
        # Sort by shrunk value
        eligible.sort(key=lambda x: x['shrunk_value'], reverse=True)
        
        return eligible[:n]
    
    def compare_players(self, player_id_1: str, player_id_2: str) -> Dict:
        """
        Compare two players' estimates.
        
        Args:
            player_id_1: First player ID
            player_id_2: Second player ID
            
        Returns:
            Comparison dictionary
        """
        p1 = self.get_player_estimate(player_id_1)
        p2 = self.get_player_estimate(player_id_2)
        
        if not p1 or not p2:
            return {'error': 'One or both players not found'}
        
        comparison = {
            'player_1': {
                'id': player_id_1,
                'stat_type': p1['stat_type'],
                'shrunk_epa': p1['shrunk'].get('epa_per_play') or p1['shrunk'].get('epa_per_target'),
                'raw_epa': p1['raw'].get('epa_per_play') or p1['raw'].get('epa_per_target'),
                'sample_size': p1['raw'].get('attempts') or p1['raw'].get('targets'),
                'shrinkage_applied': p1['shrinkage_applied'],
            },
            'player_2': {
                'id': player_id_2,
                'stat_type': p2['stat_type'],
                'shrunk_epa': p2['shrunk'].get('epa_per_play') or p2['shrunk'].get('epa_per_target'),
                'raw_epa': p2['raw'].get('epa_per_play') or p2['raw'].get('epa_per_target'),
                'sample_size': p2['raw'].get('attempts') or p2['raw'].get('targets'),
                'shrinkage_applied': p2['shrinkage_applied'],
            },
        }
        
        # Who is better?
        epa1 = comparison['player_1']['shrunk_epa']
        epa2 = comparison['player_2']['shrunk_epa']
        
        if epa1 is not None and epa2 is not None:
            diff = epa1 - epa2
            if abs(diff) < 0.02:
                comparison['verdict'] = 'similar'
            elif diff > 0:
                comparison['verdict'] = 'player_1_better'
                comparison['epa_difference'] = round(diff, 4)
            else:
                comparison['verdict'] = 'player_2_better'
                comparison['epa_difference'] = round(diff, 4)
        
        return comparison
    
    def save(self, filepath: str):
        """Save model to JSON file."""
        data = {
            'shrinkage_k': self.shrinkage_k,
            'position_priors': self.position_priors,
            'player_estimates': self.player_estimates,
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Player model saved to {filepath}")
    
    @classmethod
    def load(cls, filepath: str) -> 'PlayerEffectivenessModel':
        """Load model from JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        model = cls(shrinkage_k=data['shrinkage_k'])
        model.position_priors = data['position_priors']
        model.player_estimates = data['player_estimates']
        
        logger.info(f"Loaded estimates for {len(model.player_estimates)} players")
        return model
