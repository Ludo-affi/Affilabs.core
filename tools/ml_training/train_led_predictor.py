"""Train LED intensity predictor.

Predicts optimal LED intensity for a channel given:
- Target signal counts
- Integration time
- Device sensitivity
"""

import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import joblib


def prepare_features(iterations_df: pd.DataFrame, runs_df: pd.DataFrame) -> pd.DataFrame:
    """Prepare features for LED prediction.

    Uses converged iterations (last iteration of successful runs).
    """
    # Get successful calibration runs
    successful_runs = runs_df[runs_df['converged_s'] == True]['log_file'].unique()

    # Filter to last iterations of S-mode in successful runs
    features = []

    for log_file in successful_runs:
        run_iters = iterations_df[
            (iterations_df['log_file'] == log_file) &
            (iterations_df['polarization'] == 's')
        ]

        if len(run_iters) == 0:
            continue

        # Get last iteration (converged state)
        last_iter = run_iters['iteration'].max()
        final_iters = run_iters[run_iters['iteration'] == last_iter]

        run_info = runs_df[runs_df['log_file'] == log_file].iloc[0]
        sensitivity = 1 if run_info['sensitivity_label'] == 'HIGH' else 0

        # Create one sample per channel
        for _, row in final_iters.iterrows():
            feature_dict = {
                'log_file': log_file,
                'channel': row['channel'],

                # Input features
                'channel_encoding': ord(row['channel']) - ord('a'),  # 0-3
                'target_counts': row['target_counts'],
                'integration_ms': row['integration_ms'],
                'sensitivity': sensitivity,

                # Target variable
                'led_intensity': row['led'],

                # Additional context (for analysis)
                'final_counts': row['counts'],
                'fraction_of_target': row['fraction_of_target'],
            }

            features.append(feature_dict)

    return pd.DataFrame(features)


def train_model(features_df: pd.DataFrame) -> GradientBoostingRegressor:
    """Train LED intensity predictor."""

    # Prepare X and y
    feature_cols = [
        'channel_encoding',
        'target_counts',
        'integration_ms',
        'sensitivity',
    ]

    X = features_df[feature_cols].values
    y = features_df['led_intensity'].values

    print(f"Training data: {X.shape[0]} samples")
    print(f"LED range: {y.min():.0f} - {y.max():.0f}")
    print(f"LED mean: {y.mean():.1f} +/- {y.std():.1f}")

    # Train-test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # Train Gradient Boosting Regressor
    model = GradientBoostingRegressor(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.05,
        min_samples_split=10,
        min_samples_leaf=4,
        random_state=42,
        loss='huber',  # Robust to outliers
    )

    model.fit(X_train, y_train)

    # Evaluate
    y_train_pred = model.predict(X_train)
    y_test_pred = model.predict(X_test)

    print(f"\n=== Training Results ===")
    print(f"Training MAE: {mean_absolute_error(y_train, y_train_pred):.2f} LED units")
    print(f"Training RMSE: {np.sqrt(mean_squared_error(y_train, y_train_pred)):.2f} LED units")
    print(f"Training R²: {r2_score(y_train, y_train_pred):.3f}")

    print(f"\n=== Test Results ===")
    print(f"Test MAE: {mean_absolute_error(y_test, y_test_pred):.2f} LED units")
    print(f"Test RMSE: {np.sqrt(mean_squared_error(y_test, y_test_pred)):.2f} LED units")
    print(f"Test R²: {r2_score(y_test, y_test_pred):.3f}")

    # Cross-validation (adjust folds for small datasets)
    n_splits = min(5, len(X))
    if n_splits >= 2:
        cv_scores = -cross_val_score(model, X, y, cv=n_splits, scoring='neg_mean_absolute_error')
        print(f"\nCross-validation MAE: {cv_scores.mean():.2f} (+/- {cv_scores.std():.2f}) LED units (cv={n_splits})")
    else:
        print(f"\nCross-validation: Skipped (insufficient samples: {len(X)})")

    # Feature importance
    print(f"\n=== Feature Importance ===")
    for feat, imp in sorted(zip(feature_cols, model.feature_importances_),
                           key=lambda x: x[1], reverse=True):
        print(f"  {feat:30s}: {imp:.4f}")

    # Error analysis
    print(f"\n=== Error Analysis (Test Set) ===")
    errors = y_test_pred - y_test
    print(f"Mean error: {errors.mean():.2f} LED units")
    print(f"Median error: {np.median(errors):.2f} LED units")
    print(f"95th percentile |error|: {np.percentile(np.abs(errors), 95):.2f} LED units")

    # Check predictions stay in valid range
    print(f"\n=== Prediction Range ===")
    print(f"Min predicted LED: {y_test_pred.min():.1f}")
    print(f"Max predicted LED: {y_test_pred.max():.1f}")
    out_of_range = np.sum((y_test_pred < 10) | (y_test_pred > 255))
    print(f"Predictions out of range [10, 255]: {out_of_range}/{len(y_test_pred)}")

    return model


def main():
    """Train and save LED predictor."""
    data_dir = Path("tools/ml_training/data")

    # Load parsed data
    iterations_df = pd.read_csv(data_dir / "iterations.csv")
    runs_df = pd.read_csv(data_dir / "calibration_runs.csv")

    print(f"Loaded {len(iterations_df)} iteration records from {len(runs_df)} runs")

    # Prepare features
    print("\nPreparing features from converged iterations...")
    features_df = prepare_features(iterations_df, runs_df)

    print(f"Created {len(features_df)} training samples")

    # Train model
    print("\nTraining LED intensity predictor...")
    model = train_model(features_df)

    # Save model
    output_dir = Path("tools/ml_training/models")
    output_dir.mkdir(parents=True, exist_ok=True)

    model_path = output_dir / "led_predictor.joblib"
    joblib.dump(model, model_path)

    print(f"\n✓ Model saved to {model_path}")
    print(f"  Use in ConvergenceEngine(..., led_predictor_path='{model_path}')")


if __name__ == "__main__":
    main()
