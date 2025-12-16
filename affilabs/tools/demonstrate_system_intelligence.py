"""Example: System Intelligence in Action

This script demonstrates how the System Intelligence module works
by simulating various operational scenarios and showing the guidance provided.

Run this to see:
- Issue detection and classification
- Troubleshooting recommendations
- Maintenance predictions
- Diagnostic report generation

Author: AI Assistant
Date: November 21, 2025
"""

import time

from core.system_intelligence import get_system_intelligence

from affilabs.utils.logger import logger


def demonstrate_calibration_analysis():
    """Demonstrate calibration quality analysis."""
    print("\n" + "=" * 60)
    print("SCENARIO 1: Calibration Quality Analysis")
    print("=" * 60)

    si = get_system_intelligence()

    # Scenario 1A: Good calibration
    print("\n--- Good Calibration ---")
    si.update_calibration_metrics(
        success=True,
        quality_scores={"a": 0.92, "b": 0.88, "c": 0.90, "d": 0.91},
        failed_channels=None,
    )

    state, issues = si.diagnose_system()
    print(f"System State: {state.value}")
    print(f"Active Issues: {len(issues)}")

    # Scenario 1B: Low quality channel
    print("\n--- Low Quality Channel C ---")
    si.clear_all_issues()
    si.update_calibration_metrics(
        success=True,
        quality_scores={"a": 0.92, "b": 0.88, "c": 0.65, "d": 0.91},
        failed_channels=None,
    )

    state, issues = si.diagnose_system()
    print(f"System State: {state.value}")
    for issue in issues:
        print(f"\n🚨 {issue.severity.value.upper()}: {issue.title}")
        print(f"   Confidence: {issue.confidence*100:.0f}%")
        print(f"   Description: {issue.description}")
        print("   Recommended Actions:")
        for action in issue.recommended_actions[:3]:
            print(f"      • {action}")

    # Scenario 1C: Complete calibration failure
    print("\n--- Complete Calibration Failure ---")
    si.clear_all_issues()
    si.update_calibration_metrics(
        success=False,
        quality_scores={},
        failed_channels=["a", "b", "c", "d"],
    )

    state, issues = si.diagnose_system()
    print(f"System State: {state.value}")
    for issue in issues:
        print(f"\n🔴 {issue.severity.value.upper()}: {issue.title}")
        print(f"   Confidence: {issue.confidence*100:.0f}%")
        print("   Probable Causes:")
        for cause in issue.probable_causes:
            print(f"      • {cause}")
        print("   Recommended Actions:")
        for action in issue.recommended_actions:
            print(f"      • {action}")


def demonstrate_signal_quality_monitoring():
    """Demonstrate real-time signal quality monitoring."""
    print("\n" + "=" * 60)
    print("SCENARIO 2: Signal Quality Monitoring")
    print("=" * 60)

    si = get_system_intelligence()
    si.clear_all_issues()

    # Scenario 2A: Good signal
    print("\n--- Good Signal Quality ---")
    si.update_signal_quality(
        channel="a",
        snr=15.5,
        peak_wavelength=637.2,
        transmission_quality=0.88,
    )

    state, issues = si.diagnose_system()
    print(f"System State: {state.value}")
    print(f"Active Issues: {len(issues)}")

    # Scenario 2B: Low SNR
    print("\n--- Low SNR Detected ---")
    si.update_signal_quality(
        channel="b",
        snr=4.2,
        peak_wavelength=637.8,
        transmission_quality=0.62,
    )

    state, issues = si.diagnose_system()
    print(f"System State: {state.value}")
    for issue in issues:
        print(f"\n[WARN] {issue.severity.value.upper()}: {issue.title}")
        print(f"   Metrics: SNR={issue.metrics.get('snr', 0):.1f}dB")
        print("   Symptoms:")
        for symptom in issue.symptoms:
            print(f"      • {symptom}")
        print("   Recommended Actions:")
        for action in issue.recommended_actions[:3]:
            print(f"      • {action}")


def demonstrate_led_health_tracking():
    """Demonstrate LED health degradation tracking."""
    print("\n" + "=" * 60)
    print("SCENARIO 3: LED Health Tracking")
    print("=" * 60)

    si = get_system_intelligence()
    si.clear_all_issues()

    # Scenario 3A: Healthy LEDs
    print("\n--- Healthy LED Operation ---")
    for ch, intensity in [("a", 29800), ("b", 30100), ("c", 30500), ("d", 29600)]:
        si.update_led_health(ch, intensity=intensity, target=30000)

    state, issues = si.diagnose_system()
    print(f"System State: {state.value}")
    print(f"Active Issues: {len(issues)}")

    # Scenario 3B: LED degradation
    print("\n--- LED Degradation on Channel B ---")
    si.update_led_health("b", intensity=22000, target=30000)

    state, issues = si.diagnose_system()
    print(f"System State: {state.value}")
    for issue in issues:
        print(f"\n[WARN] {issue.severity.value.upper()}: {issue.title}")
        print(
            f"   Metrics: Intensity={issue.metrics['intensity']:.0f}, "
            f"Target={issue.metrics['target']:.0f}, "
            f"Degradation={issue.metrics['degradation']*100:.1f}%",
        )
        print("   Probable Causes:")
        for cause in issue.probable_causes:
            print(f"      • {cause}")


def demonstrate_maintenance_recommendations():
    """Demonstrate predictive maintenance recommendations."""
    print("\n" + "=" * 60)
    print("SCENARIO 4: Maintenance Recommendations")
    print("=" * 60)

    si = get_system_intelligence()

    # Simulate operational metrics
    si.metrics.calibration_drift_rate = 0.8  # nm/hour (high drift)
    si.metrics.led_intensity_degradation["b"] = 0.25  # 25% degradation
    si.metrics.dark_noise_level = 1200  # Elevated noise

    recommendations = si.get_maintenance_recommendations()

    print(f"\nFound {len(recommendations)} maintenance recommendations:")

    for rec in recommendations:
        priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        emoji = priority_emoji.get(rec["priority"], "⚪")

        print(f"\n{emoji} {rec['priority'].upper()} Priority")
        print(f"   Category: {rec['category']}")
        print(f"   Title: {rec['title']}")
        print(f"   Description: {rec['description']}")
        print(f"   Action: {rec['action']}")
        print(f"   Urgency: Within {rec['urgency_hours']} hours")


def demonstrate_report_generation():
    """Demonstrate diagnostic report generation."""
    print("\n" + "=" * 60)
    print("SCENARIO 5: Diagnostic Report Generation")
    print("=" * 60)

    si = get_system_intelligence()

    # Generate report
    report_path = si.save_session_report()

    print("\n📊 Session report saved to:")
    print(f"   {report_path}")
    print("\nReport contains:")
    print("   • Session duration and system state")
    print("   • Operational metrics")
    print("   • Active and historical issues")
    print("   • Maintenance recommendations")


def main():
    """Run all demonstration scenarios."""
    logger.info("🧠 System Intelligence Demonstration")
    logger.info("=" * 60)

    try:
        demonstrate_calibration_analysis()
        time.sleep(1)

        demonstrate_signal_quality_monitoring()
        time.sleep(1)

        demonstrate_led_health_tracking()
        time.sleep(1)

        demonstrate_maintenance_recommendations()
        time.sleep(1)

        demonstrate_report_generation()

        print("\n" + "=" * 60)
        print("[OK] Demonstration Complete!")
        print("=" * 60)
        print("\nKey Takeaways:")
        print("  • System Intelligence detects issues automatically")
        print("  • Provides confident, actionable recommendations")
        print("  • Tracks operational metrics over time")
        print("  • Predicts maintenance needs proactively")
        print("  • Generates comprehensive diagnostic reports")
        print("\nIntegrate into your application to enable ML-guided operations!")

    except Exception as e:
        logger.exception(f"Demonstration failed: {e}")


if __name__ == "__main__":
    main()
