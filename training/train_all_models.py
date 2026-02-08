"""
Phase 2 Model Training Script

Trains all core models:
1. EPA Prediction Model
2. Team Identity Profiles
3. Player Effectiveness Model
4. Drive Simulator

Usage:
    python training/train_all_models.py
    python training/train_all_models.py --model epa
    python training/train_all_models.py --season 2023
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
import pandas as pd

from models.epa_model import EPAPredictor, load_training_data
from models.team_profiles import TeamProfiler
from models.player_effectiveness import PlayerEffectivenessModel
from models.drive_simulator import DriveSimulator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://127.0.0.1:5432/football_analytics")

# Model output directory
MODEL_DIR = Path("data/models")


def train_epa_model(conn, model_dir: Path) -> dict:
    """Train the EPA prediction model."""
    logger.info("=" * 50)
    logger.info("Training EPA Prediction Model")
    logger.info("=" * 50)
    
    # Load data
    train_seasons = [2016, 2017, 2018, 2019, 2020, 2021, 2022]
    val_seasons = [2025]
    
    logger.info(f"Training seasons: {train_seasons}")
    logger.info(f"Validation seasons: {val_seasons}")
    
    train_df, val_df = load_training_data(conn, train_seasons, val_seasons)
    
    logger.info(f"Training samples: {len(train_df):,}")
    logger.info(f"Validation samples: {len(val_df):,}")
    
    # Train model
    model = EPAPredictor(model_type='lightgbm')
    
    metrics = model.fit(train_df, target_col='epa', val_df=val_df)
    
    # Log metrics
    logger.info(f"Training RMSE: {metrics['train_rmse']:.4f}")
    logger.info(f"Training R²: {metrics['train_r2']:.4f}")
    if 'val_rmse' in metrics:
        logger.info(f"Validation RMSE: {metrics['val_rmse']:.4f}")
        logger.info(f"Validation R²: {metrics['val_r2']:.4f}")
    
    # Feature importance
    importance = model.get_feature_importance()
    logger.info("\nTop 5 features:")
    for _, row in importance.head(5).iterrows():
        logger.info(f"  {row['feature']}: {row['importance']:.4f}")
    
    # Save model
    model_path = model_dir / "epa_model.joblib"
    model.save(str(model_path))
    
    # Quick test
    logger.info("\nQuick test - 3rd and 5 at opponent 40:")
    comparison = model.compare_play_types(
        down=3, ydstogo=5, yardline_100=40,
        quarter=3, score_differential=0
    )
    logger.info(f"  Pass EPA: {comparison['pass_epa']:.4f}")
    logger.info(f"  Run EPA: {comparison['run_epa']:.4f}")
    logger.info(f"  Recommendation: {comparison['recommendation']}")
    
    return metrics


def build_team_profiles(conn, model_dir: Path, season: int = 2025) -> dict:
    """Build team identity profiles."""
    logger.info("=" * 50)
    logger.info(f"Building Team Profiles for {season}")
    logger.info("=" * 50)
    
    profiler = TeamProfiler()
    
    # Build all profiles
    profiles = profiler.build_all_profiles(conn, season)
    
    logger.info(f"Built profiles for {len(profiles)} teams")
    
    # Show example profile
    example_team = 'KC'
    if example_team in profiles:
        profile = profiles[example_team]
        logger.info(f"\nExample: {example_team}")
        logger.info(f"  Offensive EPA/play: {profile['overall']['epa_per_play']:.4f}")
        logger.info(f"  Pass rate: {profile['overall']['pass_rate']:.1%}")
        logger.info(f"  Strengths: {profile['strengths']}")
        logger.info(f"  Weaknesses: {profile['weaknesses']}")
    
    # Save profiles
    profile_path = model_dir / "team_profiles.json"
    profiler.save(str(profile_path))
    
    return {'teams': len(profiles), 'season': season}


def build_player_models(conn, model_dir: Path, season: int = 2025) -> dict:
    """Build player effectiveness models."""
    logger.info("=" * 50)
    logger.info(f"Building Player Effectiveness Models for {season}")
    logger.info("=" * 50)
    
    model = PlayerEffectivenessModel(shrinkage_k=30)
    
    # Build position priors
    priors = model.build_position_priors(conn, season)
    logger.info(f"Position priors built")
    logger.info(f"  Rushing prior EPA: {priors['rushing']['mean_epa']:.4f}")
    logger.info(f"  Passing prior EPA: {priors['passing']['mean_epa']:.4f}")
    
    # Build player estimates
    estimates = model.build_player_estimates(conn, season)
    logger.info(f"Built estimates for {len(estimates)} players")
    
    # Show top rushers
    logger.info("\nTop 5 rushers by shrunk EPA (min 50 attempts):")
    top_rushers = model.get_top_players('rushing', 'epa_per_play', min_attempts=50, n=5)
    for i, rusher in enumerate(top_rushers, 1):
        logger.info(f"  {i}. {rusher['player_id']}: {rusher['epa_per_play']:.4f} EPA/play "
                   f"({rusher['attempts']} att, {rusher['shrinkage_applied']:.0%} shrinkage)")
    
    # Save model
    model_path = model_dir / "player_estimates.json"
    model.save(str(model_path))
    
    return {'players': len(estimates), 'season': season}


def setup_drive_simulator(conn, model_dir: Path) -> dict:
    """Set up drive simulator with historical distributions."""
    logger.info("=" * 50)
    logger.info("Setting Up Drive Simulator")
    logger.info("=" * 50)
    
    simulator = DriveSimulator()
    
    # Load distributions
    simulator.load_distributions(conn, seasons=[2020, 2021, 2022, 2023, 2024, 2025])
    
    logger.info(f"Loaded {len(simulator.play_distributions)} situation distributions")
    logger.info(f"Loaded {len(simulator.fg_success_rates)} FG distance rates")
    
    # Test simulation
    logger.info("\nTest: 4th and 2 at opponent 35")
    result = simulator.simulate_decision(down=4, ydstogo=2, yardline=35, n_simulations=2000)
    
    logger.info(f"  Go for it EP: {result['go_for_it']['expected_points']:.3f}")
    logger.info(f"  Field goal EP: {result['field_goal']['expected_points']:.3f}")
    logger.info(f"  Recommendation: {result['recommendation']}")
    logger.info(f"  Confidence: {result['confidence']:.1%}")
    
    # Note: Drive simulator doesn't need to be saved - it loads from DB each time
    # But we could pickle the distributions if needed
    
    return {
        'distributions': len(simulator.play_distributions),
        'fg_rates': len(simulator.fg_success_rates),
    }


def main():
    parser = argparse.ArgumentParser(description='Train Phase 2 models')
    parser.add_argument('--model', choices=['epa', 'team', 'player', 'simulator', 'all'],
                        default='all', help='Which model to train')
    parser.add_argument('--season', type=int, default=2025,
                        help='Season for team/player profiles')
    args = parser.parse_args()
    
    # Create model directory
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    
    logger.info("=" * 60)
    logger.info("Phase 2: Model Training")
    logger.info(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)
    logger.info("")
    
    # Connect to database
    try:
        conn = psycopg2.connect(DATABASE_URL)
        logger.info("Connected to database")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        sys.exit(1)
    
    results = {}
    
    try:
        if args.model in ['epa', 'all']:
            results['epa'] = train_epa_model(conn, MODEL_DIR)
        
        if args.model in ['team', 'all']:
            results['team'] = build_team_profiles(conn, MODEL_DIR, args.season)
        
        if args.model in ['player', 'all']:
            results['player'] = build_player_models(conn, MODEL_DIR, args.season)
        
        if args.model in ['simulator', 'all']:
            results['simulator'] = setup_drive_simulator(conn, MODEL_DIR)
        
    except Exception as e:
        logger.error(f"Training failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        conn.close()
    
    logger.info("")
    logger.info("=" * 60)
    logger.info("Training Complete!")
    logger.info("=" * 60)
    logger.info(f"Models saved to: {MODEL_DIR}")
    
    for model_name, model_results in results.items():
        logger.info(f"  {model_name}: {model_results}")
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
