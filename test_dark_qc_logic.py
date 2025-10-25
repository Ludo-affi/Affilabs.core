"""
Test script to verify Step 5 dark noise QC logic
This simulates the QC check without running full calibration
"""

# Simulate QC parameters (from spr_calibrator.py)
EXPECTED_DARK_MEAN_OCEAN_OPTICS = 3000.0  # Ocean Optics detector baseline
DARK_QC_THRESHOLD = EXPECTED_DARK_MEAN_OCEAN_OPTICS * 2.0  # 6,000 counts
MAX_RETRY_ATTEMPTS = 3

def test_dark_qc(dark_mean_values):
    """Simulate dark noise QC check with retry logic

    Args:
        dark_mean_values: List of dark noise mean values for each attempt
    """
    print("\n" + "="*80)
    print(f"TESTING DARK NOISE QC")
    print(f"Expected: {EXPECTED_DARK_MEAN_OCEAN_OPTICS:.0f} counts (Ocean Optics detector)")
    print(f"Threshold: {DARK_QC_THRESHOLD:.0f} counts (2× expected)")
    print("="*80)

    for attempt, dark_mean in enumerate(dark_mean_values, start=1):
        print(f"\n🔄 Attempt {attempt}/{MAX_RETRY_ATTEMPTS}")
        print(f"   Measured dark noise: {dark_mean:.1f} counts")

        if dark_mean > DARK_QC_THRESHOLD:
            print(f"   ❌ QC FAILED: {dark_mean:.1f} > {DARK_QC_THRESHOLD:.0f}")
            print(f"   ({dark_mean/EXPECTED_DARK_MEAN_OCEAN_OPTICS:.1f}× higher than expected)")

            if attempt < MAX_RETRY_ATTEMPTS:
                print(f"   → Retrying with longer LED settle time...")
                continue
            else:
                print(f"\n❌ FATAL: Dark noise QC failed after {MAX_RETRY_ATTEMPTS} attempts")
                print("   Calibration cannot proceed!")
                return False
        else:
            print(f"   ✅ QC PASSED: {dark_mean:.1f} < {DARK_QC_THRESHOLD:.0f}")
            if attempt > 1:
                print(f"   (Succeeded on retry attempt {attempt})")
            return True

    return False


# Test Cases
print("\n" + "#"*80)
print("TEST CASE 1: Normal Operation (LEDs properly off)")
print("#"*80)
# Dark noise is normal on first attempt
result1 = test_dark_qc([2847.3])
print(f"\n✅ Result: {'PASSED' if result1 else 'FAILED'}")


print("\n\n" + "#"*80)
print("TEST CASE 2: Slow LED Decay (needs longer settle time)")
print("#"*80)
# First attempt: LEDs not fully off (7,234 counts > 6,000)
# Second attempt: Better but still high (5,892 counts < 6,000)
result2 = test_dark_qc([7234.2, 5892.1])
print(f"\n✅ Result: {'PASSED' if result2 else 'FAILED'}")


print("\n\n" + "#"*80)
print("TEST CASE 3: LED Stuck On (fatal error)")
print("#"*80)
# All attempts fail - LED physically stuck on
result3 = test_dark_qc([8523.4, 8312.7, 8198.1])
print(f"\n❌ Result: {'PASSED' if result3 else 'FAILED'}")


print("\n\n" + "#"*80)
print("TEST CASE 4: Light Leak (progressive improvement but still fails)")
print("#"*80)
# Each attempt improves but never reaches threshold
result4 = test_dark_qc([12000.0, 9500.0, 7200.0])
print(f"\n❌ Result: {'PASSED' if result4 else 'FAILED'}")


print("\n\n" + "#"*80)
print("TEST CASE 5: Borderline Pass (just under threshold on retry)")
print("#"*80)
# First attempt fails, second attempt barely passes
result5 = test_dark_qc([6500.0, 5950.0])
print(f"\n✅ Result: {'PASSED' if result5 else 'FAILED'}")


print("\n\n" + "="*80)
print("SUMMARY")
print("="*80)
print("""
The QC system will:
1. ✅ Pass immediately if dark < 6,000 counts (normal operation)
2. ✅ Retry up to 3 times with longer LED-off delays
3. ❌ Fail calibration if all 3 attempts exceed threshold
4. 📊 Log detailed diagnostics for troubleshooting

This protects against:
• LEDs not completely turned off
• Light leaking into detector
• Previous measurement residual signal
• Hardware malfunctions

Detector-specific threshold: 6,000 counts for Ocean Optics/USB4000 class
""")
