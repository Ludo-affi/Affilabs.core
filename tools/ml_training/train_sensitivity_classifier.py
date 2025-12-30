"""Train sensitivity classifier to predict HIGH vs BASELINE devices.

Predicts if a device will exhibit high sensitivity (early saturation risk)
from early iteration data.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix
import joblib


def prepare_features(iterations_df: pd.DataFrame, runs_df: pd.DataFrame) -> pd.DataFrame:
    """Prepare features for sensitivity classification.

    Uses data from first 3 iterations to predict device sensitivity.
    """
    # Filter to early iterations (1-3) of S-mode only
    early_iters = iterations_df[
        (iterations_df['iteration'] <= 3) &
        (iterations_df['polarization'] == 's')
    ].copy()

    # Aggregate features per calibration run
    features = []

    for log_file in early_iters['log_file'].unique():
        run_iters = early_iters[early_iters['log_file'] == log_file]
        run_info = runs_df[runs_df['log_file'] == log_file]

        if len(run_info) == 0:
            continue

        run_info = run_info.iloc[0]

        # Feature engineering
        feature_dict = {
            'log_file': log_file,

            # Integration time progression
            'integration_ms': run_iters['integration_ms'].mean(),

            # Number of channels
            'num_channels': run_iters['total_channels'].iloc[0],

            # Saturation indicators
            'num_saturating': run_iters[run_iters['saturated']]['channel'].nunique(),
            'total_saturated_pixels': run_iters['saturation_pixels'].sum(),

            # Signal levels
            'avg_signal_fraction_of_target': run_iters['fraction_of_target'].mean(),
            'max_signal_fraction': run_iters['fraction_of_target'].max(),
            'min_signal_fraction': run_iters['fraction_of_target'].min(),
            'signal_imbalance': run_iters['fraction_of_target'].std(),

            # LED levels
            'avg_led': run_iters['led'].mean(),
            'max_led': run_iters['led'].max(),
            'min_led': run_iters['led'].min(),

            # Target label
            'sensitivity_label': run_info['sensitivity_label'],
        }

        features.append(feature_dict)

    return pd.DataFrame(features)


def train_model(features_df: pd.DataFrame) -> RandomForestClassifier:
    """Train sensitivity classifier."""

    # Prepare X and y
    feature_cols = [
        'integration_ms',
        'num_channels',
        'num_saturating',
        'total_saturated_pixels',
        'avg_signal_fraction_of_target',
        'max_signal_fraction',
        'min_signal_fraction',
        'signal_imbalance',
        'avg_led',
        'max_led',
        'min_led',
    ]

    X = features_df[feature_cols].values
    y = (features_df['sensitivity_label'] == 'HIGH').astype(int).values

    print(f"Training data: {X.shape[0]} samples")
    print(f"Class distribution: {np.bincount(y)}")

    # Train-test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # Train Random Forest
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=42,
        class_weight='balanced',  # Handle class imbalance
    )

    model.fit(X_train, y_train)

    # Evaluate
    print(f"\n=== Training Results ===")
    print(f"Training accuracy: {model.score(X_train, y_train):.3f}")
    print(f"Test accuracy: {model.score(X_test, y_test):.3f}")

    # Cross-validation
    cv_scores = cross_val_score(model, X, y, cv=5)
    print(f"Cross-validation accuracy: {cv_scores.mean():.3f} (+/- {cv_scores.std():.3f})")

    # Classification report
    y_pred = model.predict(X_test)
    print(f"\n=== Test Set Classification Report ===")
    print(classification_report(y_test, y_pred, target_names=['BASELINE', 'HIGH']))

    print(f"\n=== Confusion Matrix ===")
    print(confusion_matrix(y_test, y_pred))

    # Feature importance
    print(f"\n=== Feature Importance ===")
    for feat, imp in sorted(zip(feature_cols, model.feature_importances_),
                           key=lambda x: x[1], reverse=True):
        print(f"  {feat:40s}: {imp:.4f}")

    return model


def main():
    """Train and save sensitivity classifier."""
    data_dir = Path("tools/ml_training/data")

    # Load parsed data
    iterations_df = pd.read_csv(data_dir / "iterations.csv")
    runs_df = pd.read_csv(data_dir / "calibration_runs.csv")

    print(f"Loaded {len(iterations_df)} iteration records from {len(runs_df)} runs")

    # Prepare features
    print("\nPreparing features...")
    features_df = prepare_features(iterations_df, runs_df)

    print(f"Created {len(features_df)} training samples")

    # Train model
    print("\nTraining sensitivity classifier...")
    model = train_model(features_df)

    # Save model
    output_dir = Path("tools/ml_training/models")
    output_dir.mkdir(parents=True, exist_ok=True)

    model_path = output_dir / "sensitivity_classifier.joblib"
    joblib.dump(model, model_path)

    print(f"\n✓ Model saved to {model_path}")
    print(f"  Use in ConvergenceEngine(..., sensitivity_model_path='{model_path}')")


if __name__ == "__main__":
    main()
