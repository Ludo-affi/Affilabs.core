"""LED Health Monitoring System

Tracks LED degradation over time by comparing afterglow calibration data.
Automatically runs every 100 operating hours to detect:
- Phosphor decay time (τ) drift
- Afterglow amplitude changes
- Fit quality degradation
- Channel-to-channel variations

Author: GitHub Copilot
Date: October 21, 2025
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np

from utils.logger import logger


class LEDHealthMonitor:
    """Monitor LED degradation by comparing afterglow calibrations over time."""

    def __init__(self, baseline_file: str | Path, device_config_path: str | Path = "config/device_config.json"):
        """Initialize LED health monitor.

        Args:
            baseline_file: Path to baseline afterglow calibration (reference)
            device_config_path: Path to device configuration file
        """
        self.baseline_file = Path(baseline_file)
        self.device_config_path = Path(device_config_path)

        # Load baseline data
        with open(self.baseline_file) as f:
            self.baseline = json.load(f)

        logger.info(f"📊 LED Health Monitor initialized with baseline: {self.baseline_file.name}")

    def should_run_health_check(self) -> tuple[bool, float, float]:
        """Check if LED health check is due based on operating hours.

        Returns:
            (should_run, hours_since_last_check, hours_until_next)
        """
        try:
            with open(self.device_config_path) as f:
                config = json.load(f)
        except FileNotFoundError:
            logger.warning(f"Device config not found: {self.device_config_path}")
            return False, 0.0, 100.0

        # Get tracking data
        maintenance = config.get('maintenance', {})
        led_on_hours = maintenance.get('led_on_hours', 0.0)
        last_health_check_hours = maintenance.get('led_health_check_last_hours', 0.0)
        check_interval_hours = maintenance.get('led_health_check_interval_hours', 100.0)

        hours_since_last = led_on_hours - last_health_check_hours
        hours_until_next = check_interval_hours - hours_since_last

        should_run = hours_since_last >= check_interval_hours

        if should_run:
            logger.info(f"⏰ LED health check DUE: {hours_since_last:.1f} hours since last check")
        else:
            logger.debug(f"LED health check in {hours_until_next:.1f} hours")

        return should_run, hours_since_last, hours_until_next

    def run_afterglow_calibration(self) -> Path | None:
        """Run afterglow calibration and return path to new calibration file.

        Returns:
            Path to new calibration file, or None if failed
        """
        logger.info("🔬 Starting LED afterglow calibration (40-50 minutes)...")

        try:
            # Run the calibration script
            script_path = Path("led_afterglow_integration_time_model.py")
            venv_python = Path(".venv312/Scripts/python.exe")

            if not venv_python.exists():
                venv_python = Path(".venv/Scripts/python.exe")

            result = subprocess.run(
                [str(venv_python), str(script_path)],
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout
            )

            if result.returncode != 0:
                logger.error(f"Calibration failed: {result.stderr}")
                return None

            # Find the newest calibration file
            calib_dir = Path("generated-files/characterization")
            calib_files = sorted(
                calib_dir.glob("led_afterglow_integration_time_models_*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )

            if calib_files:
                logger.info(f"✅ Calibration complete: {calib_files[0].name}")
                return calib_files[0]
            else:
                logger.error("No calibration file found after running calibration")
                return None

        except subprocess.TimeoutExpired:
            logger.error("Calibration timed out after 1 hour")
            return None
        except Exception as e:
            logger.error(f"Calibration error: {e}")
            return None

    def compare_calibrations(self, new_file: Path) -> dict[str, Any]:
        """Compare new calibration against baseline.

        Args:
            new_file: Path to new calibration file

        Returns:
            Dictionary with degradation metrics for each channel
        """
        logger.info(f"📈 Comparing calibrations: baseline vs {new_file.name}")

        with open(new_file) as f:
            new_data = json.load(f)

        results = {
            'comparison_date': datetime.now().isoformat(),
            'baseline_file': str(self.baseline_file.name),
            'new_file': str(new_file.name),
            'channels': {}
        }

        for channel in ['A', 'B', 'C', 'D']:
            baseline_ch = self.baseline['channel_data'][channel]
            new_ch = new_data['channel_data'][channel]

            # Extract tau values
            baseline_taus = []
            new_taus = []
            baseline_amps = []
            new_amps = []

            for bd in baseline_ch['integration_time_data']:
                if bd.get('fit_success', False):
                    baseline_taus.append(bd['tau_ms'])
                    baseline_amps.append(bd['amplitude'])

            for nd in new_ch['integration_time_data']:
                if nd.get('fit_success', False):
                    new_taus.append(nd['tau_ms'])
                    new_amps.append(nd['amplitude'])

            # Calculate metrics
            tau_baseline_mean = np.mean(baseline_taus) if baseline_taus else 0
            tau_new_mean = np.mean(new_taus) if new_taus else 0
            tau_drift_pct = ((tau_new_mean - tau_baseline_mean) / tau_baseline_mean * 100) if tau_baseline_mean > 0 else 0

            amp_baseline_mean = np.mean(baseline_amps) if baseline_amps else 0
            amp_new_mean = np.mean(new_amps) if new_amps else 0
            amp_drift_pct = ((amp_new_mean - amp_baseline_mean) / amp_baseline_mean * 100) if amp_baseline_mean > 0 else 0

            # Health status
            if abs(tau_drift_pct) < 10 and abs(amp_drift_pct) < 20:
                health = 'GOOD'
                status_emoji = '✅'
            elif abs(tau_drift_pct) < 20 and abs(amp_drift_pct) < 40:
                health = 'WARNING'
                status_emoji = '⚠️'
            else:
                health = 'CRITICAL'
                status_emoji = '🚨'

            results['channels'][channel] = {
                'tau_baseline_ms': tau_baseline_mean,
                'tau_new_ms': tau_new_mean,
                'tau_drift_percent': tau_drift_pct,
                'amplitude_baseline': amp_baseline_mean,
                'amplitude_new': amp_new_mean,
                'amplitude_drift_percent': amp_drift_pct,
                'health_status': health,
                'status_emoji': status_emoji,
                'baseline_points': len(baseline_taus),
                'new_points': len(new_taus)
            }

            logger.info(
                f"  Channel {channel}: {status_emoji} {health} "
                f"(τ drift: {tau_drift_pct:+.1f}%, amp drift: {amp_drift_pct:+.1f}%)"
            )

        return results

    def generate_health_report(self, comparison_results: dict[str, Any], output_dir: Path = None) -> Path:
        """Generate visual health report with plots.

        Args:
            comparison_results: Results from compare_calibrations()
            output_dir: Directory to save report (default: generated-files/health-reports)

        Returns:
            Path to generated report image
        """
        if output_dir is None:
            output_dir = Path("generated-files/health-reports")
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_path = output_dir / f"led_health_report_{timestamp}.png"

        # Create 2x2 plot grid
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle('LED Health Monitoring Report', fontsize=16, fontweight='bold')

        channels = ['A', 'B', 'C', 'D']
        colors = {'A': 'red', 'B': 'blue', 'C': 'green', 'D': 'orange'}

        # Plot 1: Tau drift per channel
        ax1 = axes[0, 0]
        tau_drifts = [comparison_results['channels'][ch]['tau_drift_percent'] for ch in channels]
        bars1 = ax1.bar(channels, tau_drifts, color=[colors[ch] for ch in channels], alpha=0.7)
        ax1.axhline(y=10, color='orange', linestyle='--', label='Warning threshold (±10%)')
        ax1.axhline(y=-10, color='orange', linestyle='--')
        ax1.axhline(y=20, color='red', linestyle='--', label='Critical threshold (±20%)')
        ax1.axhline(y=-20, color='red', linestyle='--')
        ax1.set_ylabel('Decay Time (τ) Drift (%)', fontweight='bold')
        ax1.set_title('Phosphor Decay Time Change')
        ax1.legend(fontsize=8)
        ax1.grid(True, alpha=0.3)

        # Plot 2: Amplitude drift per channel
        ax2 = axes[0, 1]
        amp_drifts = [comparison_results['channels'][ch]['amplitude_drift_percent'] for ch in channels]
        bars2 = ax2.bar(channels, amp_drifts, color=[colors[ch] for ch in channels], alpha=0.7)
        ax2.axhline(y=20, color='orange', linestyle='--', label='Warning threshold (±20%)')
        ax2.axhline(y=-20, color='orange', linestyle='--')
        ax2.axhline(y=40, color='red', linestyle='--', label='Critical threshold (±40%)')
        ax2.axhline(y=-40, color='red', linestyle='--')
        ax2.set_ylabel('Afterglow Amplitude Drift (%)', fontweight='bold')
        ax2.set_title('Afterglow Strength Change')
        ax2.legend(fontsize=8)
        ax2.grid(True, alpha=0.3)

        # Plot 3: Health status summary
        ax3 = axes[1, 0]
        health_statuses = [comparison_results['channels'][ch]['health_status'] for ch in channels]
        status_colors = {'GOOD': 'green', 'WARNING': 'orange', 'CRITICAL': 'red'}
        bar_colors = [status_colors[status] for status in health_statuses]
        status_values = [2 if s == 'GOOD' else 1 if s == 'WARNING' else 0 for s in health_statuses]
        bars3 = ax3.bar(channels, status_values, color=bar_colors, alpha=0.7)
        ax3.set_ylabel('Health Status', fontweight='bold')
        ax3.set_yticks([0, 1, 2])
        ax3.set_yticklabels(['CRITICAL', 'WARNING', 'GOOD'])
        ax3.set_title('Overall LED Health Status')
        ax3.grid(True, alpha=0.3, axis='y')

        # Plot 4: Summary text
        ax4 = axes[1, 1]
        ax4.axis('off')

        summary_text = f"""
LED HEALTH SUMMARY

Baseline: {comparison_results['baseline_file']}
Current:  {comparison_results['new_file']}
Date:     {comparison_results['comparison_date'][:10]}

CHANNEL STATUS:
"""
        for ch in channels:
            ch_data = comparison_results['channels'][ch]
            summary_text += f"\n{ch}: {ch_data['status_emoji']} {ch_data['health_status']}"
            summary_text += f"\n   τ drift: {ch_data['tau_drift_percent']:+.1f}%"
            summary_text += f"\n   Amplitude: {ch_data['amplitude_drift_percent']:+.1f}%"

        summary_text += "\n\nRECOMMENDATIONS:"
        critical_channels = [ch for ch, data in comparison_results['channels'].items()
                            if data['health_status'] == 'CRITICAL']
        warning_channels = [ch for ch, data in comparison_results['channels'].items()
                           if data['health_status'] == 'WARNING']

        if critical_channels:
            summary_text += f"\n🚨 REPLACE LED(s): {', '.join(critical_channels)}"
        elif warning_channels:
            summary_text += f"\n⚠️  MONITOR: {', '.join(warning_channels)}"
        else:
            summary_text += "\n✅ All LEDs healthy"

        ax4.text(0.05, 0.95, summary_text, transform=ax4.transAxes,
                fontsize=10, verticalalignment='top', family='monospace',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))

        plt.tight_layout()
        plt.savefig(report_path, dpi=150, bbox_inches='tight')
        plt.close()

        logger.info(f"📊 Health report saved: {report_path}")
        return report_path

    def update_maintenance_record(self, comparison_results: dict[str, Any]) -> None:
        """Update device config with health check timestamp.

        Args:
            comparison_results: Results from compare_calibrations()
        """
        try:
            with open(self.device_config_path) as f:
                config = json.load(f)

            maintenance = config.get('maintenance', {})
            led_on_hours = maintenance.get('led_on_hours', 0.0)

            # Update last health check timestamp
            maintenance['led_health_check_last_hours'] = led_on_hours
            maintenance['led_health_check_last_date'] = datetime.now().isoformat()

            # Store health status summary
            health_summary = {ch: data['health_status']
                            for ch, data in comparison_results['channels'].items()}
            maintenance['led_health_status'] = health_summary

            config['maintenance'] = maintenance

            with open(self.device_config_path, 'w') as f:
                json.dump(config, f, indent=2)

            logger.info(f"✅ Maintenance record updated: {led_on_hours:.1f} hours")

        except Exception as e:
            logger.error(f"Failed to update maintenance record: {e}")

    def run_health_check(self) -> bool:
        """Run complete LED health check workflow.

        Returns:
            True if successful, False otherwise
        """
        logger.info("=" * 60)
        logger.info("🏥 LED HEALTH CHECK STARTING")
        logger.info("=" * 60)

        try:
            # Run calibration
            new_calib_file = self.run_afterglow_calibration()
            if not new_calib_file:
                logger.error("❌ Health check failed: calibration error")
                return False

            # Compare calibrations
            results = self.compare_calibrations(new_calib_file)

            # Generate report
            report_path = self.generate_health_report(results)

            # Update maintenance record
            self.update_maintenance_record(results)

            logger.info("=" * 60)
            logger.info("✅ LED HEALTH CHECK COMPLETE")
            logger.info(f"📊 Report: {report_path}")
            logger.info("=" * 60)

            return True

        except Exception as e:
            logger.error(f"❌ Health check failed: {e}", exc_info=True)
            return False


def check_and_run_health_monitor() -> bool:
    """Check if health monitor should run and execute if needed.

    Call this function on app shutdown.

    Returns:
        True if health check was run, False if skipped
    """
    baseline_file = Path("generated-files/characterization/led_afterglow_integration_time_models_20251011_210859.json")

    if not baseline_file.exists():
        logger.warning("No baseline calibration file found - skipping health check")
        return False

    monitor = LEDHealthMonitor(baseline_file)
    should_run, hours_since, hours_until = monitor.should_run_health_check()

    if should_run:
        logger.info(f"⏰ LED health check DUE ({hours_since:.1f} hours since last check)")
        return monitor.run_health_check()
    else:
        logger.debug(f"LED health check not due (next in {hours_until:.1f} hours)")
        return False


if __name__ == '__main__':
    # For manual testing
    check_and_run_health_monitor()
