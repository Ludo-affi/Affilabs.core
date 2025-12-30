"""Train convergence feasibility predictor.

Predicts if calibration will succeed based on initial conditions.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score
import joblib


def prepare_features(iterations_df: pd.DataFrame, runs_df: pd.DataFrame, device_features_df: pd.DataFrame = None) -> pd.DataFrame:
    """Prepare features for convergence prediction.

    Uses initial conditions (first 2 iterations) to predict final success.
    Optionally merges device history features for device-specific predictions.

    Args:
        iterations_df: Iteration data
        runs_df: Calibration runs data
        device_features_df: Optional device history features (from device_history.py)
    """
    features = []

    for _, run in runs_df.iterrows():
        log_file = run['log_file']

        # Get initial iterations (S-mode, iter 1-2)
        initial_iters = iterations_df[
            (iterations_df['log_file'] == log_file) &
            (iterations_df['polarization'] == 's') &
            (iterations_df['iteration'] <= 2)
        ]

        if len(initial_iters) == 0:
            continue

        # Feature engineering from initial state
        feature_dict = {
            'log_file': log_file,

            # Initial integration time
            'initial_integration_ms': initial_iters['integration_ms'].iloc[0],

            # Target signal level
            'target_percent': 0.85,  # Assumed

            # Initial LED distribution
            'avg_initial_led': initial_iters[initial_iters['iteration'] == 1]['led'].mean(),
            'max_initial_led': initial_iters[initial_iters['iteration'] == 1]['led'].max(),
            'min_initial_led': initial_iters[initial_iters['iteration'] == 1]['led'].min(),
            'led_imbalance': initial_iters[initial_iters['iteration'] == 1]['led'].std(),

            # Initial signal levels
            'avg_signal_fraction': initial_iters['fraction_of_target'].mean(),
            'min_signal_fraction': initial_iters['fraction_of_target'].min(),
            'max_signal_fraction': initial_iters['fraction_of_target'].max(),
            'signal_variance': initial_iters['fraction_of_target'].std(),

            # Early saturation indicators
            'early_saturation': int(any(initial_iters['saturated'])),
            'total_sat_pixels': initial_iters['saturation_pixels'].sum(),

            # Channel balance
            'num_channels': initial_iters['total_channels'].iloc[0],

            # Temporal features (from full run)
            'led_convergence_rate': run['led_convergence_rate_s'] if pd.notna(run['led_convergence_rate_s']) else 0.0,
            'signal_stability': run['signal_stability_s'] if pd.notna(run['signal_stability_s']) else 0.0,
            'oscillation_detected': int(run['oscillation_detected_s']),
            'phase1_iterations': run['phase1_iterations'],
            'phase2_iterations': run['phase2_iterations'],
            'phase3_iterations': run['phase3_iterations'],

            # Device-specific features (if available)
            'detector_serial': run['detector_serial'] if 'detector_serial' in run and pd.notna(run['detector_serial']) else 65535,

            # Target label
            'success': int(run['converged_s']),
        }

        features.append(feature_dict)

    features_df = pd.DataFrame(features)

    # Merge device history features if available
    if device_features_df is not None and not device_features_df.empty:
        print(f"  Merging device history features for {len(device_features_df)} devices...")
        features_df = features_df.merge(
            device_features_df,
            on='detector_serial',
            how='left'
        )

        # Fill missing device features with defaults (new devices)
        device_cols = [col for col in device_features_df.columns if col != 'detector_serial']
        for col in device_cols:
            if col in features_df.columns:
                # Only use numeric features - skip categorical ones
                if features_df[col].dtype in ['float64', 'int64']:
                    features_df[col] = features_df[col].fillna(features_df[col].median())
                else:
                    # Drop non-numeric columns (can't use in RandomForest directly)
                    features_df = features_df.drop(columns=[col])

    return features_df


def train_model(features_df: pd.DataFrame, use_device_features: bool = True) -> RandomForestClassifier:
    """Train convergence predictor.

    Args:
        features_df: Feature dataframe
        use_device_features: Whether to include device history features
    """

    # Base features
    feature_cols = [
        'initial_integration_ms',
        'target_percent',
        'avg_initial_led',
        'max_initial_led',
        'min_initial_led',
        'led_imbalance',
        'avg_signal_fraction',
        'min_signal_fraction',
        'max_signal_fraction',
        'signal_variance',
        'early_saturation',
        'total_sat_pixels',
        'num_channels',
        # New temporal features
        'led_convergence_rate',
        'signal_stability',
        'oscillation_detected',
        'phase1_iterations',
        'phase2_iterations',
        'phase3_iterations',
    ]

    # Add device history features if available
    if use_device_features:
        device_feature_cols = [
            'device_total_calibrations',
            'device_success_rate',
            'device_avg_s_iterations',
            'device_avg_p_iterations',
            'device_avg_total_iterations',
            'device_std_s_iterations',
            'device_avg_fwhm',
            'device_std_fwhm',
            'device_avg_snr',
            'device_avg_warnings',
            'device_avg_final_led_s',
            'device_avg_final_led_p',
            'device_avg_convergence_rate',
            'device_avg_stability',
            'device_oscillation_frequency',
            'device_days_since_last_cal',
            'device_calibration_frequency_days',
        ]

        # Only add features that exist in dataframe
        available_device_features = [col for col in device_feature_cols if col in features_df.columns]
        if available_device_features:
            feature_cols.extend(available_device_features)
            print(f"Using {len(available_device_features)} device history features")

    X = features_df[feature_cols].values
    y = features_df['success'].values

    print(f"Training data: {X.shape[0]} samples")
    print(f"Success rate: {y.mean():.1%} ({y.sum()}/{len(y)})")

    # Train-test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # Train Random Forest
    model = RandomForestClassifier(
        n_estimators=150,
        max_depth=12,
        min_samples_split=8,
        min_samples_leaf=3,
        random_state=42,
        class_weight='balanced',
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
    y_pred_proba = model.predict_proba(X_test)[:, 1]

    print(f"\n=== Test Set Classification Report ===")
    print(classification_report(y_test, y_pred, target_names=['FAIL', 'SUCCESS']))

    print(f"\n=== Confusion Matrix ===")
    cm = confusion_matrix(y_test, y_pred)
    print(cm)
    print(f"  True Negatives: {cm[0,0]}")
    print(f"  False Positives: {cm[0,1]} (predicted success but failed)")
    print(f"  False Negatives: {cm[1,0]} (predicted fail but succeeded)")
    print(f"  True Positives: {cm[1,1]}")

    # ROC-AUC
    auc = roc_auc_score(y_test, y_pred_proba)
    print(f"\nROC-AUC Score: {auc:.3f}")

    # Feature importance
    print(f"\n=== Feature Importance ===")
    for feat, imp in sorted(zip(feature_cols, model.feature_importances_),
                           key=lambda x: x[1], reverse=True):
        print(f"  {feat:35s}: {imp:.4f}")

    return model


def main():
    """Train and save convergence predictor."""
    data_dir = Path("tools/ml_training/data")

    # Load parsed data
    iterations_df = pd.read_csv(data_dir / "iterations.csv")
    runs_df = pd.read_csv(data_dir / "calibration_runs.csv")

    print(f"Loaded {len(iterations_df)} iteration records from {len(runs_df)} runs")

    # Load device history features if available
    device_features_path = data_dir / "device_features.csv"
    if device_features_path.exists():
        device_features_df = pd.read_csv(device_features_path)
        print(f"Loaded device history for {len(device_features_df)} devices")
    else:
        device_features_df = None
        print("No device history available (run device_history.py to generate)")

    # Prepare features
    print("\nPreparing features from initial conditions...")
    features_df = prepare_features(iterations_df, runs_df, device_features_df)

    print(f"Created {len(features_df)} training samples")

    # Train model with device features if available
    use_device_features = device_features_df is not None
    print(f"\nTraining convergence predictor (device features: {use_device_features})...")
    model = train_model(features_df, use_device_features=use_device_features)

    # Save model
    output_dir = Path("tools/ml_training/models")
    output_dir.mkdir(parents=True, exist_ok=True)

    model_path = output_dir / "convergence_predictor.joblib"
    joblib.dump(model, model_path)

    print(f"\n✓ Model saved to {model_path}")
    print(f"  Use in ConvergenceEngine(..., convergence_predictor_path='{model_path}')")


if __name__ == "__main__":
    main()
