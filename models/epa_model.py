"""
EPA Prediction Model

Predicts Expected Points Added (EPA) for a play given the game situation.
Used to compare run vs pass expected outcomes and make recommendations.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# Feature columns for the model
FEATURE_COLUMNS = [
    'down',
    'ydstogo', 
    'yardline_100',
    'quarter',
    'score_differential',
    'shotgun',
    'no_huddle',
    'half_seconds_remaining',
    'is_home',
    'ydstogo_pct',  # ydstogo / yardline_100 (how much of remaining field needed)
    'goal_to_go',   # 1 if ydstogo >= yardline_100
    'late_half',    # 1 if < 120 seconds in half
    'two_min_drill', # 1 if < 120 seconds AND losing
]

# Optional defensive features (used when available)
DEFENSIVE_FEATURES = [
    'defenders_in_box',  # Number of defenders in the box (impacts run/pass efficiency)
]

CATEGORICAL_FEATURES = ['down', 'quarter']


class EPAPredictor:
    """
    Gradient boosted model for predicting play EPA.
    """
    
    def __init__(self, model_type: str = 'lightgbm'):
        """
        Initialize the EPA predictor.
        
        Args:
            model_type: 'lightgbm' or 'xgboost'
        """
        self.model_type = model_type
        self.model = None
        self.feature_columns = FEATURE_COLUMNS.copy()
        self.is_fitted = False
        
    def _create_model(self, params: Optional[Dict] = None):
        """Create the underlying model."""
        default_params = {
            'n_estimators': 500,
            'learning_rate': 0.05,
            'max_depth': 6,
            'min_child_samples': 50,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'random_state': 42,
            'verbose': -1,
        }
        
        if params:
            default_params.update(params)
        
        if self.model_type == 'lightgbm':
            import lightgbm as lgb
            self.model = lgb.LGBMRegressor(**default_params)
        elif self.model_type == 'xgboost':
            import xgboost as xgb
            # Translate params for xgboost
            xgb_params = {
                'n_estimators': default_params['n_estimators'],
                'learning_rate': default_params['learning_rate'],
                'max_depth': default_params['max_depth'],
                'min_child_weight': default_params.get('min_child_samples', 50),
                'subsample': default_params['subsample'],
                'colsample_bytree': default_params['colsample_bytree'],
                'random_state': default_params['random_state'],
                'verbosity': 0,
            }
            self.model = xgb.XGBRegressor(**xgb_params)
        else:
            raise ValueError(f"Unknown model type: {self.model_type}")
    
    def _engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Engineer additional features from base features.
        
        Args:
            df: DataFrame with base features
            
        Returns:
            DataFrame with engineered features added
        """
        df = df.copy()
        
        # Yards to go as percentage of remaining field
        df['ydstogo_pct'] = np.where(
            df['yardline_100'] > 0,
            df['ydstogo'] / df['yardline_100'],
            0
        )
        df['ydstogo_pct'] = df['ydstogo_pct'].clip(0, 1)
        
        # Goal to go indicator
        df['goal_to_go'] = (df['ydstogo'] >= df['yardline_100']).astype(int)
        
        # Late half indicator (last 2 minutes)
        if 'half_seconds_remaining' in df.columns:
            df['late_half'] = (df['half_seconds_remaining'] < 120).astype(int)
            
            # Two minute drill (late AND losing)
            df['two_min_drill'] = (
                (df['half_seconds_remaining'] < 120) & 
                (df['score_differential'] < 0)
            ).astype(int)
        else:
            df['late_half'] = 0
            df['two_min_drill'] = 0
        
        # Fill missing is_home
        if 'is_home' not in df.columns:
            df['is_home'] = 0
            
        return df
    
    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepare features for model input.
        
        Args:
            df: Raw DataFrame with play data
            
        Returns:
            DataFrame with model-ready features
        """
        # Engineer features
        df = self._engineer_features(df)
        
        # Select only needed columns
        available_cols = [c for c in self.feature_columns if c in df.columns]
        X = df[available_cols].copy()
        
        # Fill missing values
        X = X.fillna(0)
        
        return X
    
    def fit(self, df: pd.DataFrame, target_col: str = 'epa', 
            val_df: Optional[pd.DataFrame] = None,
            params: Optional[Dict] = None) -> Dict:
        """
        Train the EPA prediction model.
        
        Args:
            df: Training DataFrame
            target_col: Name of target column
            val_df: Optional validation DataFrame
            params: Optional model parameters
            
        Returns:
            Dictionary with training metrics
        """
        logger.info("Preparing training features...")
        X_train = self.prepare_features(df)
        y_train = df[target_col].values
        
        # Store actual feature columns used
        self.feature_columns = X_train.columns.tolist()
        
        # Create model
        self._create_model(params)
        
        # Prepare validation data if provided
        eval_set = None
        if val_df is not None:
            X_val = self.prepare_features(val_df)
            y_val = val_df[target_col].values
            eval_set = [(X_val, y_val)]
        
        logger.info(f"Training {self.model_type} model on {len(X_train):,} samples...")
        
        # Fit model
        if self.model_type == 'lightgbm' and eval_set:
            self.model.fit(
                X_train, y_train,
                eval_set=eval_set,
                eval_metric='rmse',
            )
        elif self.model_type == 'xgboost' and eval_set:
            self.model.fit(
                X_train, y_train,
                eval_set=eval_set,
                verbose=False
            )
        else:
            self.model.fit(X_train, y_train)
        
        self.is_fitted = True
        
        # Calculate training metrics
        train_preds = self.model.predict(X_train)
        train_rmse = np.sqrt(np.mean((y_train - train_preds) ** 2))
        train_mae = np.mean(np.abs(y_train - train_preds))
        train_r2 = 1 - np.sum((y_train - train_preds) ** 2) / np.sum((y_train - np.mean(y_train)) ** 2)
        
        metrics = {
            'train_rmse': train_rmse,
            'train_mae': train_mae,
            'train_r2': train_r2,
            'n_samples': len(X_train),
            'n_features': len(self.feature_columns),
        }
        
        # Validation metrics
        if val_df is not None:
            val_preds = self.model.predict(X_val)
            metrics['val_rmse'] = np.sqrt(np.mean((y_val - val_preds) ** 2))
            metrics['val_mae'] = np.mean(np.abs(y_val - val_preds))
            metrics['val_r2'] = 1 - np.sum((y_val - val_preds) ** 2) / np.sum((y_val - np.mean(y_val)) ** 2)
        
        logger.info(f"Training complete. RMSE: {train_rmse:.4f}, R²: {train_r2:.4f}")
        
        return metrics
    
    def predict(self, df: pd.DataFrame) -> np.ndarray:
        """
        Predict EPA for plays.
        
        Args:
            df: DataFrame with play features
            
        Returns:
            Array of EPA predictions
        """
        if not self.is_fitted:
            raise ValueError("Model must be fitted before prediction")
        
        X = self.prepare_features(df)
        return self.model.predict(X)
    
    def predict_situation(self, 
                         down: int,
                         ydstogo: int,
                         yardline_100: int,
                         quarter: int = 2,
                         score_differential: int = 0,
                         shotgun: int = 0,
                         no_huddle: int = 0,
                         half_seconds_remaining: int = 900,
                         is_home: int = 1) -> float:
        """
        Predict EPA for a single situation.
        
        Args:
            down: Current down (1-4)
            ydstogo: Yards to first down
            yardline_100: Yards from opponent's end zone
            quarter: Quarter (1-5)
            score_differential: Offense score - Defense score
            shotgun: In shotgun formation (0/1)
            no_huddle: No-huddle (0/1)
            half_seconds_remaining: Seconds remaining in half
            is_home: Is home team (0/1)
            
        Returns:
            Predicted EPA
        """
        situation = pd.DataFrame([{
            'down': down,
            'ydstogo': ydstogo,
            'yardline_100': yardline_100,
            'quarter': quarter,
            'score_differential': score_differential,
            'shotgun': shotgun,
            'no_huddle': no_huddle,
            'half_seconds_remaining': half_seconds_remaining,
            'is_home': is_home,
        }])
        
        return self.predict(situation)[0]
    
    def compare_play_types(self,
                          down: int,
                          ydstogo: int,
                          yardline_100: int,
                          quarter: int = 2,
                          score_differential: int = 0,
                          half_seconds_remaining: int = 900,
                          is_home: int = 1,
                          team_pass_adjustment: float = 0.0,
                          team_run_adjustment: float = 0.0,
                          defenders_in_box: Optional[int] = None) -> Dict:
        """
        Compare expected EPA for run vs pass in a situation.
        
        Args:
            down, ydstogo, etc.: Situation parameters
            team_pass_adjustment: Team's EPA/play vs league avg for passing
            team_run_adjustment: Team's EPA/play vs league avg for rushing
            defenders_in_box: Number of defenders in the box (6-8 typical)
                             - 6 or fewer: favorable for run
                             - 7: neutral
                             - 8+: stacked box, favorable for pass
            
        Returns:
            Dictionary with comparison results including defensive insights
        """
        # Create base situation
        base = {
            'down': down,
            'ydstogo': ydstogo,
            'yardline_100': yardline_100,
            'quarter': quarter,
            'score_differential': score_differential,
            'half_seconds_remaining': half_seconds_remaining,
            'is_home': is_home,
        }
        
        # Add defenders_in_box if provided and model supports it
        if defenders_in_box is not None and 'defenders_in_box' in self.feature_columns:
            base['defenders_in_box'] = defenders_in_box
        
        # Predict for pass (typically from shotgun)
        pass_situation = pd.DataFrame([{**base, 'shotgun': 1, 'no_huddle': 0}])
        pass_epa = self.predict(pass_situation)[0] + team_pass_adjustment
        
        # Predict for run (typically not shotgun)
        run_situation = pd.DataFrame([{**base, 'shotgun': 0, 'no_huddle': 0}])
        run_epa = self.predict(run_situation)[0] + team_run_adjustment
        
        # Apply defensive adjustment based on box count
        defensive_insight = None
        box_adjustment = 0.0
        
        if defenders_in_box is not None:
            if defenders_in_box <= 6:
                # Light box - favorable for run
                box_adjustment = 0.03  # Boost run EPA
                run_epa += box_adjustment
                defensive_insight = f"Light box ({defenders_in_box} defenders) favors the run"
            elif defenders_in_box >= 8:
                # Stacked box - favorable for pass
                box_adjustment = 0.04  # Boost pass EPA
                pass_epa += box_adjustment
                defensive_insight = f"Stacked box ({defenders_in_box} defenders) favors the pass"
            else:
                defensive_insight = f"Standard box ({defenders_in_box} defenders)"
        
        # Determine recommendation
        epa_diff = pass_epa - run_epa
        
        if abs(epa_diff) < 0.02:
            recommendation = 'neutral'
            confidence = 0.5
        elif epa_diff > 0:
            recommendation = 'pass'
            confidence = min(0.5 + epa_diff * 2, 0.95)
        else:
            recommendation = 'run'
            confidence = min(0.5 + abs(epa_diff) * 2, 0.95)
        
        result = {
            'situation': {
                'down': down,
                'ydstogo': ydstogo,
                'yardline_100': yardline_100,
                'quarter': quarter,
                'score_differential': score_differential,
            },
            'pass_epa': round(pass_epa, 4),
            'run_epa': round(run_epa, 4),
            'epa_difference': round(epa_diff, 4),
            'recommendation': recommendation,
            'confidence': round(confidence, 3),
        }
        
        # Add defensive context if available
        if defenders_in_box is not None:
            result['situation']['defenders_in_box'] = defenders_in_box
            result['defensive_insight'] = defensive_insight
            result['box_adjustment'] = round(box_adjustment, 4)
        
        return result
    
    def get_feature_importance(self) -> pd.DataFrame:
        """Get feature importance from the model."""
        if not self.is_fitted:
            raise ValueError("Model must be fitted first")
        
        importance = self.model.feature_importances_
        
        return pd.DataFrame({
            'feature': self.feature_columns,
            'importance': importance
        }).sort_values('importance', ascending=False)
    
    def save(self, filepath: str):
        """Save model to disk."""
        import joblib
        
        model_data = {
            'model': self.model,
            'model_type': self.model_type,
            'feature_columns': self.feature_columns,
            'is_fitted': self.is_fitted,
        }
        
        joblib.dump(model_data, filepath)
        logger.info(f"Model saved to {filepath}")
    
    @classmethod
    def load(cls, filepath: str) -> 'EPAPredictor':
        """Load model from disk."""
        import joblib
        
        model_data = joblib.load(filepath)
        
        predictor = cls(model_type=model_data['model_type'])
        predictor.model = model_data['model']
        predictor.feature_columns = model_data['feature_columns']
        predictor.is_fitted = model_data['is_fitted']
        
        logger.info(f"Model loaded from {filepath}")
        return predictor


def load_training_data(conn, train_seasons: List[int], 
                       val_seasons: Optional[List[int]] = None) -> Tuple[pd.DataFrame, Optional[pd.DataFrame]]:
    """
    Load training data from database.
    
    Args:
        conn: Database connection
        train_seasons: List of seasons for training
        val_seasons: Optional list of seasons for validation
        
    Returns:
        Tuple of (train_df, val_df)
    """
    base_query = """
        SELECT 
            down, ydstogo, yardline_100, quarter,
            score_differential, shotgun, no_huddle,
            time_remaining_half as half_seconds_remaining,
            CASE WHEN posteam = home_team THEN 1 ELSE 0 END as is_home,
            epa, play_type
        FROM plays
        WHERE play_type IN ('pass', 'run')
          AND down IS NOT NULL
          AND epa IS NOT NULL
          AND season IN ({seasons})
    """
    
    # Load training data
    train_query = base_query.format(seasons=','.join(map(str, train_seasons)))
    train_df = pd.read_sql(train_query, conn)
    
    # Load validation data if specified
    val_df = None
    if val_seasons:
        val_query = base_query.format(seasons=','.join(map(str, val_seasons)))
        val_df = pd.read_sql(val_query, conn)
    
    return train_df, val_df
