-- Football Analytics Chatbot - Database Indexes
-- Run after schema.sql

-- Play-by-play indexes
CREATE INDEX IF NOT EXISTS idx_plays_game ON plays(game_id);
CREATE INDEX IF NOT EXISTS idx_plays_season ON plays(season);
CREATE INDEX IF NOT EXISTS idx_plays_team_off ON plays(posteam, season);
CREATE INDEX IF NOT EXISTS idx_plays_team_def ON plays(defteam, season);
CREATE INDEX IF NOT EXISTS idx_plays_situation ON plays(down, ydstogo, yardline_100);
CREATE INDEX IF NOT EXISTS idx_plays_personnel ON plays(offense_personnel);
CREATE INDEX IF NOT EXISTS idx_plays_player_pass ON plays(passer_player_id);
CREATE INDEX IF NOT EXISTS idx_plays_player_rush ON plays(rusher_player_id);
CREATE INDEX IF NOT EXISTS idx_plays_player_rec ON plays(receiver_player_id);
CREATE INDEX IF NOT EXISTS idx_plays_type ON plays(play_type);
CREATE INDEX IF NOT EXISTS idx_plays_season_team ON plays(season, posteam);

-- Derived table indexes
CREATE INDEX IF NOT EXISTS idx_team_stats_team ON team_season_stats(team, season);
CREATE INDEX IF NOT EXISTS idx_tendencies_team ON situational_tendencies(team, season);
CREATE INDEX IF NOT EXISTS idx_tendencies_situation ON situational_tendencies(down, distance_bucket, field_zone);
CREATE INDEX IF NOT EXISTS idx_tendencies_league ON situational_tendencies(season) WHERE team IS NULL;
CREATE INDEX IF NOT EXISTS idx_player_stats_player ON player_season_stats(player_id, season);
CREATE INDEX IF NOT EXISTS idx_player_stats_team ON player_season_stats(team, season);

-- Games indexes
CREATE INDEX IF NOT EXISTS idx_games_season ON games(season, week);
CREATE INDEX IF NOT EXISTS idx_games_teams ON games(home_team, away_team);

-- Analyze tables for query optimization
ANALYZE plays;
ANALYZE team_season_stats;
ANALYZE situational_tendencies;
ANALYZE player_season_stats;
