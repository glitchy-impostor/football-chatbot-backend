"""
Response Formatter

Converts structured data from handlers into natural language responses.
"""

from typing import Dict, Optional


class ResponseFormatter:
    """Formats handler output into natural language."""
    
    # Team name mappings for display
    TEAM_NAMES = {
        'KC': 'Kansas City Chiefs', 'SF': 'San Francisco 49ers',
        'BAL': 'Baltimore Ravens', 'BUF': 'Buffalo Bills',
        'DAL': 'Dallas Cowboys', 'PHI': 'Philadelphia Eagles',
        'DET': 'Detroit Lions', 'MIA': 'Miami Dolphins',
        'GB': 'Green Bay Packers', 'CIN': 'Cincinnati Bengals',
        'CLE': 'Cleveland Browns', 'PIT': 'Pittsburgh Steelers',
        'HOU': 'Houston Texans', 'IND': 'Indianapolis Colts',
        'JAX': 'Jacksonville Jaguars', 'TEN': 'Tennessee Titans',
        'DEN': 'Denver Broncos', 'LV': 'Las Vegas Raiders',
        'LAC': 'Los Angeles Chargers', 'LA': 'Los Angeles Rams',
        'SEA': 'Seattle Seahawks', 'ARI': 'Arizona Cardinals',
        'NO': 'New Orleans Saints', 'ATL': 'Atlanta Falcons',
        'CAR': 'Carolina Panthers', 'TB': 'Tampa Bay Buccaneers',
        'CHI': 'Chicago Bears', 'MIN': 'Minnesota Vikings',
        'NYG': 'New York Giants', 'NYJ': 'New York Jets',
        'WAS': 'Washington Commanders', 'NE': 'New England Patriots',
    }
    
    def _team_name(self, abbr: str) -> str:
        """Get full team name from abbreviation."""
        return self.TEAM_NAMES.get(abbr, abbr)
    
    def _ordinal(self, n: int) -> str:
        """Convert number to ordinal (1st, 2nd, etc.)."""
        if 10 <= n % 100 <= 20:
            suffix = 'th'
        else:
            suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
        return f"{n}{suffix}"
    
    def format(self, intent: str, data: Dict, query: str = "") -> str:
        """
        Format data into a natural language response.
        
        Args:
            intent: The intent type that produced this data
            data: Structured data from handler
            query: Original query (for context)
            
        Returns:
            Natural language response string
        """
        if data.get('error'):
            return f"Sorry, I couldn't complete that request: {data['error']}"
        
        formatter_map = {
            'team_stats': self._format_team_stats,
            'team_profile': self._format_team_stats,
            'team_ranking': self._format_team_ranking,
            'top_players': self._format_top_players,
            'player_stats': self._format_player_stats,
            'situational': self._format_situational,
            'situational_league': self._format_situational,
            'situational_team': self._format_situational,
            'comparison': self._format_comparison,
            'compare_teams': self._format_comparison,
            'decision': self._format_decision,
        }
        
        formatter = formatter_map.get(intent, self._format_generic)
        return formatter(data)
    
    def _format_team_stats(self, data: Dict) -> str:
        """Format team statistics."""
        team = self._team_name(data.get('team', ''))
        season = data.get('season', 2023)
        overall = data.get('overall', {})
        
        parts = [f"**{team} ({season})**\n"]
        
        # Offensive stats
        off_epa = overall.get('off_epa_per_play') or overall.get('epa_per_play', 0)
        if off_epa:
            if off_epa > 0.1:
                off_quality = "excellent"
            elif off_epa > 0:
                off_quality = "above average"
            elif off_epa > -0.05:
                off_quality = "average"
            else:
                off_quality = "below average"
            parts.append(f"• Offensive EPA/play: {off_epa:.3f} ({off_quality})")
        
        # Pass rate
        pass_rate = overall.get('pass_rate', 0)
        if pass_rate:
            parts.append(f"• Pass rate: {pass_rate:.1%}")
        
        # Defense
        defense = data.get('defense', {})
        def_epa = defense.get('epa_per_play', overall.get('def_epa_per_play', 0))
        if def_epa:
            # For defense, negative is good
            if def_epa < -0.1:
                def_quality = "excellent"
            elif def_epa < 0:
                def_quality = "above average"
            elif def_epa < 0.05:
                def_quality = "average"
            else:
                def_quality = "below average"
            parts.append(f"• Defensive EPA/play allowed: {def_epa:.3f} ({def_quality})")
        
        # Strengths and weaknesses
        strengths = data.get('strengths', [])
        weaknesses = data.get('weaknesses', [])
        
        if strengths:
            strengths_str = ', '.join(s.replace('_', ' ') for s in strengths)
            parts.append(f"• Strengths: {strengths_str}")
        
        if weaknesses:
            weaknesses_str = ', '.join(w.replace('_', ' ') for w in weaknesses)
            parts.append(f"• Weaknesses: {weaknesses_str}")
        
        return '\n'.join(parts)
    
    def _format_team_ranking(self, data: Dict) -> str:
        """Format team ranking."""
        team = self._team_name(data.get('team', ''))
        season = data.get('season', 2023)
        side = data.get('side', 'offense')
        rank = data.get('rank', 0)
        total = data.get('total_teams', 32)
        epa = data.get('epa_per_play', 0)
        percentile = data.get('percentile', 50)
        
        if rank <= 5:
            tier = "elite"
        elif rank <= 10:
            tier = "very good"
        elif rank <= 16:
            tier = "above average"
        elif rank <= 22:
            tier = "below average"
        else:
            tier = "struggling"
        
        return (
            f"**{team}'s {side.title()} Ranking ({season})**\n\n"
            f"Rank: **{self._ordinal(rank)}** out of {total} teams\n"
            f"EPA per play: {epa:.3f}\n"
            f"Percentile: {percentile:.0f}%\n\n"
            f"This puts them in the {tier} tier for {side}."
        )
    
    def _format_top_players(self, data: Dict) -> str:
        """Format top players list."""
        stat_type = data.get('stat_type', 'rushing')
        season = data.get('season', 2023)
        players = data.get('players', [])
        
        if not players:
            return f"No {stat_type} leaders found for {season}."
        
        parts = [f"**Top {stat_type.title()} Leaders ({season})**\n"]
        
        for p in players[:10]:
            rank = p.get('rank', 0)
            player_id = p.get('player_id', 'Unknown')
            epa = p.get('epa_per_play', p.get('shrunk_value', 0))
            attempts = p.get('attempts', p.get('targets', 0))
            
            parts.append(f"{rank}. {player_id}: {epa:.3f} EPA/play ({attempts} att)")
        
        note = data.get('note', '')
        if note:
            parts.append(f"\n_{note}_")
        
        return '\n'.join(parts)
    
    def _format_player_stats(self, data: Dict) -> str:
        """Format player statistics."""
        player_id = data.get('player_id', 'Unknown')
        season = data.get('season', 2023)
        
        parts = [f"**Player: {player_id} ({season})**\n"]
        
        # Check for different stat types
        raw = data.get('raw', {})
        shrunk = data.get('shrunk', {})
        
        if shrunk:
            epa = shrunk.get('epa_per_play', shrunk.get('epa_per_target', 0))
            parts.append(f"• EPA/play (adjusted): {epa:.3f}")
            
            shrinkage = data.get('shrinkage_applied', 0)
            if shrinkage > 0.2:
                parts.append(f"  _(Note: {shrinkage:.0%} shrinkage applied due to sample size)_")
        
        if raw:
            attempts = raw.get('attempts', raw.get('targets', 0))
            if attempts:
                parts.append(f"• Sample size: {attempts}")
        
        return '\n'.join(parts)
    
    def _format_situational(self, data: Dict) -> str:
        """Format situational statistics."""
        team = data.get('team')
        season = data.get('season', 2023)
        down = data.get('down')
        ydstogo = data.get('ydstogo')
        situations = data.get('situations', [])
        
        if team:
            team_name = self._team_name(team)
            header = f"**{team_name} Situational Tendencies ({season})**"
        else:
            header = f"**League Average Tendencies ({season})**"
        
        parts = [header]
        
        if down and ydstogo:
            parts.append(f"\nSituation: {self._ordinal(down)} & {ydstogo}\n")
        
        if situations:
            sit = situations[0]  # Most relevant situation
            parts.append(f"• Pass rate: {sit['pass_rate']:.1%}")
            parts.append(f"• Average EPA: {sit['epa_avg']:.3f}")
            parts.append(f"• Success rate: {sit['success_rate']:.1%}")
            parts.append(f"• Sample size: {sit['sample_size']} plays")
        
        # League comparison
        league = data.get('league_average')
        if league and team:
            diff = data.get('pass_rate_vs_league', 0)
            if diff > 0.05:
                parts.append(f"\n{team} passes more than league average (+{diff:.1%})")
            elif diff < -0.05:
                parts.append(f"\n{team} runs more than league average ({diff:.1%} pass rate vs league)")
        
        return '\n'.join(parts)
    
    def _format_comparison(self, data: Dict) -> str:
        """Format team comparison."""
        teams = data.get('teams', [])
        season = data.get('season', 2023)
        
        if len(teams) < 2:
            return "Unable to compare teams."
        
        team1 = self._team_name(teams[0])
        team2 = self._team_name(teams[1])
        
        parts = [f"**{team1} vs {team2} ({season})**\n"]
        
        # Stats comparison
        t1 = data.get('team1_stats', data.get('offense', {}))
        t2 = data.get('team2_stats', data.get('defense', {}))
        
        if t1 and t2:
            parts.append("**Offensive EPA/play**")
            t1_epa = t1.get('off_epa_per_play', t1.get('epa_per_play', [0])[0] if isinstance(t1.get('epa_per_play'), list) else t1.get('epa_per_play', 0))
            t2_epa = t2.get('off_epa_per_play', t2.get('epa_per_play', [0])[-1] if isinstance(t2.get('epa_per_play'), list) else t2.get('epa_per_play', 0))
            
            if isinstance(t1_epa, (int, float)) and isinstance(t2_epa, (int, float)):
                parts.append(f"• {teams[0]}: {t1_epa:.3f}")
                parts.append(f"• {teams[1]}: {t2_epa:.3f}")
        
        # Advantages
        advantages = data.get('advantages', [])
        if advantages:
            parts.append("\n**Key Differences**")
            for adv in advantages:
                parts.append(f"• {adv}")
        
        # Matchup notes
        notes = data.get('matchup_notes', [])
        if notes:
            parts.append("\n**Matchup Notes**")
            for note in notes:
                parts.append(f"• {note}")
        
        return '\n'.join(parts)
    
    def _format_decision(self, data: Dict) -> str:
        """Format play decision analysis."""
        situation = data.get('situation', {})
        down = situation.get('down', 0)
        ydstogo = situation.get('ydstogo', 0)
        yardline = situation.get('yardline_100', 50)
        
        parts = [f"**Play Decision: {self._ordinal(down)} & {ydstogo} at the {yardline}**\n"]
        
        # Run vs pass
        rvp = data.get('run_vs_pass', {})
        if rvp and 'recommendation' in rvp:
            rec = rvp['recommendation'].upper()
            conf = rvp.get('confidence', 0.5)
            
            parts.append(f"**Recommendation: {rec}**")
            parts.append(f"Confidence: {conf:.0%}")
            
            if 'pass_epa' in rvp and 'run_epa' in rvp:
                parts.append(f"\nExpected EPA:")
                parts.append(f"• Pass: {rvp['pass_epa']:.3f}")
                parts.append(f"• Run: {rvp['run_epa']:.3f}")
        
        # Fourth down specific
        sim = data.get('simulation', {})
        if sim and 'go_for_it' in sim:
            go = sim['go_for_it']
            fg = sim['field_goal']
            
            parts.append(f"\n**Fourth Down Analysis**")
            parts.append(f"• Go for it expected points: {go['expected_points']:.2f}")
            parts.append(f"  - TD probability: {go['td_probability']:.1%}")
            parts.append(f"  - Turnover probability: {go['turnover_probability']:.1%}")
            parts.append(f"• Field goal expected points: {fg['expected_points']:.2f}")
            parts.append(f"  - Make probability: {fg['success_probability']:.1%}")
        
        # Team adjustments
        adj = data.get('team_adjustments', {})
        if adj:
            team = data.get('team', '')
            parts.append(f"\n_Adjusted for {team}'s tendencies_")
        
        return '\n'.join(parts)
    
    def _format_generic(self, data: Dict) -> str:
        """Generic formatter for unhandled intents."""
        # Just return a summary of the data
        if not data:
            return "No data available."
        
        parts = []
        for key, value in data.items():
            if key not in ['sources', 'error']:
                if isinstance(value, dict):
                    parts.append(f"**{key.replace('_', ' ').title()}**")
                    for k, v in value.items():
                        parts.append(f"  • {k}: {v}")
                elif isinstance(value, list):
                    parts.append(f"**{key.replace('_', ' ').title()}**: {len(value)} items")
                else:
                    parts.append(f"**{key.replace('_', ' ').title()}**: {value}")
        
        return '\n'.join(parts) if parts else "Data retrieved successfully."
