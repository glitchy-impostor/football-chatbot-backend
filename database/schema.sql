-- Football Analytics Chatbot - Database Schema
-- Phase 1: Core Tables

-- Core play-by-play table
CREATE TABLE IF NOT EXISTS plays (
    id SERIAL PRIMARY KEY,
    game_id VARCHAR(20) NOT NULL,
    play_id BIGINT NOT NULL,  -- BIGINT for 2025+ seasons
    
    -- Game context
    season INTEGER NOT NULL,
    week INTEGER NOT NULL,
    season_type VARCHAR(10),
    home_team VARCHAR(5),
    away_team VARCHAR(5),
    
    -- Play context
    posteam VARCHAR(5),
    defteam VARCHAR(5),
    quarter INTEGER,
    time_remaining_half INTEGER,
    down INTEGER,
    ydstogo INTEGER,
    yardline_100 INTEGER,
    
    -- Score context
    posteam_score INTEGER,
    defteam_score INTEGER,
    score_differential INTEGER,
    
    -- Play details
    play_type VARCHAR(20),
    pass INTEGER,
    rush INTEGER,
    yards_gained INTEGER,
    
    -- Personnel (2016+)
    offense_personnel VARCHAR(50),
    defense_personnel VARCHAR(50),
    defenders_in_box INTEGER,
    
    -- Formation indicators
    shotgun INTEGER,
    no_huddle INTEGER,
    
    -- Outcomes
    epa DECIMAL(8,4),
    wpa DECIMAL(8,4),
    success INTEGER,
    touchdown INTEGER,
    interception INTEGER,
    fumble INTEGER,
    first_down INTEGER,
    
    -- Player IDs
    passer_player_id VARCHAR(20),
    rusher_player_id VARCHAR(20),
    receiver_player_id VARCHAR(20),
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(game_id, play_id)
);

-- Games table
CREATE TABLE IF NOT EXISTS games (
    game_id VARCHAR(20) PRIMARY KEY,
    season INTEGER NOT NULL,
    week INTEGER NOT NULL,
    season_type VARCHAR(10),
    game_date DATE,
    home_team VARCHAR(5),
    away_team VARCHAR(5),
    home_score INTEGER,
    away_score INTEGER,
    result VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Rosters table
CREATE TABLE IF NOT EXISTS rosters (
    id SERIAL PRIMARY KEY,
    season INTEGER NOT NULL,
    team VARCHAR(5) NOT NULL,
    player_id VARCHAR(20),
    player_name VARCHAR(100),
    position VARCHAR(10),
    jersey_number INTEGER,
    height VARCHAR(10),
    weight INTEGER,
    college VARCHAR(100),
    birth_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(season, player_id)
);

-- Team season stats (derived)
CREATE TABLE IF NOT EXISTS team_season_stats (
    id SERIAL PRIMARY KEY,
    team VARCHAR(5) NOT NULL,
    season INTEGER NOT NULL,
    
    -- Offensive stats
    off_plays INTEGER,
    off_epa_total DECIMAL(10,4),
    off_epa_per_play DECIMAL(8,4),
    off_pass_rate DECIMAL(5,4),
    off_success_rate DECIMAL(5,4),
    off_explosive_rate DECIMAL(5,4),
    
    -- Defensive stats
    def_plays INTEGER,
    def_epa_total DECIMAL(10,4),
    def_epa_per_play DECIMAL(8,4),
    def_success_rate DECIMAL(5,4),
    
    -- Situational
    early_down_pass_rate DECIMAL(5,4),
    third_down_conv_rate DECIMAL(5,4),
    red_zone_td_rate DECIMAL(5,4),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(team, season)
);

-- Situational tendencies (derived)
CREATE TABLE IF NOT EXISTS situational_tendencies (
    id SERIAL PRIMARY KEY,
    team VARCHAR(5),  -- NULL for league average
    season INTEGER NOT NULL,
    
    -- Situation definition
    down INTEGER,
    distance_bucket VARCHAR(20),  -- 'short', 'medium', 'long'
    field_zone VARCHAR(20),       -- 'own_deep', 'own_territory', 'opp_territory', 'red_zone'
    score_bucket VARCHAR(20),     -- 'losing_big', 'losing', 'tied', 'winning', 'winning_big'
    
    -- Tendencies
    sample_size INTEGER,
    pass_rate DECIMAL(5,4),
    run_rate DECIMAL(5,4),
    epa_avg DECIMAL(8,4),
    success_rate DECIMAL(5,4),
    
    -- Play type breakdown (JSON)
    play_type_dist JSONB,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(team, season, down, distance_bucket, field_zone, score_bucket)
);

-- Player season stats (derived)
CREATE TABLE IF NOT EXISTS player_season_stats (
    id SERIAL PRIMARY KEY,
    player_id VARCHAR(20) NOT NULL,
    player_name VARCHAR(100),
    team VARCHAR(5),
    position VARCHAR(10),
    season INTEGER NOT NULL,
    
    -- Passing stats
    pass_attempts INTEGER DEFAULT 0,
    completions INTEGER DEFAULT 0,
    pass_yards INTEGER DEFAULT 0,
    pass_td INTEGER DEFAULT 0,
    interceptions INTEGER DEFAULT 0,
    pass_epa DECIMAL(10,4) DEFAULT 0,
    cpoe DECIMAL(8,4),
    
    -- Rushing stats
    rush_attempts INTEGER DEFAULT 0,
    rush_yards INTEGER DEFAULT 0,
    rush_td INTEGER DEFAULT 0,
    rush_epa DECIMAL(10,4) DEFAULT 0,
    
    -- Receiving stats
    targets INTEGER DEFAULT 0,
    receptions INTEGER DEFAULT 0,
    rec_yards INTEGER DEFAULT 0,
    rec_td INTEGER DEFAULT 0,
    rec_epa DECIMAL(10,4) DEFAULT 0,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(player_id, season)
);

-- Log table for data refresh tracking
CREATE TABLE IF NOT EXISTS data_refresh_log (
    id SERIAL PRIMARY KEY,
    refresh_type VARCHAR(50) NOT NULL,
    season INTEGER,
    rows_affected INTEGER,
    status VARCHAR(20),
    error_message TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);
