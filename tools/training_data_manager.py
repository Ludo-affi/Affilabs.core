"""Training Data Manager for SPR Instrument Characterization

Manages hierarchical training data structure:
- Device level: Each instrument instance (unique LED/fiber/detector set)
- Detector level: S-signal (instrument-only) and P-signal (sensor-dependent)
- Sensor quality levels: Reference to various chip qualities per detector

Directory Structure:
training_data/
├── device_001/
│   ├── device_info.json (LED model, serial numbers, installation date)
│   ├── detector_A/
│   │   ├── s_signal/
│   │   │   ├── baseline/          # Pure instrument characterization
│   │   │   │   ├── measurement_001.csv
│   │   │   │   ├── measurement_001.json (analysis)
│   │   │   │   └── metadata.json
│   │   │   ├── thermal/            # Warm-up studies
│   │   │   └── stability/          # Long-term drift
│   │   ├── p_signal/
│   │   │   ├── sensor_excellent/   # Reference quality chips
│   │   │   │   ├── chip_batch_A/
│   │   │   │   │   ├── measurement_001.csv
│   │   │   │   │   ├── measurement_001.json
│   │   │   │   │   └── chip_metadata.json
│   │   │   ├── sensor_good/
│   │   │   ├── sensor_acceptable/
│   │   │   ├── sensor_poor/
│   │   │   └── sensor_defective/
│   │   └── detector_metadata.json
│   ├── detector_B/
│   ├── detector_C/
│   └── detector_D/
└── device_002/
    └── ...

Usage:
    from training_data_manager import TrainingDataManager

    # Initialize for your device
    tdm = TrainingDataManager(device_id="device_001")

    # Save S-signal measurement (pure instrument)
    tdm.save_s_signal(
        detector="A",
        category="baseline",
        csv_path="measurement.csv",
        metadata={"warm_up_min": 15, "ambient_temp": 23.5}
    )

    # Save P-signal measurement (with sensor)
    tdm.save_p_signal(
        detector="A",
        sensor_quality="excellent",
        chip_batch="ABC-2025-10",
        csv_path="measurement.csv",
        metadata={
            "chip_age_days": 5,
            "storage_temp": 4.0,
            "ri_medium": 1.3333,
            "coating_type": "gold_50nm"
        }
    )

    # Query training data
    s_baselines = tdm.get_s_signal_data(detector="A", category="baseline")
    excellent_sensors = tdm.get_p_signal_data(detector="A", quality="excellent")

    # Get device statistics
    stats = tdm.get_device_statistics()
"""

import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


class TrainingDataManager:
    """Manages hierarchical training data for SPR instruments."""

    # Standard sensor quality categories
    SENSOR_QUALITIES = [
        "excellent",  # Reference quality, fresh, perfect storage
        "good",  # Normal quality, proper storage
        "acceptable",  # Older but functional
        "poor",  # Degraded, storage issues, nearing end-of-life
        "defective",  # Known defects, contamination, for failure mode analysis
    ]

    # S-signal categories (instrument characterization)
    S_SIGNAL_CATEGORIES = [
        "baseline",  # Standard measurements for instrument reference
        "thermal",  # Warm-up and thermal stability studies
        "stability",  # Long-term drift characterization
        "led_testing",  # LED delay optimization, spectral analysis
        "noise_floor",  # Dark measurements, detector noise
    ]

    def __init__(self, device_id: str, base_path: Path | None = None):
        """Initialize training data manager for a specific device.

        Args:
            device_id: Unique identifier for this instrument (e.g., "device_001", "lab_A_unit_1")
            base_path: Root directory for training data (default: ./training_data)

        """
        self.device_id = device_id
        self.base_path = base_path or Path("training_data")
        self.device_path = self.base_path / device_id

        # Create directory structure
        self._initialize_structure()

    def _initialize_structure(self):
        """Create the hierarchical directory structure."""
        self.device_path.mkdir(parents=True, exist_ok=True)

        # Create detector directories (A, B, C, D)
        for detector in ["A", "B", "C", "D"]:
            detector_path = self.device_path / f"detector_{detector}"
            detector_path.mkdir(exist_ok=True)

            # S-signal subdirectories
            s_signal_path = detector_path / "s_signal"
            for category in self.S_SIGNAL_CATEGORIES:
                (s_signal_path / category).mkdir(parents=True, exist_ok=True)

            # P-signal subdirectories
            p_signal_path = detector_path / "p_signal"
            for quality in self.SENSOR_QUALITIES:
                (p_signal_path / quality).mkdir(parents=True, exist_ok=True)

        # Create device info if doesn't exist
        device_info_path = self.device_path / "device_info.json"
        if not device_info_path.exists():
            self._create_device_info()

    def _create_device_info(self):
        """Create initial device information file."""
        device_info = {
            "device_id": self.device_id,
            "created_date": datetime.now().isoformat(),
            "hardware": {
                "led_model": "UNKNOWN",
                "led_serial": "UNKNOWN",
                "fiber_type": "UNKNOWN",
                "detector_model": "UNKNOWN",
                "detector_serial": "UNKNOWN",
            },
            "installation": {
                "date": datetime.now().isoformat(),
                "location": "UNKNOWN",
                "operator": "UNKNOWN",
            },
            "calibration": {
                "last_calibration": None,
                "calibration_interval_days": 90,
            },
            "notes": [],
        }

        with open(self.device_path / "device_info.json", "w") as f:
            json.dump(device_info, f, indent=2)

        print(f"✓ Created device info for {self.device_id}")
        print(
            f"  → Update hardware details in: {self.device_path / 'device_info.json'}",
        )

    def update_device_info(self, **kwargs):
        """Update device information."""
        device_info_path = self.device_path / "device_info.json"
        with open(device_info_path) as f:
            device_info = json.load(f)

        # Update nested fields
        for key, value in kwargs.items():
            if "." in key:
                section, field = key.split(".", 1)
                if section in device_info:
                    device_info[section][field] = value
            else:
                device_info[key] = value

        device_info["last_modified"] = datetime.now().isoformat()

        with open(device_info_path, "w") as f:
            json.dump(device_info, f, indent=2)

    def save_s_signal(
        self,
        detector: str,
        category: str,
        csv_path: str,
        metadata: dict[str, Any] | None = None,
        auto_analyze: bool = True,
    ) -> Path:
        """Save S-signal measurement (pure instrument characterization).

        Args:
            detector: Channel ID ("A", "B", "C", or "D")
            category: S-signal category (baseline, thermal, stability, etc.)
            csv_path: Path to CSV file with measurement data
            metadata: Additional metadata (warm-up time, temperature, etc.)
            auto_analyze: Run spectral_quality_analyzer automatically

        Returns:
            Path to saved measurement directory

        """
        if category not in self.S_SIGNAL_CATEGORIES:
            raise ValueError(
                f"Invalid S-signal category: {category}. Must be one of {self.S_SIGNAL_CATEGORIES}",
            )

        # Generate measurement ID
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        measurement_id = f"s_signal_{timestamp}"

        # Create measurement directory
        save_dir = (
            self.device_path
            / f"detector_{detector}"
            / "s_signal"
            / category
            / measurement_id
        )
        save_dir.mkdir(parents=True, exist_ok=True)

        # Copy CSV file
        csv_dest = save_dir / "measurement.csv"
        shutil.copy2(csv_path, csv_dest)

        # Save metadata
        full_metadata = {
            "measurement_id": measurement_id,
            "timestamp": datetime.now().isoformat(),
            "device_id": self.device_id,
            "detector": detector,
            "signal_type": "S",
            "category": category,
            "csv_file": "measurement.csv",
            **(metadata or {}),
        }

        with open(save_dir / "metadata.json", "w") as f:
            json.dump(full_metadata, f, indent=2)

        # Run spectral quality analyzer
        if auto_analyze:
            self._run_analyzer(csv_dest, save_dir / "analysis.json")

        print(f"✓ Saved S-signal: {detector}/{category}/{measurement_id}")
        print(f"  → {save_dir}")

        return save_dir

    def save_p_signal(
        self,
        detector: str,
        sensor_quality: str,
        chip_batch: str,
        csv_path: str,
        metadata: dict[str, Any] | None = None,
        auto_analyze: bool = True,
    ) -> Path:
        """Save P-signal measurement (with sensor chip).

        Args:
            detector: Channel ID ("A", "B", "C", or "D")
            sensor_quality: Quality level (excellent, good, acceptable, poor, defective)
            chip_batch: Chip batch identifier (e.g., "ABC-2025-10")
            csv_path: Path to CSV file with measurement data
            metadata: Additional metadata (chip age, RI, coating, etc.)
            auto_analyze: Run spectral_quality_analyzer automatically

        Returns:
            Path to saved measurement directory

        """
        if sensor_quality not in self.SENSOR_QUALITIES:
            raise ValueError(
                f"Invalid sensor quality: {sensor_quality}. Must be one of {self.SENSOR_QUALITIES}",
            )

        # Generate measurement ID
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        measurement_id = f"p_signal_{timestamp}"

        # Create measurement directory (organized by chip batch)
        save_dir = (
            self.device_path
            / f"detector_{detector}"
            / "p_signal"
            / sensor_quality
            / chip_batch
            / measurement_id
        )
        save_dir.mkdir(parents=True, exist_ok=True)

        # Copy CSV file
        csv_dest = save_dir / "measurement.csv"
        shutil.copy2(csv_path, csv_dest)

        # Save metadata
        full_metadata = {
            "measurement_id": measurement_id,
            "timestamp": datetime.now().isoformat(),
            "device_id": self.device_id,
            "detector": detector,
            "signal_type": "P",
            "sensor_quality": sensor_quality,
            "chip_batch": chip_batch,
            "csv_file": "measurement.csv",
            "medium_ri": metadata.get("ri_medium", 1.3333) if metadata else 1.3333,
            **(metadata or {}),
        }

        with open(save_dir / "metadata.json", "w") as f:
            json.dump(full_metadata, f, indent=2)

        # Run spectral quality analyzer
        if auto_analyze:
            self._run_analyzer(csv_dest, save_dir / "analysis.json")

        print(
            f"✓ Saved P-signal: {detector}/{sensor_quality}/{chip_batch}/{measurement_id}",
        )
        print(f"  → {save_dir}")

        return save_dir

    def _run_analyzer(self, csv_path: Path, output_path: Path):
        """Run spectral_quality_analyzer on measurement."""
        try:
            analyzer_script = Path("spectral_quality_analyzer.py")
            if analyzer_script.exists():
                cmd = [
                    "python",
                    str(analyzer_script),
                    "analyze",
                    str(csv_path),
                    "-o",
                    str(output_path),
                ]
                subprocess.run(cmd, capture_output=True, check=True)
                print(f"  ✓ Analysis saved: {output_path.name}")
        except Exception as e:
            print(f"  ⚠️ Analysis failed: {e}")

    def get_s_signal_data(
        self,
        detector: str,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        """Query S-signal measurements.

        Args:
            detector: Channel ID
            category: Optional category filter

        Returns:
            List of measurement metadata dictionaries

        """
        results = []
        s_signal_path = self.device_path / f"detector_{detector}" / "s_signal"

        categories = [category] if category else self.S_SIGNAL_CATEGORIES

        for cat in categories:
            cat_path = s_signal_path / cat
            if not cat_path.exists():
                continue

            for meas_dir in cat_path.iterdir():
                if meas_dir.is_dir():
                    metadata_file = meas_dir / "metadata.json"
                    if metadata_file.exists():
                        with open(metadata_file) as f:
                            metadata = json.load(f)
                            metadata["measurement_path"] = str(meas_dir)
                            results.append(metadata)

        return sorted(results, key=lambda x: x["timestamp"], reverse=True)

    def get_p_signal_data(
        self,
        detector: str,
        quality: str | None = None,
        chip_batch: str | None = None,
    ) -> list[dict[str, Any]]:
        """Query P-signal measurements.

        Args:
            detector: Channel ID
            quality: Optional quality filter
            chip_batch: Optional batch filter

        Returns:
            List of measurement metadata dictionaries

        """
        results = []
        p_signal_path = self.device_path / f"detector_{detector}" / "p_signal"

        qualities = [quality] if quality else self.SENSOR_QUALITIES

        for qual in qualities:
            qual_path = p_signal_path / qual
            if not qual_path.exists():
                continue

            # Iterate through chip batches
            for batch_dir in qual_path.iterdir():
                if not batch_dir.is_dir():
                    continue

                # Filter by chip_batch if specified
                if chip_batch and batch_dir.name != chip_batch:
                    continue

                # Iterate through measurements in batch
                for meas_dir in batch_dir.iterdir():
                    if meas_dir.is_dir():
                        metadata_file = meas_dir / "metadata.json"
                        if metadata_file.exists():
                            with open(metadata_file) as f:
                                metadata = json.load(f)
                                metadata["measurement_path"] = str(meas_dir)
                                results.append(metadata)

        return sorted(results, key=lambda x: x["timestamp"], reverse=True)

    def get_device_statistics(self) -> dict[str, Any]:
        """Get statistics about collected training data."""
        stats = {
            "device_id": self.device_id,
            "total_measurements": 0,
            "by_detector": {},
            "by_signal_type": {"S": 0, "P": 0},
            "by_sensor_quality": {q: 0 for q in self.SENSOR_QUALITIES},
            "by_s_category": {c: 0 for c in self.S_SIGNAL_CATEGORIES},
            "date_range": {"earliest": None, "latest": None},
        }

        for detector in ["A", "B", "C", "D"]:
            s_data = self.get_s_signal_data(detector)
            p_data = self.get_p_signal_data(detector)

            stats["by_detector"][detector] = {
                "s_signal": len(s_data),
                "p_signal": len(p_data),
                "total": len(s_data) + len(p_data),
            }

            stats["by_signal_type"]["S"] += len(s_data)
            stats["by_signal_type"]["P"] += len(p_data)
            stats["total_measurements"] += len(s_data) + len(p_data)

            # Count by categories
            for meas in s_data:
                if meas.get("category"):
                    stats["by_s_category"][meas["category"]] += 1

            for meas in p_data:
                if meas.get("sensor_quality"):
                    stats["by_sensor_quality"][meas["sensor_quality"]] += 1

            # Track date range
            for meas in s_data + p_data:
                timestamp = meas.get("timestamp")
                if timestamp:
                    if (
                        stats["date_range"]["earliest"] is None
                        or timestamp < stats["date_range"]["earliest"]
                    ):
                        stats["date_range"]["earliest"] = timestamp
                    if (
                        stats["date_range"]["latest"] is None
                        or timestamp > stats["date_range"]["latest"]
                    ):
                        stats["date_range"]["latest"] = timestamp

        return stats

    def export_training_dataset(
        self,
        output_file: str,
        detector: str | None = None,
        signal_type: str | None = None,
    ):
        """Export training data as consolidated JSON for model training.

        Args:
            output_file: Path to output JSON file
            detector: Optional detector filter
            signal_type: Optional signal type filter ("S" or "P")

        """
        dataset = {
            "device_id": self.device_id,
            "export_date": datetime.now().isoformat(),
            "measurements": [],
        }

        detectors = [detector] if detector else ["A", "B", "C", "D"]

        for det in detectors:
            if signal_type in [None, "S"]:
                s_measurements = self.get_s_signal_data(det)
                for meas in s_measurements:
                    # Load analysis if exists
                    meas_path = Path(meas["measurement_path"])
                    analysis_file = meas_path / "analysis.json"
                    if analysis_file.exists():
                        with open(analysis_file) as f:
                            meas["analysis"] = json.load(f)
                    dataset["measurements"].append(meas)

            if signal_type in [None, "P"]:
                p_measurements = self.get_p_signal_data(det)
                for meas in p_measurements:
                    # Load analysis if exists
                    meas_path = Path(meas["measurement_path"])
                    analysis_file = meas_path / "analysis.json"
                    if analysis_file.exists():
                        with open(analysis_file) as f:
                            meas["analysis"] = json.load(f)
                    dataset["measurements"].append(meas)

        with open(output_file, "w") as f:
            json.dump(dataset, f, indent=2)

        print(
            f"✓ Exported {len(dataset['measurements'])} measurements to {output_file}",
        )


def main():
    """CLI interface for training data management."""
    import argparse

    parser = argparse.ArgumentParser(description="SPR Training Data Manager")
    parser.add_argument("--device", required=True, help="Device ID")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Init command
    subparsers.add_parser("init", help="Initialize training data structure")

    # Save S-signal
    save_s = subparsers.add_parser("save-s", help="Save S-signal measurement")
    save_s.add_argument("--detector", required=True, choices=["A", "B", "C", "D"])
    save_s.add_argument(
        "--category",
        required=True,
        choices=TrainingDataManager.S_SIGNAL_CATEGORIES,
    )
    save_s.add_argument("--csv", required=True, help="Path to CSV file")
    save_s.add_argument("--warmup", type=float, help="Warm-up time (minutes)")
    save_s.add_argument("--temp", type=float, help="Ambient temperature (°C)")

    # Save P-signal
    save_p = subparsers.add_parser("save-p", help="Save P-signal measurement")
    save_p.add_argument("--detector", required=True, choices=["A", "B", "C", "D"])
    save_p.add_argument(
        "--quality",
        required=True,
        choices=TrainingDataManager.SENSOR_QUALITIES,
    )
    save_p.add_argument("--batch", required=True, help="Chip batch ID")
    save_p.add_argument("--csv", required=True, help="Path to CSV file")
    save_p.add_argument("--chip-age", type=int, help="Chip age (days)")
    save_p.add_argument("--ri", type=float, default=1.3333, help="Medium RI")

    # Query
    query = subparsers.add_parser("query", help="Query training data")
    query.add_argument("--detector", required=True, choices=["A", "B", "C", "D"])
    query.add_argument("--signal", choices=["S", "P"])
    query.add_argument("--quality", choices=TrainingDataManager.SENSOR_QUALITIES)

    # Stats
    subparsers.add_parser("stats", help="Show statistics")

    # Export
    export = subparsers.add_parser("export", help="Export training dataset")
    export.add_argument("--output", required=True, help="Output JSON file")
    export.add_argument("--detector", choices=["A", "B", "C", "D"])
    export.add_argument("--signal", choices=["S", "P"])

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    tdm = TrainingDataManager(device_id=args.device)

    if args.command == "init":
        print(f"✓ Training data structure initialized for {args.device}")

    elif args.command == "save-s":
        metadata = {}
        if args.warmup:
            metadata["warm_up_min"] = args.warmup
        if args.temp:
            metadata["ambient_temp"] = args.temp

        tdm.save_s_signal(
            detector=args.detector,
            category=args.category,
            csv_path=args.csv,
            metadata=metadata,
        )

    elif args.command == "save-p":
        metadata = {
            "ri_medium": args.ri,
        }
        if args.chip_age:
            metadata["chip_age_days"] = args.chip_age

        tdm.save_p_signal(
            detector=args.detector,
            sensor_quality=args.quality,
            chip_batch=args.batch,
            csv_path=args.csv,
            metadata=metadata,
        )

    elif args.command == "query":
        if args.signal == "S":
            results = tdm.get_s_signal_data(detector=args.detector)
        elif args.signal == "P":
            results = tdm.get_p_signal_data(
                detector=args.detector,
                quality=args.quality,
            )
        else:
            results = tdm.get_s_signal_data(
                detector=args.detector,
            ) + tdm.get_p_signal_data(detector=args.detector)

        print(f"\n📊 Found {len(results)} measurements:")
        for r in results[:10]:  # Show first 10
            print(
                f"  • {r['measurement_id']} | {r['signal_type']}-signal | {r['timestamp']}",
            )

        if len(results) > 10:
            print(f"  ... and {len(results) - 10} more")

    elif args.command == "stats":
        stats = tdm.get_device_statistics()
        print(f"\n📊 Training Data Statistics for {stats['device_id']}")
        print(f"   Total measurements: {stats['total_measurements']}")
        print("\n   By Detector:")
        for det, counts in stats["by_detector"].items():
            print(
                f"     {det}: {counts['total']} (S={counts['s_signal']}, P={counts['p_signal']})",
            )
        print("\n   By Sensor Quality:")
        for qual, count in stats["by_sensor_quality"].items():
            if count > 0:
                print(f"     {qual}: {count}")

    elif args.command == "export":
        tdm.export_training_dataset(
            output_file=args.output,
            detector=args.detector,
            signal_type=args.signal,
        )


if __name__ == "__main__":
    main()
