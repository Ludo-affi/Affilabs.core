"""QC Report Manager - Persistent storage and retrieval of calibration QC reports.

Manages device-specific quality control reports with full traceability for:
- Compliance and audit trails
- Historical performance tracking
- ML preventative maintenance model integration
- Trend analysis and anomaly detection

Directory Structure:
    OpticalSystem_QC/<SERIAL>/validation_reports/
        ├── qc_report_latest.json          # Latest report (quick access)
        ├── qc_report_YYYYMMDD_HHMMSS.json # Timestamped reports
        └── qc_report_latest.html          # Human-readable export
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from affilabs.utils.logger import logger


class QCReportManager:
    """Manages persistent storage and retrieval of calibration QC reports."""

    def __init__(self, base_qc_dir: str = "OpticalSystem_QC"):
        """Initialize QC report manager.

        Args:
            base_qc_dir: Base directory for all QC data (default: OpticalSystem_QC)

        """
        self.base_qc_dir = Path(base_qc_dir)

    def _get_reports_dir(self, device_serial: str) -> Path:
        """Get validation_reports directory for device.

        Args:
            device_serial: Device serial number

        Returns:
            Path to validation_reports directory

        """
        reports_dir = self.base_qc_dir / device_serial / "validation_reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        return reports_dir

    def save_qc_report(
        self,
        calibration_data: dict[str, Any],
        device_serial: str,
        user_name: str | None = None,
        software_version: str | None = None,
    ) -> Path:
        """Save QC report as JSON file.

        Saves both a timestamped version and updates the 'latest' version.
        Designed for ML model integration - includes all relevant features.

        Args:
            calibration_data: Complete calibration data dictionary
            device_serial: Device serial number
            user_name: Operator name (optional)
            software_version: Software version string (optional)

        Returns:
            Path to saved timestamped report file

        """
        try:
            reports_dir = self._get_reports_dir(device_serial)
            timestamp = datetime.now()
            timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")

            # Build comprehensive QC report structure
            qc_report = {
                "metadata": {
                    "timestamp": timestamp.isoformat(),
                    "device_serial": device_serial,
                    "firmware_version": calibration_data.get(
                        "firmware_version",
                        "Unknown",
                    ),
                    "software_version": software_version or "2.0",
                    "calibration_type": calibration_data.get(
                        "calibration_type",
                        "full_7step",
                    ),
                    "user": user_name or "operator",
                    "report_version": "1.0",
                },
                "calibration_parameters": {
                    "integration_time_ms": calibration_data.get("integration_time_ms"),
                    "num_scans": calibration_data.get("num_scans"),
                    "servo_s_position": calibration_data.get("servo_s_position"),
                    "servo_p_position": calibration_data.get("servo_p_position"),
                    "led_intensities": calibration_data.get("led_intensities", {}),
                    "cycle_time_ms": calibration_data.get("cycle_time_ms"),
                    "acquisition_rate_hz": calibration_data.get("acquisition_rate_hz"),
                },
                # Full spectra for ML feature extraction
                "spectra_data": {
                    "wavelengths": self._safe_serialize(
                        calibration_data.get("wavelengths"),
                    ),
                    "s_pol": self._serialize_channel_data(
                        calibration_data.get("s_pol_spectra", {}),
                    ),
                    "p_pol": self._serialize_channel_data(
                        calibration_data.get("p_pol_spectra", {}),
                    ),
                    "dark": self._serialize_channel_data(
                        calibration_data.get("dark_spectra", {}),
                    ),
                    "transmission": self._serialize_channel_data(
                        calibration_data.get("transmission_spectra", {}),
                    ),
                },
                # QC validation results (features for ML)
                "qc_validation": {
                    "s_ref_qc": calibration_data.get("s_ref_qc_results", {}),
                    "p_ref_qc": calibration_data.get("p_ref_qc_results", {}),
                    "overall_status": calibration_data.get(
                        "qc_overall_status",
                        "UNKNOWN",
                    ),
                    "failed_channels": calibration_data.get("ch_error_list", []),
                    "warnings": calibration_data.get("qc_warnings", []),
                },
                # Model performance metrics (ML features)
                "model_performance": {
                    "s_pol_predictions_accuracy": calibration_data.get(
                        "s_model_accuracy",
                    ),
                    "p_pol_predictions_accuracy": calibration_data.get(
                        "p_model_accuracy",
                    ),
                    "convergence_iterations_s": calibration_data.get(
                        "s_convergence_iterations",
                    ),
                    "convergence_iterations_p": calibration_data.get(
                        "p_convergence_iterations",
                    ),
                    "model_residuals_s": calibration_data.get("s_model_residuals"),
                    "model_residuals_p": calibration_data.get("p_model_residuals"),
                },
                # Signal quality metrics (ML features for predictive maintenance)
                "signal_quality": {
                    "snr_by_channel": self._extract_snr(calibration_data),
                    "peak_counts_by_channel": self._extract_peak_counts(
                        calibration_data,
                    ),
                    "noise_floor_by_channel": self._extract_noise_floor(
                        calibration_data,
                    ),
                    "spectral_stability": self._calculate_stability(calibration_data),
                    "led_efficiency": self._calculate_led_efficiency(calibration_data),
                },
                # Timing metrics (ML features)
                "timing_metrics": {
                    "timing_jitter_ms": calibration_data.get("timing_jitter_ms"),
                    "cycle_consistency": calibration_data.get("cycle_consistency"),
                    "synchronization_offset_ms": calibration_data.get("sync_offset_ms"),
                },
                # Environmental/operational context (ML features)
                "operational_context": {
                    "total_device_hours": calibration_data.get("total_led_hours", 0),
                    "total_cycles": calibration_data.get("total_cycles", 0),
                    "days_since_last_calibration": calibration_data.get(
                        "days_since_last_cal",
                    ),
                    "calibration_trigger": calibration_data.get(
                        "calibration_trigger",
                        "manual",
                    ),
                },
                # Raw calibration result for full reproduction
                "raw_calibration_data": calibration_data,
            }

            # Save timestamped version
            timestamped_file = reports_dir / f"qc_report_{timestamp_str}.json"
            with open(timestamped_file, "w", encoding="utf-8") as f:
                json.dump(qc_report, f, indent=2, default=str)

            # Save as 'latest' for quick access
            latest_file = reports_dir / "qc_report_latest.json"
            with open(latest_file, "w", encoding="utf-8") as f:
                json.dump(qc_report, f, indent=2, default=str)

            logger.debug(f"QC report saved: {timestamped_file.name} ({reports_dir})")

            return timestamped_file

        except Exception as e:
            logger.error(f"Failed to save QC report: {e}", exc_info=True)
            return None

    def load_qc_report(
        self,
        device_serial: str,
        timestamp: str | None = None,
    ) -> dict[str, Any] | None:
        """Load QC report from file.

        Args:
            device_serial: Device serial number
            timestamp: Specific timestamp string (YYYYMMDD_HHMMSS), or None for latest

        Returns:
            QC report dictionary, or None if not found

        """
        try:
            reports_dir = self._get_reports_dir(device_serial)

            if timestamp:
                report_file = reports_dir / f"qc_report_{timestamp}.json"
            else:
                report_file = reports_dir / "qc_report_latest.json"

            if not report_file.exists():
                logger.warning(f"QC report not found: {report_file}")
                return None

            with open(report_file, encoding="utf-8") as f:
                report = json.load(f)

            logger.info(f"Loaded QC report: {report_file.name}")
            return report

        except Exception as e:
            logger.error(f"Failed to load QC report: {e}")
            return None

    def list_qc_reports(self, device_serial: str) -> list[dict[str, Any]]:
        """List all QC reports for a device.

        Args:
            device_serial: Device serial number

        Returns:
            List of report metadata dicts sorted by timestamp (newest first)

        """
        try:
            reports_dir = self._get_reports_dir(device_serial)

            report_files = sorted(
                reports_dir.glob("qc_report_*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )

            reports_list = []
            for report_file in report_files:
                # Skip 'latest' file (it's a duplicate)
                if report_file.name == "qc_report_latest.json":
                    continue

                try:
                    with open(report_file, encoding="utf-8") as f:
                        report = json.load(f)

                    # Extract summary info
                    failed_ch = report["qc_validation"].get("failed_channels", [])
                    # Handle both list and dict formats
                    if isinstance(failed_ch, dict):
                        failed_count = len([v for v in failed_ch.values() if v])
                    else:
                        failed_count = len(failed_ch) if failed_ch else 0

                    reports_list.append(
                        {
                            "filename": report_file.name,
                            "timestamp": report["metadata"]["timestamp"],
                            "status": report["qc_validation"]["overall_status"],
                            "failed_channels": failed_count,
                            "user": report["metadata"]["user"],
                            "file_path": str(report_file),
                        },
                    )
                except Exception as e:
                    logger.warning(f"Could not read report {report_file.name}: {e}", exc_info=True)
                    continue

            logger.info(f"Found {len(reports_list)} QC reports for {device_serial}")
            return reports_list

        except Exception as e:
            logger.error(f"Failed to list QC reports: {e}")
            return []

    def export_to_html(
        self,
        report_path: Path,
        output_path: Path | None = None,
    ) -> Path:
        """Export QC report to human-readable HTML.

        Args:
            report_path: Path to JSON report file
            output_path: Optional output path, defaults to same dir with .html extension

        Returns:
            Path to generated HTML file

        """
        try:
            with open(report_path, encoding="utf-8") as f:
                report = json.load(f)

            if output_path is None:
                output_path = report_path.with_suffix(".html")

            html_content = self._generate_html_report(report)

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            logger.debug(f"HTML report exported: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to export HTML report: {e}")
            return None

    def get_ml_features(
        self,
        device_serial: str,
        n_reports: int = 10,
    ) -> dict[str, list]:
        """Extract ML features from recent QC reports for predictive maintenance.

        Args:
            device_serial: Device serial number
            n_reports: Number of recent reports to analyze

        Returns:
            Dictionary of feature arrays for ML model input

        """
        try:
            reports_list = self.list_qc_reports(device_serial)[:n_reports]

            features = {
                "timestamps": [],
                "snr_trends": {"a": [], "b": [], "c": [], "d": []},
                "peak_counts_trends": {"a": [], "b": [], "c": [], "d": []},
                "model_accuracy_s": [],
                "model_accuracy_p": [],
                "convergence_iterations": [],
                "timing_jitter": [],
                "led_efficiency": [],
                "device_hours": [],
                "failed_channels_count": [],
            }

            for report_info in reports_list:
                report = self.load_qc_report(
                    device_serial,
                    report_info["filename"].replace("qc_report_", "").replace(".json", ""),
                )

                if report:
                    features["timestamps"].append(report["metadata"]["timestamp"])

                    # SNR trends
                    snr_data = report["signal_quality"].get("snr_by_channel", {})
                    for ch in ["a", "b", "c", "d"]:
                        features["snr_trends"][ch].append(snr_data.get(ch))

                    # Peak counts trends
                    peak_data = report["signal_quality"].get(
                        "peak_counts_by_channel",
                        {},
                    )
                    for ch in ["a", "b", "c", "d"]:
                        features["peak_counts_trends"][ch].append(peak_data.get(ch))

                    # Model performance
                    features["model_accuracy_s"].append(
                        report["model_performance"].get("s_pol_predictions_accuracy"),
                    )
                    features["model_accuracy_p"].append(
                        report["model_performance"].get("p_pol_predictions_accuracy"),
                    )

                    # Other metrics
                    features["convergence_iterations"].append(
                        (
                            report["model_performance"].get(
                                "convergence_iterations_s",
                                0,
                            )
                            + report["model_performance"].get(
                                "convergence_iterations_p",
                                0,
                            )
                        )
                        / 2,
                    )
                    features["timing_jitter"].append(
                        report["timing_metrics"].get("timing_jitter_ms"),
                    )
                    features["led_efficiency"].append(
                        report["signal_quality"].get("led_efficiency"),
                    )
                    features["device_hours"].append(
                        report["operational_context"].get("total_device_hours", 0),
                    )
                    features["failed_channels_count"].append(
                        len(report["qc_validation"].get("failed_channels", [])),
                    )

            logger.info(f"Extracted ML features from {len(reports_list)} reports")
            return features

        except Exception as e:
            logger.error(f"Failed to extract ML features: {e}")
            return {}

    # Helper methods for data extraction and serialization

    def _safe_serialize(self, data):
        """Safely serialize numpy arrays or lists."""
        if data is None:
            return None
        try:
            import numpy as np

            if isinstance(data, np.ndarray):
                return data.tolist()
            return data
        except Exception:
            return data

    def _serialize_channel_data(self, channel_dict: dict) -> dict:
        """Serialize channel data dictionary."""
        if not channel_dict:
            return {}
        return {ch: self._safe_serialize(data) for ch, data in channel_dict.items()}

    def _extract_snr(self, calibration_data: dict) -> dict[str, float]:
        """Extract SNR by channel from calibration data."""
        snr_data = {}
        s_qc = calibration_data.get("s_ref_qc_results", {})
        for ch in ["a", "b", "c", "d"]:
            if ch in s_qc and "snr" in s_qc[ch]:
                snr_data[ch] = s_qc[ch]["snr"]
        return snr_data

    def _extract_peak_counts(self, calibration_data: dict) -> dict[str, float]:
        """Extract peak counts by channel."""
        peak_data = {}
        s_qc = calibration_data.get("s_ref_qc_results", {})
        for ch in ["a", "b", "c", "d"]:
            if ch in s_qc and "peak_counts" in s_qc[ch]:
                peak_data[ch] = s_qc[ch]["peak_counts"]
        return peak_data

    def _extract_noise_floor(self, calibration_data: dict) -> dict[str, float]:
        """Calculate noise floor from dark spectra."""
        noise_floor = {}
        dark_data = calibration_data.get("dark_spectra", {})
        for ch, spectrum in dark_data.items():
            if spectrum is not None:
                try:
                    import numpy as np

                    noise_floor[ch] = float(np.std(spectrum))
                except Exception:
                    pass
        return noise_floor

    def _calculate_stability(self, calibration_data: dict) -> float:
        """Calculate spectral stability metric."""
        # Placeholder - can be enhanced with actual stability calculation
        return calibration_data.get("spectral_stability", 0.95)

    def _calculate_led_efficiency(self, calibration_data: dict) -> float:
        """Calculate LED efficiency metric (signal per LED intensity unit)."""
        try:
            led_intensities = calibration_data.get("led_intensities", {})
            peak_counts = self._extract_peak_counts(calibration_data)

            if led_intensities and peak_counts:
                total_intensity = sum(led_intensities.values())
                total_counts = sum(peak_counts.values())
                if total_intensity > 0:
                    return total_counts / total_intensity
        except Exception:
            pass
        return None

    def _generate_html_report(self, report: dict) -> str:
        """Generate HTML report from QC data."""
        metadata = report["metadata"]
        qc_validation = report["qc_validation"]

        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>QC Report - {metadata['device_serial']}</title>
    <style>
        body {{ font-family: -apple-system, system-ui, sans-serif; margin: 40px; background: #f5f5f7; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 40px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        h1 {{ color: #1d1d1f; border-bottom: 3px solid #007aff; padding-bottom: 10px; }}
        h2 {{ color: #007aff; margin-top: 30px; }}
        .status-pass {{ color: #34c759; font-weight: bold; }}
        .status-fail {{ color: #ff3b30; font-weight: bold; }}
        .metadata {{ background: #f5f5f7; padding: 20px; border-radius: 8px; margin: 20px 0; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #d1d1d6; }}
        th {{ background: #f5f5f7; font-weight: 600; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Calibration QC Report</h1>

        <div class="metadata">
            <p><strong>Device Serial:</strong> {metadata['device_serial']}</p>
            <p><strong>Timestamp:</strong> {metadata['timestamp']}</p>
            <p><strong>Firmware:</strong> {metadata['firmware_version']}</p>
            <p><strong>Software:</strong> {metadata['software_version']}</p>
            <p><strong>Operator:</strong> {metadata['user']}</p>
        </div>

        <h2>QC Status</h2>
        <p class="{'status-pass' if qc_validation['overall_status'] == 'PASS' else 'status-fail'}">
            {qc_validation['overall_status']}
        </p>

        <h2>Failed Channels</h2>
        <p>{', '.join(qc_validation['failed_channels']) if qc_validation['failed_channels'] else 'None - All channels passed'}</p>

        <h2>Calibration Parameters</h2>
        <table>
            <tr><th>Parameter</th><th>Value</th></tr>
            {self._generate_table_rows(report['calibration_parameters'])}
        </table>

        <p style="margin-top: 40px; color: #86868b; font-size: 12px;">
            Generated by ezControl AI v{metadata['software_version']} • Report version {metadata['report_version']}
        </p>
    </div>
</body>
</html>"""
        return html

    def _generate_table_rows(self, data: dict) -> str:
        """Generate HTML table rows from dictionary."""
        rows = []
        for key, value in data.items():
            if isinstance(value, dict):
                value = json.dumps(value, indent=2)
            rows.append(f"<tr><td>{key}</td><td>{value}</td></tr>")
        return "\n".join(rows)
