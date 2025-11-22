"""Test FMEA Tracker - Demonstrate cohesive monitoring across phases."""

import sys
from pathlib import Path

# Add Old software to path
old_software_path = Path(__file__).parent / "Old software"
sys.path.insert(0, str(old_software_path))

from core.fmea_tracker import FMEATracker, FailureMode, Severity
from core.fmea_integration import FMEAIntegrationHelper


def test_calibration_phase():
    """Simulate calibration phase with various scenarios."""
    print("\n" + "="*70)
    print("PHASE 1: CALIBRATION")
    print("="*70)

    fmea = FMEATracker(session_id="test_demo_001")
    helper = FMEAIntegrationHelper(fmea)

    # Scenario 1: Good LED calibration
    print("\n✅ Channel A - Good LED calibration")
    helper.check_led_calibration(
        channel='a',
        intensity=25000,
        target_intensity=25000,
        r_squared=0.997
    )

    # Scenario 2: LED saturation
    print("\n❌ Channel B - LED Saturation")
    helper.check_led_calibration(
        channel='b',
        intensity=62000,
        target_intensity=25000,
        r_squared=0.950
    )

    # Scenario 3: Good dark noise
    print("\n✅ System - Good dark noise")
    helper.check_dark_noise(
        channel=None,
        dark_mean=95.0,
        dark_std=15.0
    )

    # Scenario 4: High dark noise
    print("\n⚠️ Channel C - High dark noise (potential leak)")
    helper.check_dark_noise(
        channel='c',
        dark_mean=250.0,
        dark_std=45.0
    )

    fmea.mark_calibration_complete()

    return fmea, helper


def test_afterglow_phase(fmea, helper):
    """Simulate afterglow validation phase."""
    print("\n" + "="*70)
    print("PHASE 2: AFTERGLOW VALIDATION")
    print("="*70)

    # Scenario 1: Good tau for LCW LED
    print("\n✅ Channel A - Good tau")
    helper.check_afterglow_tau(
        channel='a',
        tau_ms=21.5,
        led_type='LCW',
        expected_range=(15, 26),
        warn_range=(10, 35)
    )

    # Scenario 2: Tau out of range (B has saturation issue from calibration)
    print("\n❌ Channel B - Tau out of range (correlation with saturation)")
    helper.check_afterglow_tau(
        channel='b',
        tau_ms=42.0,  # Way too high
        led_type='LCW',
        expected_range=(15, 26),
        warn_range=(10, 35)
    )

    # Scenario 3: High amplitude (LED timing issue)
    print("\n⚠️ Channel C - High amplitude (LED timing issue)")
    helper.check_afterglow_amplitude(
        channel='c',
        amplitude=15000,  # Too high
        integration_time_ms=55.0
    )

    # Scenario 4: Good fit quality
    print("\n✅ Channel A - Excellent fit quality")
    helper.check_afterglow_fit_quality(
        channel='a',
        r_squared=0.978
    )

    # Scenario 5: Poor fit quality
    print("\n❌ Channel B - Poor fit quality (correlation with tau issue)")
    helper.check_afterglow_fit_quality(
        channel='b',
        r_squared=0.812  # Below threshold
    )

    fmea.mark_afterglow_validation_complete()

    # Check calibration → afterglow correlation
    print("\n" + "-"*70)
    print("CROSS-PHASE CORRELATION: Calibration → Afterglow")
    print("-"*70)
    helper.check_calibration_afterglow_correlation()


def test_live_data_phase(fmea, helper):
    """Simulate live data acquisition phase."""
    print("\n" + "="*70)
    print("PHASE 3: LIVE DATA PROCESSING")
    print("="*70)

    # Scenario 1: Good signal quality
    print("\n✅ Channel A - Good signal quality")
    helper.check_signal_quality(
        channel='a',
        peak_intensity=25000,
        fwhm_nm=38.5,
        snr=125.0
    )

    # Scenario 2: Signal loss (Channel B has issues from earlier phases)
    print("\n❌ Channel B - Signal loss (cascading from calibration issues)")
    helper.check_signal_quality(
        channel='b',
        peak_intensity=500,  # Very low
        fwhm_nm=85.0,  # Poor
        snr=5.2  # Low SNR
    )

    # Scenario 3: Pump interference
    print("\n⚠️ Channel A - Pump interference detected")
    helper.check_pump_correlation(
        channel='a',
        pump_flow_rate=200.0,
        signal_change=150.0,  # Large spike
        time_since_pump_change=1.2,  # Recent
        expected_correlation=False  # Not during injection
    )

    # Scenario 4: FWHM degradation over time
    print("\n⚠️ Channel A - FWHM degrading over time")
    helper.check_fwhm_trend(
        channel='a',
        current_fwhm=42.8,
        calibration_fwhm=38.5,
        fwhm_rate_nm_per_min=0.65,  # Above threshold
        max_rate=0.5
    )

    # Check afterglow → live data correlation
    print("\n" + "-"*70)
    print("CROSS-PHASE CORRELATION: Afterglow → Live Data")
    print("-"*70)
    helper.check_afterglow_live_correlation()


def display_system_health(fmea):
    """Display current system health summary."""
    print("\n" + "="*70)
    print("SYSTEM HEALTH SUMMARY")
    print("="*70)

    health = fmea.get_system_health()

    print(f"\n📊 Session: {health['session_id']}")
    print(f"⏱️ Duration: {health['session_duration_minutes']:.1f} minutes")
    print(f"🎯 Overall Health: {health['overall_health'].upper()}")
    print(f"🔴 Active Failures: {health['active_failures']['count']}")

    if health['active_failures']['failures']:
        print("\n📋 Active Failure Details:")
        for failure in health['active_failures']['failures']:
            print(f"   • {failure['mode']} (Ch {failure['channel'] or 'System'})")
            print(f"     Severity: {failure['severity']}, Active for: {failure['since']:.0f}s")

    print(f"\n📈 Severity Distribution:")
    for severity, count in health['severity_distribution'].items():
        if count > 0:
            print(f"   {severity}: {count}")

    print(f"\n✅ Phase Status:")
    print(f"   Calibration: {'✓ Complete' if health['phase_status']['calibration_completed'] else '⏳ Pending'}")
    print(f"   Afterglow: {'✓ Complete' if health['phase_status']['afterglow_validated'] else '⏳ Pending'}")
    print(f"   Live Data: {'🟢 Active' if health['phase_status']['live_data_active'] else '⚫ Inactive'}")

    print(f"\n🔗 Correlation Score: {health['correlation_score']:.1f}/100")
    print(f"📝 Total Events: {health['total_events']}")


def display_active_scenarios(fmea):
    """Display detected failure scenarios."""
    print("\n" + "="*70)
    print("DETECTED FAILURE SCENARIOS")
    print("="*70)

    scenarios = fmea.get_active_scenarios()

    if not scenarios:
        print("\n✅ No active failure scenarios detected")
        return

    for i, scenario in enumerate(scenarios, 1):
        print(f"\n⚠️ SCENARIO {i}: {scenario['name']}")
        print(f"   Description: {scenario['description']}")
        print(f"   Detection: {scenario['detection_logic']}")
        print(f"   Severity: {scenario['severity']}")
        print(f"   🔧 Mitigation: {scenario['mitigation']}")
        if scenario['correlation_check']:
            print(f"   🔗 Correlation: {scenario['correlation_check']}")


def display_event_summary(fmea):
    """Display event summary by phase and status."""
    print("\n" + "="*70)
    print("EVENT SUMMARY")
    print("="*70)

    phases = ['calibration', 'afterglow', 'live_data']

    for phase in phases:
        events = fmea.query_events(phase=phase)
        if events:
            passed = sum(1 for e in events if e.passed)
            failed = sum(1 for e in events if not e.passed)
            total = len(events)

            print(f"\n{phase.upper()}:")
            print(f"   Total: {total} events")
            print(f"   ✅ Passed: {passed} ({passed/total*100:.0f}%)")
            print(f"   ❌ Failed: {failed} ({failed/total*100:.0f}%)")


def main():
    """Run FMEA demonstration."""
    print("\n" + "="*70)
    print("FMEA TRACKER DEMONSTRATION")
    print("Cohesive Monitoring: Calibration → Afterglow → Live Data")
    print("="*70)

    # Run through all phases
    fmea, helper = test_calibration_phase()
    test_afterglow_phase(fmea, helper)
    test_live_data_phase(fmea, helper)

    # Display analysis
    display_system_health(fmea)
    display_active_scenarios(fmea)
    display_event_summary(fmea)

    # Export report
    print("\n" + "="*70)
    print("EXPORTING SESSION REPORT")
    print("="*70)

    report_path = fmea.export_session_report()
    print(f"\n📄 Report saved: {report_path}")
    print(f"📊 View JSON file for complete event history and metrics")

    print("\n" + "="*70)
    print("✅ FMEA DEMONSTRATION COMPLETE")
    print("="*70)
    print("\nKey Features Demonstrated:")
    print("  ✓ Cross-phase event tracking (calibration → afterglow → live)")
    print("  ✓ Failure mode classification and severity")
    print("  ✓ Correlation analysis between phases")
    print("  ✓ Scenario detection with mitigation strategies")
    print("  ✓ System health scoring")
    print("  ✓ Exportable session reports")
    print("\nIntegration:")
    print("  • See fmea_integration.py for code examples")
    print("  • Integrate into led_calibration.py, afterglow_correction.py,")
    print("    data_acquisition_manager.py for complete coverage")
    print()


if __name__ == "__main__":
    main()
