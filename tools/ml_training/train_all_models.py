"""Master script to train all ML models from calibration logs.

Runs the complete pipeline:
1. Parse calibration logs
2. Build device history database
3. Export device features
4. Train sensitivity classifier
5. Train LED intensity predictor
6. Train convergence predictor (with device features)
"""

print("SCRIPT START - Imports beginning...")
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tools.ml_training.parse_calibration_logs import CalibrationLogParser
from tools.ml_training.train_sensitivity_classifier import prepare_features as prep_sensitivity, train_model as train_sensitivity
from tools.ml_training.train_led_predictor import prepare_features as prep_led, train_model as train_led
from tools.ml_training.train_convergence_predictor import prepare_features as prep_convergence, train_model as train_convergence
from tools.ml_training.device_history import DeviceHistoryDatabase

import joblib


def main():
    """Run complete ML training pipeline."""
    print("=" * 80)
    print("ML TRAINING PIPELINE FOR CALIBRATION CONVERGENCE")
    print("=" * 80)

    # Step 1: Parse logs
    print("\n[1/6] Parsing calibration logs...")
    print("-" * 80)

    # Navigate to root directory (2 levels up from tools/ml_training/)
    root_dir = Path(__file__).parent.parent.parent
    logs_dir = root_dir / "logs"

    if not logs_dir.exists():
        print(f"ERROR: Logs directory not found: {logs_dir}")
        print(f"Looking in: {logs_dir.absolute()}")
        sys.exit(1)

    parser = CalibrationLogParser(logs_dir)
    # Parse recent 500 logs for better ML training coverage
    iterations_df, runs_df = parser.parse_all_logs(max_logs=500)

    # Save parsed data
    data_dir = Path("tools/ml_training/data")
    data_dir.mkdir(parents=True, exist_ok=True)

    iterations_df.to_csv(data_dir / "iterations.csv", index=False)
    runs_df.to_csv(data_dir / "calibration_runs.csv", index=False)

    print(f"\n[OK] Parsed {len(runs_df)} calibration runs with {len(iterations_df)} iteration records")
    print(f"  Saved to {data_dir}/")

    # Step 2: Build device history database
    print("\n[2/6] Building device history database...")
    print("-" * 80)

    db = DeviceHistoryDatabase()
    db.import_from_csv(data_dir / "calibration_runs.csv")

    print(f"\n[OK] Device history database created at {db.db_path}")

    # Step 3: Export device features for ML
    print("\n[3/6] Exporting device features...")
    print("-" * 80)

    device_features_path = data_dir / "device_features.csv"
    device_features_df = db.export_device_features_for_ml(device_features_path, lookback_days=90)

    print(f"\n[OK] Device features exported to {device_features_path}")

    # Step 4: Train sensitivity classifier
    print("\n[4/6] Training Sensitivity Classifier...")
    print("-" * 80)

    sensitivity_features = prep_sensitivity(iterations_df, runs_df)
    sensitivity_model = train_sensitivity(sensitivity_features)

    # Save to development location (for testing/improvement)
    # Production models are in affilabs/convergence/models/ (updated during releases)
    model_dir = Path("tools/ml_training/models")
    model_dir.mkdir(parents=True, exist_ok=True)

    sensitivity_path = model_dir / "sensitivity_classifier.joblib"
    joblib.dump(sensitivity_model, sensitivity_path)
    print(f"\n[OK] Sensitivity classifier saved to {sensitivity_path}")

    # Step 5: Train LED predictor
    print("\n[5/6] Training LED Intensity Predictor...")
    print("-" * 80)

    led_features = prep_led(iterations_df, runs_df)
    print(f"LED features shape: {led_features.shape}")
    print(f"LED features columns: {led_features.columns.tolist()}")

    if len(led_features) == 0:
        print("WARNING: No LED features generated - skipping LED predictor training")
        led_model = None
    else:
        led_model = train_led(led_features)

    led_path = model_dir / "led_predictor.joblib"
    joblib.dump(led_model, led_path)
    print(f"\n[OK] LED predictor saved to {led_path}")

    # Step 6: Train convergence predictor with device features
    print("\n[6/6] Training Convergence Predictor (with device history)...")
    print("-" * 80)

    convergence_features = prep_convergence(iterations_df, runs_df, device_features_df)
    convergence_model = train_convergence(convergence_features, use_device_features=True)

    convergence_path = model_dir / "convergence_predictor.joblib"
    joblib.dump(convergence_model, convergence_path)
    print(f"\n[OK] Convergence predictor saved to {convergence_path}")

    # Summary
    print("\n" + "=" * 80)
    print("TRAINING COMPLETE!")
    print("=" * 80)
    print(f"\nModels saved to: {model_dir.absolute()}/")
    print("  1. sensitivity_classifier.joblib")
    print("  2. led_predictor.joblib")
    print("  3. convergence_predictor.joblib")

    print("\nTo enable ML in calibration, update led_convergence.py:")
    print("  engine = ConvergenceEngine(")
    print("      spectrometer=spect,")
    print("      roi_extractor=roi,")
    print("      scheduler=ThreadScheduler(1),")
    print("      logger=logger,")
    print(f"      sensitivity_model_path='{sensitivity_path.absolute()}',")
    print(f"      led_predictor_path='{led_path.absolute()}',")
    print(f"      convergence_predictor_path='{convergence_path.absolute()}',")
    print("  )")

    print("\n[OK] Ready to use ML-powered calibration!")


if __name__ == "__main__":
    main()
