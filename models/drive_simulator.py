"""
Drive Simulator

Monte Carlo simulation of drive outcomes for decision analysis.
Useful for "go for it" vs "kick" decisions and expected points calculations.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class DriveOutcome(Enum):
    """Possible drive outcomes."""
    TOUCHDOWN = 'touchdown'
    FIELD_GOAL = 'field_goal'
    TURNOVER = 'turnover'
    PUNT = 'punt'
    TURNOVER_ON_DOWNS = 'turnover_on_downs'
    END_OF_HALF = 'end_of_half'
    SAFETY = 'safety'


@dataclass
class PlayResult:
    """Result of a single play."""
    yards_gained: int
    first_down: bool
    touchdown: bool
    turnover: bool
    success: bool


class DriveSimulator:
    """
    Simulates drive outcomes using historical play distributions.
    """
    
    def __init__(self):
        self.play_distributions: Dict = {}
        self.fg_success_rates: Dict[int, float] = {}
        self.is_loaded = False
        
    def load_distributions(self, conn, seasons: List[int] = None):
        """
        Load play outcome distributions from database.
        
        Args:
            conn: Database connection
            seasons: List of seasons to use (default: 2020-2024)
        """
        if seasons is None:
            seasons = [2020, 2021, 2022, 2023, 2024]
        
        logger.info(f"Loading play distributions from seasons {seasons}...")
        
        season_str = ','.join(map(str, seasons))
        
        # Load play outcomes by situation
        query = f"""
            SELECT 
                down,
                CASE 
                    WHEN ydstogo <= 3 THEN 'short'
                    WHEN ydstogo <= 7 THEN 'medium'
                    ELSE 'long'
                END as distance,
                CASE 
                    WHEN yardline_100 <= 10 THEN 'goal_line'
                    WHEN yardline_100 <= 20 THEN 'red_zone'
                    WHEN yardline_100 <= 40 THEN 'opp_territory'
                    WHEN yardline_100 <= 60 THEN 'midfield'
                    ELSE 'own_territory'
                END as field_zone,
                play_type,
                yards_gained,
                COALESCE(first_down, 0) as first_down,
                COALESCE(touchdown, 0) as touchdown,
                COALESCE(interception, 0) + COALESCE(fumble, 0) as turnover
            FROM plays
            WHERE season IN ({season_str})
              AND play_type IN ('pass', 'run')
              AND down IS NOT NULL
              AND yards_gained IS NOT NULL
        """
        
        plays = pd.read_sql(query, conn)
        
        # Build distributions for each situation
        for (down, distance, field_zone), group in plays.groupby(['down', 'distance', 'field_zone']):
            key = f"{down}_{distance}_{field_zone}"
            
            self.play_distributions[key] = {
                'yards': group['yards_gained'].tolist(),
                'first_down_rate': group['first_down'].mean(),
                'td_rate': group['touchdown'].mean(),
                'turnover_rate': group['turnover'].mean(),
                'sample_size': len(group),
            }
        
        # Field goal success rates by distance
        fg_query = f"""
            SELECT 
                yardline_100 + 17 as fg_distance,  -- Add 17 for snap + endzone
                AVG(CASE WHEN play_type = 'field_goal' AND touchdown = 0 
                    AND (yards_gained > 0 OR success = 1) THEN 1.0 ELSE 0.0 END) as success_rate,
                COUNT(*) as attempts
            FROM plays
            WHERE season IN ({season_str})
              AND play_type = 'field_goal'
            GROUP BY yardline_100
            HAVING COUNT(*) >= 5
        """
        
        fg_data = pd.read_sql(fg_query, conn)
        
        for _, row in fg_data.iterrows():
            dist = int(row['fg_distance'])
            self.fg_success_rates[dist] = float(row['success_rate'])
        
        # Fill in missing FG distances with interpolation
        for dist in range(18, 65):
            if dist not in self.fg_success_rates:
                # Simple interpolation
                lower = max([d for d in self.fg_success_rates.keys() if d < dist], default=18)
                upper = min([d for d in self.fg_success_rates.keys() if d > dist], default=64)
                
                if lower in self.fg_success_rates and upper in self.fg_success_rates:
                    ratio = (dist - lower) / (upper - lower) if upper != lower else 0.5
                    self.fg_success_rates[dist] = (
                        self.fg_success_rates[lower] * (1 - ratio) + 
                        self.fg_success_rates[upper] * ratio
                    )
                else:
                    # Default estimate
                    self.fg_success_rates[dist] = max(0.3, 1.0 - (dist - 20) * 0.015)
        
        self.is_loaded = True
        logger.info(f"Loaded {len(self.play_distributions)} situation distributions")
    
    def _get_distance_bucket(self, ydstogo: int) -> str:
        if ydstogo <= 3:
            return 'short'
        elif ydstogo <= 7:
            return 'medium'
        return 'long'
    
    def _get_field_zone(self, yardline_100: int) -> str:
        if yardline_100 <= 10:
            return 'goal_line'
        elif yardline_100 <= 20:
            return 'red_zone'
        elif yardline_100 <= 40:
            return 'opp_territory'
        elif yardline_100 <= 60:
            return 'midfield'
        return 'own_territory'
    
    def _sample_play(self, down: int, ydstogo: int, yardline_100: int) -> PlayResult:
        """
        Sample a single play outcome from historical distribution.
        
        Args:
            down: Current down
            ydstogo: Yards to first down
            yardline_100: Yards from opponent's end zone
            
        Returns:
            PlayResult with outcome
        """
        distance = self._get_distance_bucket(ydstogo)
        field_zone = self._get_field_zone(yardline_100)
        key = f"{down}_{distance}_{field_zone}"
        
        # Get distribution for this situation
        dist = self.play_distributions.get(key)
        
        if not dist or dist['sample_size'] < 20:
            # Fallback to generic distribution
            generic_key = f"{down}_{distance}_midfield"
            dist = self.play_distributions.get(generic_key, {
                'yards': [0, 1, 2, 3, 4, 5, -2, 8, 10],
                'turnover_rate': 0.03,
                'td_rate': 0.03,
            })
        
        # Check for turnover first
        if np.random.random() < dist.get('turnover_rate', 0.03):
            return PlayResult(
                yards_gained=0,
                first_down=False,
                touchdown=False,
                turnover=True,
                success=False
            )
        
        # Sample yards gained
        yards = int(np.random.choice(dist['yards']))
        
        # Cap yards at yardline
        yards = min(yards, yardline_100)
        
        # Check for touchdown
        touchdown = yards >= yardline_100
        
        # Check for first down
        first_down = yards >= ydstogo or touchdown
        
        # Success (positive EPA play approximation)
        success = yards >= ydstogo * 0.4 or first_down
        
        return PlayResult(
            yards_gained=yards,
            first_down=first_down,
            touchdown=touchdown,
            turnover=False,
            success=success
        )
    
    def _get_fg_success_rate(self, yardline_100: int) -> float:
        """Get field goal success rate for a given field position."""
        fg_distance = yardline_100 + 17  # Snap + end zone
        return self.fg_success_rates.get(fg_distance, max(0.2, 1.0 - (fg_distance - 20) * 0.015))
    
    def simulate_drive(self, 
                      start_down: int,
                      start_ydstogo: int,
                      start_yardline: int,
                      max_plays: int = 20) -> Tuple[DriveOutcome, float]:
        """
        Simulate a single drive from a starting position.
        
        Args:
            start_down: Starting down
            start_ydstogo: Starting yards to go
            start_yardline: Starting yardline_100
            max_plays: Maximum plays before stopping
            
        Returns:
            Tuple of (outcome, points_scored)
        """
        down = start_down
        ydstogo = start_ydstogo
        yardline = start_yardline
        
        for _ in range(max_plays):
            # 4th down decision (simple heuristic)
            if down == 4:
                fg_distance = yardline + 17
                fg_rate = self._get_fg_success_rate(yardline)
                
                # Decide: go for it, kick FG, or punt
                if yardline <= 2:
                    # Goal line, go for it
                    pass
                elif yardline <= 35 and fg_rate > 0.5:
                    # Kick FG
                    if np.random.random() < fg_rate:
                        return DriveOutcome.FIELD_GOAL, 3.0
                    else:
                        return DriveOutcome.TURNOVER_ON_DOWNS, 0.0
                elif ydstogo <= 3 and yardline <= 50:
                    # Short yardage, go for it
                    pass
                else:
                    # Punt
                    return DriveOutcome.PUNT, 0.0
            
            # Run a play
            result = self._sample_play(down, ydstogo, yardline)
            
            # Update state
            if result.turnover:
                return DriveOutcome.TURNOVER, 0.0
            
            if result.touchdown:
                return DriveOutcome.TOUCHDOWN, 7.0  # Assume XP
            
            yardline = max(1, yardline - result.yards_gained)
            
            if result.first_down:
                down = 1
                ydstogo = min(10, yardline)  # Goal to go
            else:
                down += 1
                ydstogo = max(1, ydstogo - result.yards_gained)
            
            # Failed 4th down
            if down > 4:
                return DriveOutcome.TURNOVER_ON_DOWNS, 0.0
        
        # Max plays reached
        return DriveOutcome.END_OF_HALF, 0.0
    
    def simulate_decision(self,
                         down: int,
                         ydstogo: int,
                         yardline: int,
                         n_simulations: int = 5000) -> Dict:
        """
        Simulate "go for it" vs "kick" decision.
        
        Args:
            down: Current down (typically 4)
            ydstogo: Yards to first down
            yardline: Yards from opponent's end zone (yardline_100)
            n_simulations: Number of simulations to run
            
        Returns:
            Decision analysis dictionary
        """
        if not self.is_loaded:
            raise ValueError("Must call load_distributions() first")
        
        fg_rate = self._get_fg_success_rate(yardline)
        fg_distance = yardline + 17
        
        # Simulate "go for it"
        go_outcomes = {'touchdown': 0, 'field_goal': 0, 'turnover': 0, 'points': []}
        
        for _ in range(n_simulations):
            outcome, points = self.simulate_drive(down, ydstogo, yardline)
            
            if outcome == DriveOutcome.TOUCHDOWN:
                go_outcomes['touchdown'] += 1
            elif outcome == DriveOutcome.FIELD_GOAL:
                go_outcomes['field_goal'] += 1
            else:
                go_outcomes['turnover'] += 1
            
            go_outcomes['points'].append(points)
        
        go_expected_points = np.mean(go_outcomes['points'])
        go_td_rate = go_outcomes['touchdown'] / n_simulations
        go_fg_rate = go_outcomes['field_goal'] / n_simulations
        go_turnover_rate = go_outcomes['turnover'] / n_simulations
        
        # Calculate "kick field goal" expected points
        fg_expected_points = fg_rate * 3.0
        
        # Calculate "punt" expected value (negative because gives opponent ball)
        # Simple model: punt gives opponent ball ~40 yards back
        punt_expected_points = 0  # Neutral for now (could model opponent EP)
        
        # Determine recommendation
        options = {
            'go_for_it': go_expected_points,
            'field_goal': fg_expected_points if yardline <= 45 else -999,
            'punt': punt_expected_points if down == 4 else -999,
        }
        
        recommendation = max(options, key=options.get)
        confidence = abs(options[recommendation] - sorted(options.values())[-2]) / 3.0
        confidence = min(0.95, max(0.5, 0.5 + confidence))
        
        return {
            'situation': {
                'down': down,
                'ydstogo': ydstogo,
                'yardline': yardline,
                'fg_distance': fg_distance,
            },
            'simulations': n_simulations,
            'go_for_it': {
                'expected_points': round(go_expected_points, 3),
                'td_probability': round(go_td_rate, 3),
                'fg_probability': round(go_fg_rate, 3),
                'turnover_probability': round(go_turnover_rate, 3),
            },
            'field_goal': {
                'expected_points': round(fg_expected_points, 3),
                'success_probability': round(fg_rate, 3),
            },
            'punt': {
                'expected_points': 0,
            },
            'recommendation': recommendation,
            'confidence': round(confidence, 3),
            'expected_points_difference': round(
                options[recommendation] - sorted(options.values())[-2], 3
            ),
        }
    
    def simulate_scenario(self,
                         yardline: int,
                         n_simulations: int = 5000) -> Dict:
        """
        Simulate starting a drive from a given field position.
        Useful for expected points calculations.
        
        Args:
            yardline: Starting yardline_100
            n_simulations: Number of simulations
            
        Returns:
            Expected points and outcome probabilities
        """
        outcomes = {'touchdown': 0, 'field_goal': 0, 'other': 0, 'points': []}
        
        for _ in range(n_simulations):
            # Start with 1st and 10
            ydstogo = min(10, yardline)
            outcome, points = self.simulate_drive(1, ydstogo, yardline)
            
            if outcome == DriveOutcome.TOUCHDOWN:
                outcomes['touchdown'] += 1
            elif outcome == DriveOutcome.FIELD_GOAL:
                outcomes['field_goal'] += 1
            else:
                outcomes['other'] += 1
            
            outcomes['points'].append(points)
        
        return {
            'starting_yardline': yardline,
            'simulations': n_simulations,
            'expected_points': round(np.mean(outcomes['points']), 3),
            'td_probability': round(outcomes['touchdown'] / n_simulations, 3),
            'fg_probability': round(outcomes['field_goal'] / n_simulations, 3),
            'no_score_probability': round(outcomes['other'] / n_simulations, 3),
        }
    
    def build_ep_table(self, n_simulations: int = 2000) -> pd.DataFrame:
        """
        Build expected points table by field position.
        
        Args:
            n_simulations: Simulations per field position
            
        Returns:
            DataFrame with expected points by yardline
        """
        results = []
        
        for yardline in range(1, 100):
            result = self.simulate_scenario(yardline, n_simulations)
            results.append({
                'yardline_100': yardline,
                'expected_points': result['expected_points'],
                'td_prob': result['td_probability'],
                'fg_prob': result['fg_probability'],
            })
        
        return pd.DataFrame(results)
