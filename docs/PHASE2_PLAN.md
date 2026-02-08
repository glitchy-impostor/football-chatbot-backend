# Phase 2: Core Models — Implementation Plan

## Overview

Phase 2 builds the analytical models that power the chatbot's intelligence. These models transform raw play-by-play data into actionable insights.

| Model | Purpose | Output |
|-------|---------|--------|
| EPA Prediction | Predict expected EPA for play calls | Run vs Pass recommendation with confidence |
| Team Identity Profiles | Quantify how teams differ from league average | Deviation vectors, archetype clusters |
| Player Effectiveness | Context-aware player performance estimates | Shrunk estimates with confidence intervals |
| Drive Simulator | Monte Carlo simulation of drive outcomes | Expected points, TD/FG/TO probabilities |

---

## Phase 2 Directory Structure

```
football-chatbot/
├── models/
│   ├── __init__.py
│   ├── epa_model.py           # EPA prediction model
│   ├── team_profiles.py       # Team identity profiles
│   ├── player_effectiveness.py # Player shrinkage model
│   └── drive_simulator.py     # Monte Carlo simulator
├── training/
│   ├── train_epa_model.py     # Train EPA model
│   ├── build_team_profiles.py # Generate team profiles
│   └── build_player_models.py # Build player estimates
├── tests/
│   ├── phase1/                # (existing)
│   └── phase2/
│       ├── test_epa_model.py
│       ├── test_team_profiles.py
│       ├── test_player_effectiveness.py
│       ├── test_drive_simulator.py
│       └── run_phase2_validation.py
├── data/
│   └── models/                # Saved model artifacts
│       ├── epa_model.joblib
│       ├── team_profiles.json
│       └── player_estimates.json
└── notebooks/                 # (optional) exploration
```

---

## Model 1: EPA Prediction

### Purpose
Predict the expected EPA for a play given the game situation, allowing comparison between run and pass options.

### Features
| Feature | Type | Description |
|---------|------|-------------|
| down | categorical | 1, 2, 3, 4 |
| ydstogo | numeric | Yards to first down |
| yardline_100 | numeric | Distance from opponent's end zone |
| quarter | categorical | 1, 2, 3, 4, 5 (OT) |
| score_differential | numeric | Offense score - Defense score |
| shotgun | binary | In shotgun formation |
| no_huddle | binary | No-huddle offense |
| half_seconds_remaining | numeric | Seconds left in half |
| posteam_timeouts | numeric | Timeouts remaining (if available) |
| is_home | binary | Is possession team at home |

### Target
- `epa` (continuous) — Expected Points Added

### Architecture
- **Algorithm:** Gradient Boosted Trees (XGBoost or LightGBM)
- **Why:** Handles non-linear relationships, feature interactions, missing values well
- **Output:** Point estimate + can get prediction intervals via quantile regression

### Training Strategy
- Train on 2016-2022 data
- Validate on 2023 data
- Test on 2024 data
- Retrain weekly during season

---

## Model 2: Team Identity Profiles

### Purpose
Quantify each team's tendencies and effectiveness relative to league average.

### Profile Components
1. **Tendency Deviations** — How much more/less they pass in each situation
2. **Effectiveness Deviations** — EPA difference from league average
3. **Situational Strengths** — Where they excel vs struggle
4. **Style Indicators** — Shotgun rate, no-huddle rate, explosiveness

### Output Format
```json
{
  "team": "KC",
  "season": 2023,
  "overall": {
    "off_epa_rank": 2,
    "def_epa_rank": 8,
    "pass_rate_vs_league": 0.05,
    "shotgun_rate": 0.78
  },
  "situational": {
    "third_medium": {
      "pass_rate_vs_league": 0.12,
      "epa_vs_league": 0.15,
      "sample_size": 145
    }
  },
  "strengths": ["passing_efficiency", "red_zone_offense"],
  "weaknesses": ["run_defense", "third_down_defense"]
}
```

### Implementation
- Precompute nightly/weekly
- Store as JSON in database or file
- Cache in Redis for fast retrieval

---

## Model 3: Player Effectiveness

### Problem
Player stats in specific contexts have tiny sample sizes. A RB with 5 carries in the red zone isn't reliably estimated.

### Solution: Bayesian Shrinkage
1. Compute raw player stats per context
2. Group players into archetypes (similar players)
3. Shrink individual estimates toward archetype mean
4. Amount of shrinkage depends on sample size

### Formula
```
shrunk_estimate = (n * player_mean + k * archetype_mean) / (n + k)
```
Where:
- `n` = player's sample size
- `k` = shrinkage strength (tuned, typically 10-50)
- Higher `n` → estimate closer to player's actual performance
- Lower `n` → estimate closer to archetype average

### Player Archetypes
| Position | Archetypes |
|----------|------------|
| QB | Pocket passer, Dual-threat, Game manager |
| RB | Power back, Speed back, Receiving back, Committee |
| WR | Outside X, Slot, Deep threat, Possession |
| TE | Blocking TE, Receiving TE, Hybrid |

### Output
```json
{
  "player_id": "00-123456",
  "name": "Player Name",
  "position": "RB",
  "archetype": "power_back",
  "season": 2023,
  "overall": {
    "epa_per_play": 0.05,
    "confidence_interval": [-0.02, 0.12],
    "sample_size": 180
  },
  "situational": {
    "red_zone": {
      "epa_per_play": 0.15,
      "shrinkage_applied": 0.4,
      "sample_size": 12
    }
  }
}
```

---

## Model 4: Drive Simulator

### Purpose
Simulate many possible drive outcomes to estimate:
- Expected points
- Probability of TD, FG, punt, turnover
- Compare "go for it" vs "kick" decisions

### Approach: Historical Resampling
1. Given starting situation (down, distance, field position, score)
2. Find similar historical plays
3. Sample an outcome
4. Update state
5. Repeat until drive ends
6. Run 5,000-10,000 simulations

### State Transitions
```
Play → First Down → Continue drive
Play → Touchdown → +7 points, end
Play → Field Goal → +3 points, end  
Play → Turnover → 0 points, end
Play → Punt → 0 points, end
Play → Failed 4th → 0 points, end
```

### Output
```json
{
  "situation": {
    "down": 4,
    "distance": 2,
    "yardline": 35,
    "score_diff": -4
  },
  "simulations": 10000,
  "go_for_it": {
    "expected_points": 2.1,
    "td_prob": 0.28,
    "fg_prob": 0.15,
    "turnover_prob": 0.42
  },
  "field_goal": {
    "expected_points": 1.6,
    "success_prob": 0.53
  },
  "recommendation": "go_for_it",
  "confidence": 0.72
}
```

---

## Implementation Order

1. **EPA Prediction Model** (foundation for everything else)
2. **Team Identity Profiles** (needed for team-aware recommendations)
3. **Player Effectiveness** (adds player-level intelligence)
4. **Drive Simulator** (builds on all above)

---

## Dependencies to Install

```bash
pip install scikit-learn xgboost lightgbm joblib
```

Add to requirements.txt:
```
scikit-learn>=1.3.0
xgboost>=2.0.0
lightgbm>=4.0.0
joblib>=1.3.0
```
