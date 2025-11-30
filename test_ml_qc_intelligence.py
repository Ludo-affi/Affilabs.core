"""Test ML QC Intelligence System.

This script tests all 4 ML models with synthetic calibration data.
"""

import sys
sys.path.insert(0, 'src')

from core.ml_qc_intelligence import MLQCIntelligence
from datetime import datetime

def test_ml_qc_intelligence():
    """Test all 4 ML models without full CalibrationData."""

    print("=" * 80)
    print("🧪 TESTING ML QC INTELLIGENCE SYSTEM")
    print("=" * 80)

    # Initialize ML intelligence
    ml_intel = MLQCIntelligence(device_serial="TEST_DEVICE_001")

    print(f"\n✅ ML QC Intelligence initialized")
    print(f"   Device: {ml_intel.device_serial}")
    print(f"   Data directory: {ml_intel.data_dir}")

    # Simulate 10 calibrations with increasing FWHM (sensor degradation)
    print(f"\n📊 Simulating 10 calibrations with sensor degradation...")

    for i in range(10):
        # Increasing FWHM to simulate sensor coating degradation
        # Increasing LED intensity to simulate LED degradation
        cal_record = {
            'timestamp': datetime.now().isoformat(),
            'device_type': 'P4SPR',
            'detector_serial': 'TEST_DEVICE_001',
            'firmware_version': '1.2.0',
            's_integration_time': 93.0,
            'p_integration_time': 93.0,
            's_mode_intensity': {
                'a': 185 + i * 3,
                'b': 210 + i * 4,
                'c': 192 + i * 3,
                'd': 235 + i * 5
            },
            'p_mode_intensity': {
                'a': 190 + i * 3,
                'b': 215 + i * 4,
                'c': 197 + i * 3,
                'd': 240 + i * 5
            },
            'transmission_qc': {
                'a': {
                    'fwhm': 25.0 + i * 2.0,
                    'dip_detected': True,
                    'ratio': 0.65,
                    'status': '✅ PASS' if (25.0 + i * 2.0) < 60 else '❌ FAIL'
                },
                'b': {
                    'fwhm': 27.0 + i * 2.5,
                    'dip_detected': True,
                    'ratio': 0.65,
                    'status': '✅ PASS' if (27.0 + i * 2.5) < 60 else '❌ FAIL'
                },
                'c': {
                    'fwhm': 26.0 + i * 2.2,
                    'dip_detected': True,
                    'ratio': 0.65,
                    'status': '✅ PASS' if (26.0 + i * 2.2) < 60 else '❌ FAIL'
                },
                'd': {
                    'fwhm': 28.0 + i * 3.0,
                    'dip_detected': True,
                    'ratio': 0.65,
                    'status': '✅ PASS' if (28.0 + i * 3.0) < 60 else '❌ FAIL'
                }
            },
            'failed': False if i < 8 else True  # Last 2 calibrations fail
        }

        # Add to history directly
        ml_intel.calibration_history.append(cal_record)

        avg_fwhm = sum(cal_record['transmission_qc'][ch]['fwhm'] for ch in ['a', 'b', 'c', 'd']) / 4
        print(f"   Calibration {i+1}: FWHM avg = {avg_fwhm:.1f}nm, LED max = {cal_record['p_mode_intensity']['d']}")

    print(f"\n✅ {len(ml_intel.calibration_history)} calibrations loaded")

    # Test Model 1: Calibration Quality Prediction
    print(f"\n" + "=" * 80)
    print(f"📊 MODEL 1: CALIBRATION QUALITY PREDICTION")
    print(f"=" * 80)

    cal_pred = ml_intel.predict_next_calibration()
    print(f"Failure Probability: {cal_pred.failure_probability*100:.1f}%")
    print(f"Risk Level: {cal_pred.risk_level.upper()}")
    print(f"Confidence: {cal_pred.confidence*100:.0f}%")
    print(f"\nPredicted FWHM:")
    for ch, fwhm in cal_pred.predicted_fwhm.items():
        print(f"  Ch {ch.upper()}: {fwhm:.1f} nm")

    if cal_pred.warnings:
        print(f"\n⚠️  Warnings:")
        for w in cal_pred.warnings:
            print(f"  • {w}")

    print(f"\n💡 Recommendations:")
    for r in cal_pred.recommendations:
        print(f"  • {r}")

    # Test Model 2: LED Health Monitoring
    print(f"\n" + "=" * 80)
    print(f"💡 MODEL 2: LED HEALTH STATUS")
    print(f"=" * 80)

    led_statuses = ml_intel.predict_led_health()
    for led in led_statuses:
        status_emoji = {
            'excellent': '✅',
            'good': '✅',
            'degrading': '⚠️',
            'critical': '🚨'
        }.get(led.status, '❓')

        print(f"{status_emoji} Channel {led.channel.upper()}: {led.status.upper()}")
        print(f"   Intensity: {led.current_intensity}/255")
        print(f"   Trend: {led.intensity_trend:+.1f}/calibration")
        print(f"   Health Score: {led.health_score*100:.0f}%")
        if led.days_until_replacement:
            print(f"   Days Until Replacement: {led.days_until_replacement}")
        if led.replacement_recommended:
            print(f"   🚨 REPLACEMENT RECOMMENDED")

    # Test Model 3: Sensor Coating Degradation
    print(f"\n" + "=" * 80)
    print(f"🔬 MODEL 3: SENSOR COATING STATUS")
    print(f"=" * 80)

    coating = ml_intel.predict_sensor_coating_life()
    quality_emoji = {
        'excellent': '✅',
        'good': '✅',
        'acceptable': '⚠️',
        'poor': '❌'
    }.get(coating.coating_quality, '❓')

    print(f"{quality_emoji} Quality: {coating.coating_quality.upper()}")
    print(f"Current FWHM (avg): {coating.current_fwhm_avg:.1f} nm")
    print(f"FWHM Trend: {coating.fwhm_trend:+.2f} nm/calibration")
    if coating.estimated_experiments_remaining:
        print(f"Estimated Lifespan: {coating.estimated_experiments_remaining} experiments")
    print(f"Confidence: {coating.confidence*100:.0f}%")
    if coating.replacement_warning:
        print(f"⚠️  REPLACEMENT WARNING: Sensor approaching end of life")

    # Test Model 4: Optical Alignment (Baseline-based)
    print(f"\n" + "=" * 80)
    print(f"🔧 MODEL 4: OPTICAL ALIGNMENT (BASELINE MONITOR)")
    print(f"=" * 80)
    print(f"Note: Uses CALIBRATION baseline only, not real-time SPR data\n")

    # Simulate alignment baseline building
    for i in range(15):
        ps_ratio = 0.65 + (i * 0.002)  # Slight drift over time
        ml_intel._update_alignment_baseline(ps_ratio)

    print(f"Baseline P/S Ratios: {len(ml_intel.alignment_baseline)} calibrations")
    print(f"Baseline Mean: {sum(ml_intel.alignment_baseline)/len(ml_intel.alignment_baseline):.3f}")
    print(f"Baseline Std: {(sum((x - sum(ml_intel.alignment_baseline)/len(ml_intel.alignment_baseline))**2 for x in ml_intel.alignment_baseline) / len(ml_intel.alignment_baseline))**0.5:.3f}")
    print(f"✅ Baseline established - ready for drift detection")

    # Generate full intelligence report
    print(f"\n" + "=" * 80)
    print(f"📋 COMPREHENSIVE INTELLIGENCE REPORT")
    print(f"=" * 80)

    report = ml_intel.generate_intelligence_report()
    print(report)

    print(f"\n" + "=" * 80)
    print(f"✅ ML QC INTELLIGENCE TEST COMPLETE")
    print(f"=" * 80)
    print(f"\n💾 Test data saved to: {ml_intel.data_dir}")

if __name__ == "__main__":
    test_ml_qc_intelligence()
