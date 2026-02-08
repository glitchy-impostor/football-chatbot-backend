#!/usr/bin/env python3
"""
Phase 2 Validation Script

Validates that all Phase 2 models are built and working correctly.

Usage:
    python tests/phase2/run_phase2_validation.py
"""

import os
import sys
from pathlib import Path
from datetime import datetime

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import psycopg2
import json

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://127.0.0.1:5432/football_analytics")
MODEL_DIR = Path("data/models")

CHECKS = []


def check(name):
    """Decorator to register a check."""
    def decorator(func):
        CHECKS.append((name, func))
        return func
    return decorator


# =============================================================================
# EPA MODEL CHECKS
# =============================================================================

@check("EPA Model File Exists")
def check_epa_model_exists():
    path = MODEL_DIR / "epa_model.joblib"
    return path.exists(), f"Path: {path}"


@check("EPA Model Loads Successfully")
def check_epa_model_loads():
    try:
        from models.epa_model import EPAPredictor
        model = EPAPredictor.load(str(MODEL_DIR / "epa_model.joblib"))
        return model.is_fitted, "Model loaded and fitted"
    except Exception as e:
        return False, str(e)


@check("EPA Model Makes Predictions")
def check_epa_model_predicts():
    try:
        from models.epa_model import EPAPredictor
        model = EPAPredictor.load(str(MODEL_DIR / "epa_model.joblib"))
        
        # Test prediction
        result = model.compare_play_types(
            down=3, ydstogo=5, yardline_100=40,
            quarter=2, score_differential=0
        )
        
        has_keys = all(k in result for k in ['pass_epa', 'run_epa', 'recommendation'])
        return has_keys, f"Pass EPA: {result['pass_epa']:.4f}, Run EPA: {result['run_epa']:.4f}"
    except Exception as e:
        return False, str(e)


@check("EPA Model Predictions Reasonable")
def check_epa_predictions_reasonable():
    try:
        from models.epa_model import EPAPredictor
        model = EPAPredictor.load(str(MODEL_DIR / "epa_model.joblib"))
        
        # Test various situations
        tests = [
            {'down': 1, 'ydstogo': 10, 'yardline_100': 75},
            {'down': 3, 'ydstogo': 1, 'yardline_100': 50},
            {'down': 3, 'ydstogo': 15, 'yardline_100': 30},
            {'down': 4, 'ydstogo': 1, 'yardline_100': 5},
        ]
        
        all_reasonable = True
        for test in tests:
            result = model.compare_play_types(**test, quarter=2, score_differential=0)
            # EPA should be between -3 and 3 typically
            if not (-3 < result['pass_epa'] < 3 and -3 < result['run_epa'] < 3):
                all_reasonable = False
                break
        
        return all_reasonable, "All predictions in reasonable range"
    except Exception as e:
        return False, str(e)


# =============================================================================
# TEAM PROFILES CHECKS
# =============================================================================

@check("Team Profiles File Exists")
def check_team_profiles_exists():
    path = MODEL_DIR / "team_profiles.json"
    return path.exists(), f"Path: {path}"


@check("Team Profiles Loads Successfully")
def check_team_profiles_loads():
    try:
        from models.team_profiles import TeamProfiler
        profiler = TeamProfiler.load(str(MODEL_DIR / "team_profiles.json"))
        count = len(profiler.profiles)
        return count >= 30, f"Loaded {count} team profiles"
    except Exception as e:
        return False, str(e)


@check("Team Profiles Have Expected Structure")
def check_team_profiles_structure():
    try:
        from models.team_profiles import TeamProfiler
        profiler = TeamProfiler.load(str(MODEL_DIR / "team_profiles.json"))
        
        # Check a profile has expected keys
        profile = list(profiler.profiles.values())[0]
        expected_keys = ['team', 'season', 'overall', 'defense', 'deviations', 'situational']
        
        has_keys = all(k in profile for k in expected_keys)
        
        # Check overall has metrics
        overall_keys = ['pass_rate', 'epa_per_play', 'success_rate']
        has_overall = all(k in profile.get('overall', {}) for k in overall_keys)
        
        return has_keys and has_overall, f"Profile has all expected keys"
    except Exception as e:
        return False, str(e)


@check("Team Profile Values Reasonable")
def check_team_profile_values():
    try:
        from models.team_profiles import TeamProfiler
        profiler = TeamProfiler.load(str(MODEL_DIR / "team_profiles.json"))
        
        all_reasonable = True
        for team, profile in profiler.profiles.items():
            overall = profile.get('overall', {})
            
            # Pass rate should be 0.4-0.75
            pr = overall.get('pass_rate', 0)
            if not (0.4 < pr < 0.75):
                all_reasonable = False
                break
            
            # EPA should be -0.3 to 0.3
            epa = overall.get('epa_per_play', 0)
            if not (-0.4 < epa < 0.4):
                all_reasonable = False
                break
        
        return all_reasonable, "All team values in reasonable ranges"
    except Exception as e:
        return False, str(e)


# =============================================================================
# PLAYER EFFECTIVENESS CHECKS
# =============================================================================

@check("Player Estimates File Exists")
def check_player_model_exists():
    path = MODEL_DIR / "player_estimates.json"
    return path.exists(), f"Path: {path}"


@check("Player Model Loads Successfully")
def check_player_model_loads():
    try:
        from models.player_effectiveness import PlayerEffectivenessModel
        model = PlayerEffectivenessModel.load(str(MODEL_DIR / "player_estimates.json"))
        count = len(model.player_estimates)
        return count >= 100, f"Loaded {count} player estimates"
    except Exception as e:
        return False, str(e)


@check("Player Estimates Have Shrinkage Applied")
def check_player_shrinkage():
    try:
        from models.player_effectiveness import PlayerEffectivenessModel
        model = PlayerEffectivenessModel.load(str(MODEL_DIR / "player_estimates.json"))
        
        # Check that shrinkage was applied
        shrinkage_applied = False
        for player_id, estimate in model.player_estimates.items():
            if estimate.get('shrinkage_applied', 0) > 0:
                shrinkage_applied = True
                break
        
        return shrinkage_applied, "Shrinkage is being applied"
    except Exception as e:
        return False, str(e)


@check("Top Players Query Works")
def check_top_players():
    try:
        from models.player_effectiveness import PlayerEffectivenessModel
        model = PlayerEffectivenessModel.load(str(MODEL_DIR / "player_estimates.json"))
        
        top = model.get_top_players('rushing', 'epa_per_play', min_attempts=30, n=5)
        
        return len(top) >= 3, f"Found {len(top)} top rushers"
    except Exception as e:
        return False, str(e)


# =============================================================================
# DRIVE SIMULATOR CHECKS
# =============================================================================

@check("Drive Simulator Initializes")
def check_simulator_init():
    try:
        from models.drive_simulator import DriveSimulator
        sim = DriveSimulator()
        return True, "Simulator created"
    except Exception as e:
        return False, str(e)


@check("Drive Simulator Loads Distributions")
def check_simulator_loads():
    try:
        from models.drive_simulator import DriveSimulator
        conn = psycopg2.connect(DATABASE_URL)
        
        sim = DriveSimulator()
        sim.load_distributions(conn, seasons=[2022, 2023, 2024])
        
        conn.close()
        
        count = len(sim.play_distributions)
        return count >= 50, f"Loaded {count} distributions"
    except Exception as e:
        return False, str(e)


@check("Drive Simulator Decision Analysis Works")
def check_simulator_decision():
    try:
        from models.drive_simulator import DriveSimulator
        conn = psycopg2.connect(DATABASE_URL)
        
        sim = DriveSimulator()
        sim.load_distributions(conn, seasons=[2022, 2023, 2024])
        
        result = sim.simulate_decision(down=4, ydstogo=2, yardline=35, n_simulations=500)
        
        conn.close()
        
        has_keys = all(k in result for k in ['go_for_it', 'field_goal', 'recommendation'])
        return has_keys, f"Recommendation: {result['recommendation']}"
    except Exception as e:
        return False, str(e)


# =============================================================================
# INTEGRATION CHECKS
# =============================================================================

@check("All Model Files Present")
def check_all_files():
    files = [
        MODEL_DIR / "epa_model.joblib",
        MODEL_DIR / "team_profiles.json",
        MODEL_DIR / "player_estimates.json",
    ]
    
    present = [f.exists() for f in files]
    return all(present), f"{sum(present)}/{len(files)} files present"


@check("Models Work Together (Situation Analysis)")
def check_integration():
    try:
        from models.epa_model import EPAPredictor
        from models.team_profiles import TeamProfiler
        
        # Load models
        epa_model = EPAPredictor.load(str(MODEL_DIR / "epa_model.joblib"))
        profiler = TeamProfiler.load(str(MODEL_DIR / "team_profiles.json"))
        
        # Get team adjustment
        team = 'KC'
        profile = None
        for key, p in profiler.profiles.items():
            if team in key:
                profile = p
                break
        
        if not profile:
            return False, "Could not find team profile"
        
        team_pass_adj = profile['overall']['pass_epa'] - profile['overall'].get('epa_per_play', 0)
        team_run_adj = profile['overall']['rush_epa'] - profile['overall'].get('epa_per_play', 0)
        
        # Get EPA prediction with team adjustment
        result = epa_model.compare_play_types(
            down=3, ydstogo=5, yardline_100=40,
            quarter=2, score_differential=0,
            team_pass_adjustment=team_pass_adj,
            team_run_adjustment=team_run_adj
        )
        
        return True, f"Team-adjusted recommendation: {result['recommendation']}"
    except Exception as e:
        return False, str(e)


# =============================================================================
# RUNNER
# =============================================================================

def run_validation():
    """Run all Phase 2 validation checks."""
    print("=" * 70)
    print("PHASE 2 VALIDATION - Core Models")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()
    
    # Check model directory exists
    if not MODEL_DIR.exists():
        print(f"❌ Model directory not found: {MODEL_DIR}")
        print()
        print("Please run training first:")
        print("  python training/train_all_models.py")
        return False
    
    passed = 0
    failed = 0
    
    print("-" * 70)
    print("Running checks...")
    print("-" * 70)
    print()
    
    for name, check_func in CHECKS:
        try:
            result = check_func()
            if isinstance(result, tuple):
                ok, detail = result
            else:
                ok, detail = result, ""
            
            if ok:
                status = "✅ PASS"
                passed += 1
            else:
                status = "❌ FAIL"
                failed += 1
            
            detail_str = f" → {detail}" if detail else ""
            print(f"  {status} | {name}{detail_str}")
            
        except Exception as e:
            print(f"  ❌ FAIL | {name} → Error: {e}")
            failed += 1
    
    print()
    print("=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)
    
    if failed == 0:
        print()
        print("🎉 PHASE 2 COMPLETE!")
        print()
        print("Your core models are ready:")
        print("  • EPA Prediction: Predicts expected points for play calls")
        print("  • Team Profiles: Quantifies team tendencies vs league average")
        print("  • Player Effectiveness: Shrunk estimates for player performance")
        print("  • Drive Simulator: Monte Carlo simulation for decision analysis")
        print()
        print("Ready to proceed to Phase 3: Pipeline Infrastructure")
        print()
        return True
    else:
        print()
        print("⚠️  Phase 2 has failures. Please fix before proceeding.")
        print()
        print("Common fixes:")
        print("  - If models missing: python training/train_all_models.py")
        print("  - If imports fail: pip install lightgbm xgboost joblib")
        print()
        return False


if __name__ == "__main__":
    success = run_validation()
    sys.exit(0 if success else 1)
