"""
Response Formatter

Converts pipeline outputs to natural language responses.
"""

from typing import Dict, Any, Optional, List
import json


class ResponseFormatter:
    """
    Formats pipeline outputs into natural language responses.
    """
    
    def __init__(self, include_data: bool = True, detail_level: str = 'normal'):
        """
        Initialize formatter.
        
        Args:
            include_data: Whether to include raw data in response
            detail_level: 'brief', 'normal', or 'detailed'
        """
        self.include_data = include_data
        self.detail_level = detail_level
    
    def format(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format a pipeline result into a response.
        
        Args:
            result: Pipeline execution result
            
        Returns:
            Formatted response with 'text' and optionally 'data'
        """
        if not result.get('success'):
            return self._format_error(result)
        
        pipeline = result.get('pipeline', 'unknown')
        data = result.get('data', {})
        
        formatter_map = {
            'team_profile': self._format_team_profile,
            'team_comparison': self._format_team_comparison,
            'team_tendencies': self._format_team_tendencies,
            'situation_epa': self._format_situation_epa,
            'decision_analysis': self._format_decision_analysis,
            'player_rankings': self._format_player_rankings,
            'player_comparison': self._format_player_comparison,
            'drive_simulation': self._format_drive_simulation,
            'general_query': self._format_general_query,
        }
        
        formatter = formatter_map.get(pipeline, self._format_generic)
        text = formatter(data)
        
        response = {
            'text': text,
            'pipeline': pipeline,
            'success': True
        }
        
        if self.include_data:
            response['data'] = data
        
        return response
    
    def _format_error(self, result: Dict) -> Dict:
        """Format error response."""
        error = result.get('error', 'Unknown error')
        return {
            'text': f"I couldn't complete that analysis: {error}",
            'pipeline': result.get('pipeline', 'unknown'),
            'success': False,
            'error': error
        }
    
    def _format_team_profile(self, data: Dict) -> str:
        """Format team profile response."""
        team = data.get('team', 'Unknown')
        season = data.get('season', 2025)
        profile = data.get('profile', {})
        
        overall = profile.get('overall', {})
        defense = profile.get('defense', {})
        strengths = profile.get('strengths', [])
        weaknesses = profile.get('weaknesses', [])
        
        # Build response
        lines = [f"**{team} {season} Profile**\n"]
        
        # Offense
        epa = overall.get('epa_per_play', 0)
        pass_rate = overall.get('pass_rate', 0)
        success_rate = overall.get('success_rate', 0)
        
        lines.append("**Offense:**")
        lines.append(f"• EPA/Play: {epa:+.3f} {'(above avg)' if epa > 0 else '(below avg)'}")
        lines.append(f"• Pass Rate: {pass_rate:.1%}")
        lines.append(f"• Success Rate: {success_rate:.1%}")
        
        if self.detail_level in ['normal', 'detailed']:
            pass_epa = overall.get('pass_epa', 0)
            rush_epa = overall.get('rush_epa', 0)
            lines.append(f"• Pass EPA: {pass_epa:+.3f} | Rush EPA: {rush_epa:+.3f}")
        
        # Defense
        def_epa = defense.get('epa_per_play', 0)
        lines.append("\n**Defense:**")
        lines.append(f"• EPA/Play Allowed: {def_epa:+.3f} {'(good)' if def_epa < 0 else '(poor)'}")
        
        # Strengths/Weaknesses
        if strengths:
            lines.append(f"\n**Strengths:** {', '.join(s.replace('_', ' ').title() for s in strengths)}")
        if weaknesses:
            lines.append(f"**Weaknesses:** {', '.join(w.replace('_', ' ').title() for w in weaknesses)}")
        
        return '\n'.join(lines)
    
    def _format_team_comparison(self, data: Dict) -> str:
        """Format team comparison response."""
        team1 = data.get('team1', 'Team 1')
        team2 = data.get('team2', 'Team 2')
        profile1 = data.get('profile1', {})
        profile2 = data.get('profile2', {})
        comparison = data.get('comparison', {})
        
        lines = [f"**{team1} vs {team2}**\n"]
        
        # EPA comparison
        epa1 = profile1.get('overall', {}).get('epa_per_play', 0)
        epa2 = profile2.get('overall', {}).get('epa_per_play', 0)
        
        lines.append("**Offensive Efficiency:**")
        lines.append(f"• {team1}: {epa1:+.3f} EPA/play")
        lines.append(f"• {team2}: {epa2:+.3f} EPA/play")
        
        if epa1 > epa2:
            diff = epa1 - epa2
            lines.append(f"• Edge: {team1} (+{diff:.3f})")
        elif epa2 > epa1:
            diff = epa2 - epa1
            lines.append(f"• Edge: {team2} (+{diff:.3f})")
        else:
            lines.append("• Edge: Even")
        
        # Pass rates
        pr1 = profile1.get('overall', {}).get('pass_rate', 0)
        pr2 = profile2.get('overall', {}).get('pass_rate', 0)
        
        lines.append(f"\n**Tendencies:**")
        lines.append(f"• {team1} pass rate: {pr1:.1%}")
        lines.append(f"• {team2} pass rate: {pr2:.1%}")
        
        # Matchup notes
        notes = comparison.get('matchup_notes', [])
        if notes:
            lines.append(f"\n**Matchup Notes:**")
            for note in notes:
                lines.append(f"• {note}")
        
        return '\n'.join(lines)
    
    def _format_team_tendencies(self, data: Dict) -> str:
        """Format team tendencies response."""
        team = data.get('team', 'Unknown')
        tendencies = data.get('overall_tendencies', {})
        deviations = data.get('deviations', {})
        specific = data.get('specific_situation')
        
        lines = [f"**{team} Tendencies**\n"]
        
        # Overall
        pass_rate = tendencies.get('pass_rate', 0)
        shotgun = tendencies.get('shotgun_rate', 0)
        
        lines.append(f"**Overall:**")
        lines.append(f"• Pass Rate: {pass_rate:.1%}")
        lines.append(f"• Shotgun Rate: {shotgun:.1%}")
        
        # Deviations from league average
        pass_dev = deviations.get('pass_rate', 0)
        if abs(pass_dev) > 0.02:
            direction = "more" if pass_dev > 0 else "less"
            lines.append(f"• Passes {abs(pass_dev):.1%} {direction} than league average")
        
        # Specific situation
        if specific and 'note' in specific:
            lines.append(f"\n**Situation Analysis:**")
            lines.append(f"• {specific['note']}")
        
        return '\n'.join(lines)
    
    def _format_situation_epa(self, data: Dict) -> str:
        """Format situation EPA response."""
        situation = data.get('situation', {})
        analysis = data.get('analysis', {})
        team = data.get('team')
        
        down = situation.get('down', '?')
        distance = situation.get('distance', '?')
        yardline = situation.get('yardline', 50)
        defenders_in_box = situation.get('defenders_in_box')
        
        pass_epa = analysis.get('pass_epa', 0)
        run_epa = analysis.get('run_epa', 0)
        recommendation = analysis.get('recommendation', 'neutral')
        confidence = analysis.get('confidence', 0.5)
        defensive_insight = analysis.get('defensive_insight')
        
        lines = [f"**{down}{'st' if down==1 else 'nd' if down==2 else 'rd' if down==3 else 'th'} & {distance}**"]
        
        if team:
            lines[0] += f" ({team})"
        
        lines.append(f"At the {yardline} yard line")
        
        # Add defensive context if available
        if defenders_in_box is not None:
            lines.append(f"Defense showing {defenders_in_box} in the box\n")
        else:
            lines.append("")
        
        lines.append("**Expected Points Added:**")
        lines.append(f"• Pass: {pass_epa:+.3f}")
        lines.append(f"• Run: {run_epa:+.3f}")
        
        # Recommendation
        if recommendation == 'pass':
            lines.append(f"\n**Recommendation: PASS** ({confidence:.0%} confidence)")
            lines.append(f"Passing has {abs(pass_epa - run_epa):.3f} higher expected value.")
        elif recommendation == 'run':
            lines.append(f"\n**Recommendation: RUN** ({confidence:.0%} confidence)")
            lines.append(f"Running has {abs(run_epa - pass_epa):.3f} higher expected value.")
        else:
            lines.append(f"\n**Recommendation: NEUTRAL**")
            lines.append("Both options have similar expected value.")
        
        # Add defensive insight if available
        if defensive_insight:
            lines.append(f"\n**Defensive Read:** {defensive_insight}")
        
        return '\n'.join(lines)
    
    def _format_decision_analysis(self, data: Dict) -> str:
        """Format 4th down decision response."""
        situation = data.get('situation', {})
        go_for_it = data.get('go_for_it', {})
        field_goal = data.get('field_goal', {})
        recommendation = data.get('recommendation', 'unknown')
        confidence = data.get('confidence', 0.5)
        
        down = situation.get('down', 4)
        distance = situation.get('ydstogo') or situation.get('distance') or '?'
        yardline = situation.get('yardline') or 35  # Default to 35 if missing
        fg_distance = situation.get('fg_distance') or (yardline + 17 if isinstance(yardline, int) else '?')
        
        lines = [f"**4th & {distance} at the {yardline}**"]
        lines.append(f"({fg_distance} yard field goal)\n")
        
        # Go for it analysis
        go_ep = go_for_it.get('expected_points', 0)
        go_td = go_for_it.get('td_probability', 0)
        go_to = go_for_it.get('turnover_probability', 0)
        
        lines.append("**Go For It:**")
        lines.append(f"• Expected Points: {go_ep:.2f}")
        lines.append(f"• TD Probability: {go_td:.1%}")
        lines.append(f"• Turnover Risk: {go_to:.1%}")
        
        # Field goal analysis
        fg_ep = field_goal.get('expected_points', 0)
        fg_rate = field_goal.get('success_probability', 0)
        
        lines.append(f"\n**Kick Field Goal:**")
        lines.append(f"• Expected Points: {fg_ep:.2f}")
        lines.append(f"• Success Rate: {fg_rate:.1%}")
        
        # Recommendation
        rec_text = {
            'go_for_it': 'GO FOR IT',
            'field_goal': 'KICK THE FIELD GOAL',
            'punt': 'PUNT'
        }.get(recommendation, recommendation.upper())
        
        lines.append(f"\n**Recommendation: {rec_text}** ({confidence:.0%} confidence)")
        
        ep_diff = data.get('expected_points_difference', 0)
        if ep_diff > 0.1:
            lines.append(f"This option gains {ep_diff:.2f} expected points over the alternative.")
        
        return '\n'.join(lines)
    
    def _format_player_rankings(self, data: Dict) -> str:
        """Format player rankings response."""
        position = data.get('position', 'Player')
        stat_type = data.get('stat_type', 'stats')
        metric = data.get('metric', 'epa')
        players = data.get('players', [])
        
        lines = [f"**Top {position}s by {metric.replace('_', ' ').title()}**\n"]
        
        for i, player in enumerate(players, 1):
            # Use player_name if available, otherwise fall back to player_id
            player_name = player.get('player_name') or player.get('player_id', 'Unknown')
            team = player.get('team', '')
            
            # Format name with team if available
            if team:
                lines.append(f"{i}. **{player_name}** ({team})")
            else:
                lines.append(f"{i}. **{player_name}**")
            
            # Check if this is EPA-based or stat-based
            if 'stat_value' in player:
                # Traditional stats (yards, TDs)
                stat_value = player.get('stat_value', 0)
                lines.append(f"   {metric}: {stat_value:,}")
            else:
                # EPA-based
                epa = player.get('epa_per_play') or player.get('epa_per_target', 0)
                attempts = player.get('attempts', 0)
                shrinkage = player.get('shrinkage_applied', 0)
                lines.append(f"   EPA: {epa:+.3f} ({attempts} attempts, {shrinkage:.0%} shrinkage)")
        
        if not players:
            lines.append("No players found matching criteria.")
        
        return '\n'.join(lines)
    
    def _format_player_comparison(self, data: Dict) -> str:
        """Format player comparison response."""
        p1 = data.get('player_1', {})
        p2 = data.get('player_2', {})
        verdict = data.get('verdict', 'unknown')
        
        lines = [f"**Player Comparison**\n"]
        
        lines.append(f"**{p1.get('id', 'Player 1')}:**")
        lines.append(f"• EPA: {p1.get('shrunk_epa', 0):+.3f}")
        lines.append(f"• Sample: {p1.get('sample_size', 0)} plays")
        lines.append(f"• Shrinkage: {p1.get('shrinkage_applied', 0):.0%}")
        
        lines.append(f"\n**{p2.get('id', 'Player 2')}:**")
        lines.append(f"• EPA: {p2.get('shrunk_epa', 0):+.3f}")
        lines.append(f"• Sample: {p2.get('sample_size', 0)} plays")
        lines.append(f"• Shrinkage: {p2.get('shrinkage_applied', 0):.0%}")
        
        if verdict == 'player_1_better':
            lines.append(f"\n**Verdict:** {p1.get('id')} has the edge")
        elif verdict == 'player_2_better':
            lines.append(f"\n**Verdict:** {p2.get('id')} has the edge")
        else:
            lines.append(f"\n**Verdict:** Similar performance")
        
        return '\n'.join(lines)
    
    def _format_drive_simulation(self, data: Dict) -> str:
        """Format drive simulation response."""
        yardline = data.get('starting_yardline', 75)
        ep = data.get('expected_points', 0)
        td_prob = data.get('td_probability', 0)
        fg_prob = data.get('fg_probability', 0)
        
        lines = [f"**Drive from Own {100 - yardline}**\n"]
        
        lines.append(f"Expected Points: **{ep:.2f}**")
        lines.append(f"• TD Probability: {td_prob:.1%}")
        lines.append(f"• FG Probability: {fg_prob:.1%}")
        lines.append(f"• No Score: {1 - td_prob - fg_prob:.1%}")
        
        return '\n'.join(lines)
    
    def _format_general_query(self, data: Dict) -> str:
        """Format general query response."""
        teams = data.get('teams_mentioned', [])
        available = data.get('available_data', [])
        
        if not available:
            return "I don't have specific data for that query. Could you ask about a specific team, player, or game situation?"
        
        lines = ["Here's what I found:\n"]
        
        for item in available:
            team = item.get('team', 'Unknown')
            summary = item.get('profile_summary', {})
            
            lines.append(f"**{team}:**")
            lines.append(f"• EPA/Play: {summary.get('epa_per_play', 0):+.3f}")
            lines.append(f"• Pass Rate: {summary.get('pass_rate', 0):.1%}")
            
            strengths = summary.get('strengths', [])
            if strengths:
                lines.append(f"• Strengths: {', '.join(strengths)}")
        
        return '\n'.join(lines)
    
    def _format_generic(self, data: Dict) -> str:
        """Generic formatter for unknown pipeline types."""
        return f"Analysis complete. Data: {json.dumps(data, indent=2, default=str)[:500]}..."
