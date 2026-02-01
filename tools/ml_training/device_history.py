"""Device History Database for Calibration Pattern Tracking.

Tracks per-device calibration patterns to improve ML predictions:
- Average convergence time (iterations per mode)
- Success/failure rates
- Typical FWHM quality metrics
- LED ranges and integration time patterns
- Drift over time (calibration intervals)

This enables device-specific learning, adding ~5-10% accuracy to convergence prediction.
"""

import sqlite3
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass
from datetime import datetime
import statistics


@dataclass
class CalibrationRecord:
    """Single calibration record for a device."""
    timestamp: str
    detector_serial: int
    success: bool

    # Convergence metrics
    s_mode_iterations: int
    p_mode_iterations: int
    total_iterations: int
    s_mode_converged: bool
    p_mode_converged: bool

    # Quality metrics
    final_fwhm_avg: Optional[float] = None
    final_fwhm_std: Optional[float] = None
    final_snr_avg: Optional[float] = None
    final_dip_depth_avg: Optional[float] = None
    num_warnings: int = 0
    overall_quality: Optional[str] = None  # 'excellent', 'good', 'poor'

    # LED patterns
    final_leds_s_avg: Optional[float] = None
    final_leds_p_avg: Optional[float] = None
    final_integration_s: Optional[float] = None
    final_integration_p: Optional[float] = None

    # Temporal features
    led_convergence_rate_s: Optional[float] = None
    signal_stability_s: Optional[float] = None
    oscillation_detected_s: bool = False


@dataclass
class DeviceStatistics:
    """Aggregated statistics for a device."""
    detector_serial: int
    total_calibrations: int
    successful_calibrations: int
    failed_calibrations: int
    success_rate: float

    # Convergence patterns
    avg_s_iterations: float
    avg_p_iterations: float
    avg_total_iterations: float
    std_s_iterations: float

    # Quality patterns
    avg_fwhm: Optional[float] = None
    std_fwhm: Optional[float] = None
    avg_snr: Optional[float] = None
    typical_quality: Optional[str] = None  # Most common quality
    avg_warnings_per_calibration: float = 0.0

    # LED patterns
    avg_final_led_s: Optional[float] = None
    avg_final_led_p: Optional[float] = None
    avg_integration_s: Optional[float] = None
    avg_integration_p: Optional[float] = None

    # Temporal patterns
    avg_led_convergence_rate: Optional[float] = None
    avg_signal_stability: Optional[float] = None
    oscillation_frequency: float = 0.0  # % of calibrations with oscillations

    # Drift metrics
    last_calibration_timestamp: Optional[str] = None
    days_since_last_calibration: Optional[float] = None
    calibration_frequency_days: Optional[float] = None  # Avg days between calibrations


class DeviceHistoryDatabase:
    """SQLite-based device history database."""

    def __init__(self, db_path: Path = None):
        """Initialize database.

        Args:
            db_path: Path to SQLite database file. Defaults to <script_dir>/device_history.db
        """
        if db_path is None:
            # Use same directory as this script
            db_path = Path(__file__).parent / "device_history.db"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_database()

    def _init_database(self):
        """Create database schema if not exists."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Main calibration records table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS calibration_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    detector_serial INTEGER NOT NULL,
                    success INTEGER NOT NULL,

                    s_mode_iterations INTEGER,
                    p_mode_iterations INTEGER,
                    total_iterations INTEGER,
                    s_mode_converged INTEGER,
                    p_mode_converged INTEGER,

                    final_fwhm_avg REAL,
                    final_fwhm_std REAL,
                    final_snr_avg REAL,
                    final_dip_depth_avg REAL,
                    num_warnings INTEGER,
                    overall_quality TEXT,

                    final_leds_s_avg REAL,
                    final_leds_p_avg REAL,
                    final_integration_s REAL,
                    final_integration_p REAL,

                    led_convergence_rate_s REAL,
                    signal_stability_s REAL,
                    oscillation_detected_s INTEGER,

                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create indices for fast queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_detector_serial
                ON calibration_records(detector_serial)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp
                ON calibration_records(timestamp)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_success
                ON calibration_records(success)
            """)

            conn.commit()

    def add_record(self, record: CalibrationRecord) -> int:
        """Add a calibration record to the database.

        Args:
            record: CalibrationRecord to add

        Returns:
            Record ID
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO calibration_records (
                    timestamp, detector_serial, success,
                    s_mode_iterations, p_mode_iterations, total_iterations,
                    s_mode_converged, p_mode_converged,
                    final_fwhm_avg, final_fwhm_std, final_snr_avg,
                    final_dip_depth_avg, num_warnings, overall_quality,
                    final_leds_s_avg, final_leds_p_avg,
                    final_integration_s, final_integration_p,
                    led_convergence_rate_s, signal_stability_s, oscillation_detected_s
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.timestamp, record.detector_serial, int(record.success),
                record.s_mode_iterations, record.p_mode_iterations, record.total_iterations,
                int(record.s_mode_converged) if record.s_mode_converged is not None else None,
                int(record.p_mode_converged) if record.p_mode_converged is not None else None,
                record.final_fwhm_avg, record.final_fwhm_std, record.final_snr_avg,
                record.final_dip_depth_avg, record.num_warnings, record.overall_quality,
                record.final_leds_s_avg, record.final_leds_p_avg,
                record.final_integration_s, record.final_integration_p,
                record.led_convergence_rate_s, record.signal_stability_s,
                int(record.oscillation_detected_s)
            ))

            conn.commit()
            return cursor.lastrowid

    def get_device_statistics(self, detector_serial: int, lookback_days: Optional[int] = None) -> Optional[DeviceStatistics]:
        """Calculate statistics for a specific device.

        Args:
            detector_serial: Device serial number
            lookback_days: Only consider calibrations within last N days (None = all time)

        Returns:
            DeviceStatistics or None if no data
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Build query with optional date filter
            where_clause = "WHERE detector_serial = ?"
            params = [detector_serial]

            if lookback_days:
                where_clause += " AND timestamp >= datetime('now', '-{} days')".format(lookback_days)

            # Get all records for device
            cursor.execute(f"""
                SELECT
                    timestamp, success, s_mode_iterations, p_mode_iterations, total_iterations,
                    final_fwhm_avg, final_snr_avg, overall_quality, num_warnings,
                    final_leds_s_avg, final_leds_p_avg, final_integration_s, final_integration_p,
                    led_convergence_rate_s, signal_stability_s, oscillation_detected_s
                FROM calibration_records
                {where_clause}
                ORDER BY timestamp DESC
            """, params)

            rows = cursor.fetchall()

            if not rows:
                return None

            # Calculate statistics
            total = len(rows)
            successful = sum(1 for r in rows if r[1])
            failed = total - successful

            s_iters = [r[2] for r in rows if r[2] is not None]
            p_iters = [r[3] for r in rows if r[3] is not None]
            total_iters = [r[4] for r in rows if r[4] is not None]

            fwhm_vals = [r[5] for r in rows if r[5] is not None]
            snr_vals = [r[6] for r in rows if r[6] is not None]
            qualities = [r[7] for r in rows if r[7] is not None]
            warnings = [r[8] for r in rows if r[8] is not None]

            leds_s = [r[9] for r in rows if r[9] is not None]
            leds_p = [r[10] for r in rows if r[10] is not None]
            int_s = [r[11] for r in rows if r[11] is not None]
            int_p = [r[12] for r in rows if r[12] is not None]

            conv_rates = [r[13] for r in rows if r[13] is not None]
            stabilities = [r[14] for r in rows if r[14] is not None]
            oscillations = [r[15] for r in rows if r[15] is not None and r[15] > 0]

            # Most common quality
            typical_quality = max(set(qualities), key=qualities.count) if qualities else None

            # Calculate time between calibrations
            timestamps = [datetime.fromisoformat(r[0].replace(' ', 'T')) for r in rows]
            timestamps.sort()

            if len(timestamps) >= 2:
                intervals = [(timestamps[i+1] - timestamps[i]).total_seconds() / 86400
                           for i in range(len(timestamps)-1)]
                avg_interval = statistics.mean(intervals) if intervals else None
            else:
                avg_interval = None

            # Days since last calibration
            if timestamps:
                last_cal = max(timestamps)
                days_since = (datetime.now() - last_cal).total_seconds() / 86400
            else:
                days_since = None

            return DeviceStatistics(
                detector_serial=detector_serial,
                total_calibrations=total,
                successful_calibrations=successful,
                failed_calibrations=failed,
                success_rate=successful / total if total > 0 else 0.0,

                avg_s_iterations=statistics.mean(s_iters) if s_iters else 0.0,
                avg_p_iterations=statistics.mean(p_iters) if p_iters else 0.0,
                avg_total_iterations=statistics.mean(total_iters) if total_iters else 0.0,
                std_s_iterations=statistics.stdev(s_iters) if len(s_iters) > 1 else 0.0,

                avg_fwhm=statistics.mean(fwhm_vals) if fwhm_vals else None,
                std_fwhm=statistics.stdev(fwhm_vals) if len(fwhm_vals) > 1 else None,
                avg_snr=statistics.mean(snr_vals) if snr_vals else None,
                typical_quality=typical_quality,
                avg_warnings_per_calibration=statistics.mean(warnings) if warnings else 0.0,

                avg_final_led_s=statistics.mean(leds_s) if leds_s else None,
                avg_final_led_p=statistics.mean(leds_p) if leds_p else None,
                avg_integration_s=statistics.mean(int_s) if int_s else None,
                avg_integration_p=statistics.mean(int_p) if int_p else None,

                avg_led_convergence_rate=statistics.mean(conv_rates) if conv_rates else None,
                avg_signal_stability=statistics.mean(stabilities) if stabilities else None,
                oscillation_frequency=len(oscillations) / total if total > 0 else 0.0,

                last_calibration_timestamp=rows[0][0],
                days_since_last_calibration=days_since,
                calibration_frequency_days=avg_interval,
            )

    def get_all_device_serials(self) -> List[int]:
        """Get list of all device serials in database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT detector_serial FROM calibration_records ORDER BY detector_serial")
            return [row[0] for row in cursor.fetchall()]

    def import_from_csv(self, calibration_runs_csv: Path):
        """Import calibration runs from parsed CSV data.

        Args:
            calibration_runs_csv: Path to calibration_runs.csv from parser
        """
        import pandas as pd

        df = pd.read_csv(calibration_runs_csv)

        records_added = 0
        for _, row in df.iterrows():
            # Calculate averages for LEDs
            final_leds_s = row.get('final_leds_s', '{}')
            final_leds_p = row.get('final_leds_p', '{}')

            try:
                leds_s_dict = eval(final_leds_s) if isinstance(final_leds_s, str) else {}
                leds_p_dict = eval(final_leds_p) if isinstance(final_leds_p, str) else {}

                avg_led_s = statistics.mean(leds_s_dict.values()) if leds_s_dict else None
                avg_led_p = statistics.mean(leds_p_dict.values()) if leds_p_dict else None
            except:
                avg_led_s = None
                avg_led_p = None

            record = CalibrationRecord(
                timestamp=row['timestamp'],
                detector_serial=int(row.get('detector_serial', 65535)),
                success=bool(row.get('success', False)),

                s_mode_iterations=int(row.get('total_iterations_s', 0)),
                p_mode_iterations=int(row.get('total_iterations_p', 0)),
                total_iterations=int(row.get('total_iterations_s', 0)) + int(row.get('total_iterations_p', 0)),
                s_mode_converged=bool(row.get('converged_s', False)),
                p_mode_converged=bool(row.get('converged_p', False)),

                final_fwhm_avg=row.get('final_fwhm_avg') if pd.notna(row.get('final_fwhm_avg')) else None,
                final_fwhm_std=row.get('final_fwhm_std') if pd.notna(row.get('final_fwhm_std')) else None,
                final_snr_avg=row.get('final_snr_avg') if pd.notna(row.get('final_snr_avg')) else None,
                final_dip_depth_avg=row.get('final_dip_depth_avg') if pd.notna(row.get('final_dip_depth_avg')) else None,
                num_warnings=int(row.get('num_warnings', 0)),
                overall_quality=row.get('overall_quality') if pd.notna(row.get('overall_quality')) else None,

                final_leds_s_avg=avg_led_s,
                final_leds_p_avg=avg_led_p,
                final_integration_s=row.get('final_integration_s') if pd.notna(row.get('final_integration_s')) else None,
                final_integration_p=row.get('final_integration_p') if pd.notna(row.get('final_integration_p')) else None,

                led_convergence_rate_s=row.get('led_convergence_rate_s') if pd.notna(row.get('led_convergence_rate_s')) else None,
                signal_stability_s=row.get('signal_stability_s') if pd.notna(row.get('signal_stability_s')) else None,
                oscillation_detected_s=bool(row.get('oscillation_detected_s', False)),
            )

            self.add_record(record)
            records_added += 1

        print(f"Imported {records_added} calibration records to device history database")

    def export_device_features_for_ml(self, output_csv: Path, lookback_days: int = 90):
        """Export device statistics as ML features.

        Creates a CSV with one row per device containing historical patterns
        that can be merged with calibration data for ML training.

        Args:
            output_csv: Path to output CSV file
            lookback_days: Only consider calibrations within last N days
        """
        import pandas as pd

        device_serials = self.get_all_device_serials()

        features = []
        for serial in device_serials:
            stats = self.get_device_statistics(serial, lookback_days=lookback_days)
            if stats:
                features.append({
                    'detector_serial': stats.detector_serial,
                    'device_total_calibrations': stats.total_calibrations,
                    'device_success_rate': stats.success_rate,
                    'device_avg_s_iterations': stats.avg_s_iterations,
                    'device_avg_p_iterations': stats.avg_p_iterations,
                    'device_avg_total_iterations': stats.avg_total_iterations,
                    'device_std_s_iterations': stats.std_s_iterations,
                    'device_avg_fwhm': stats.avg_fwhm,
                    'device_std_fwhm': stats.std_fwhm,
                    'device_avg_snr': stats.avg_snr,
                    'device_typical_quality': stats.typical_quality,
                    'device_avg_warnings': stats.avg_warnings_per_calibration,
                    'device_avg_final_led_s': stats.avg_final_led_s,
                    'device_avg_final_led_p': stats.avg_final_led_p,
                    'device_avg_integration_s': stats.avg_integration_s,
                    'device_avg_integration_p': stats.avg_integration_p,
                    'device_avg_convergence_rate': stats.avg_led_convergence_rate,
                    'device_avg_stability': stats.avg_signal_stability,
                    'device_oscillation_frequency': stats.oscillation_frequency,
                    'device_days_since_last_cal': stats.days_since_last_calibration,
                    'device_calibration_frequency_days': stats.calibration_frequency_days,
                })

        df = pd.DataFrame(features)
        df.to_csv(output_csv, index=False)
        print(f"Exported device features for {len(features)} devices to {output_csv}")
        return df


def main():
    """Test device history database."""
    import sys
    from pathlib import Path

    # Create database
    db = DeviceHistoryDatabase()

    # Check if calibration_runs.csv exists
    csv_path = Path(__file__).parent / "data" / "calibration_runs.csv"
    if csv_path.exists():
        print(f"Importing from {csv_path}...")
        db.import_from_csv(csv_path)

        # Export device features
        features_path = Path(__file__).parent / "data" / "device_features.csv"
        db.export_device_features_for_ml(features_path)

        # Show statistics for each device
        print("\n" + "="*80)
        print("DEVICE HISTORY STATISTICS")
        print("="*80)

        for serial in db.get_all_device_serials():
            stats = db.get_device_statistics(serial)
            if stats:
                print(f"\nDevice Serial: {stats.detector_serial}")
                print(f"  Total Calibrations: {stats.total_calibrations}")
                print(f"  Success Rate: {stats.success_rate*100:.1f}%")
                print(f"  Avg S-mode Iterations: {stats.avg_s_iterations:.1f} ± {stats.std_s_iterations:.1f}")
                print(f"  Avg P-mode Iterations: {stats.avg_p_iterations:.1f}")
                print(f"  Avg Total Iterations: {stats.avg_total_iterations:.1f}")

                if stats.avg_fwhm:
                    print(f"  Avg FWHM: {stats.avg_fwhm:.1f} ± {stats.std_fwhm:.1f} nm" if stats.std_fwhm else f"  Avg FWHM: {stats.avg_fwhm:.1f} nm")
                if stats.avg_snr:
                    print(f"  Avg SNR: {stats.avg_snr:.1f}")
                if stats.typical_quality:
                    print(f"  Typical Quality: {stats.typical_quality}")

                print(f"  Avg Warnings/Cal: {stats.avg_warnings_per_calibration:.1f}")
                print(f"  Oscillation Rate: {stats.oscillation_frequency*100:.1f}%")

                if stats.days_since_last_calibration:
                    print(f"  Days Since Last Cal: {stats.days_since_last_calibration:.1f}")
                if stats.calibration_frequency_days:
                    print(f"  Typical Cal Interval: {stats.calibration_frequency_days:.1f} days")
    else:
        print(f"ERROR: {csv_path} not found")
        print("Run parse_calibration_logs.py first to generate calibration_runs.csv")
        sys.exit(1)


if __name__ == "__main__":
    main()
