"""Test 6-Step Calibration - Steps 1-4
Tests the right functions and commands for the first 4 calibration steps.
"""

import time

import serial


def send_command(ser, cmd, description):
    """Send command and get response"""
    print(f"\n{description}")
    print(f"  Command: {cmd.strip()}")
    ser.write(cmd.encode())
    time.sleep(0.1)
    response = ser.read(100).decode().strip()
    print(f"  Response: {response}")
    return response


def main():
    print("=" * 70)
    print("6-STEP CALIBRATION TEST - STEPS 1-4")
    print("=" * 70)

    # Connect to controller
    ser = serial.Serial("COM4", 115200, timeout=1)
    time.sleep(0.2)

    # Verify firmware version
    print("\n📌 FIRMWARE CHECK")
    send_command(ser, "iv\n", "Check firmware version")
    send_command(ser, "id\n", "Check device ID")

    print("\n" + "=" * 70)
    print("STEP 1: DARK MEASUREMENT (Blank)")
    print("=" * 70)
    print("Purpose: Measure background signal with NO LEDs on")
    print("Command sequence: Turn off all LEDs → Measure dark spectrum")

    # Turn off all LEDs
    response = send_command(ser, "lx\n", "Turn OFF all LEDs")
    if response == "1":
        print("  ✅ All LEDs OFF - Ready for dark measurement")
    else:
        print("  ❌ LED OFF command failed!")

    input("\n>>> Visually verify ALL LEDs are OFF, then press ENTER to continue...")
    print("  → Now measure spectrum with spectrometer (this is your DARK)")
    input(">>> Press ENTER when dark measurement complete...")

    print("\n" + "=" * 70)
    print("STEP 2: WHITE REFERENCE (Sample holder EMPTY)")
    print("=" * 70)
    print("Purpose: Measure light through empty sample holder")
    print("Command sequence: Turn ON LED A FIRST → Set brightness to 100%")

    # CRITICAL: Turn on LED FIRST (resets all LEDs), THEN set intensity
    # This matches production code and avoids PWM bug
    response = send_command(ser, "la\n", "Turn ON LED A (resets all LEDs first)")
    time.sleep(0.05)
    send_command(ser, "ba255\n", "Set LED A brightness to 100% (255)")

    if response == "1":
        print("  ✅ LED A ON at 100% brightness")
    else:
        print("  ❌ LED A command failed!")

    input("\n>>> Visually verify ONLY LED A is ON (bright), then press ENTER...")
    print("  → Ensure sample holder is EMPTY")
    print("  → Now measure spectrum (this is your WHITE REFERENCE)")
    input(">>> Press ENTER when white reference measurement complete...")

    print("\n" + "=" * 70)
    print("STEP 3: SAMPLE MEASUREMENT")
    print("=" * 70)
    print("Purpose: Measure light through actual sample")
    print("LED remains at same intensity as Step 2")

    print("  ℹ️  LED A should still be ON from Step 2")
    query_response = send_command(ser, "ia\n", "Query LED A intensity")
    print(f"  Current LED A intensity: {query_response}")

    input("\n>>> Insert SAMPLE into holder, then press ENTER...")
    print("  → Now measure spectrum through sample")
    input(">>> Press ENTER when sample measurement complete...")

    print("\n" + "=" * 70)
    print("STEP 4: VERIFY LED OFF")
    print("=" * 70)
    print("Purpose: Turn off LED after measurement complete")

    response = send_command(ser, "lx\n", "Turn OFF all LEDs")
    if response == "1":
        print("  ✅ All LEDs OFF")
    else:
        print("  ❌ LED OFF command failed!")

    input("\n>>> Visually verify ALL LEDs are OFF, then press ENTER...")

    # Verify LED is actually off
    query_response = send_command(ser, "ia\n", "Query LED A intensity")
    print(f"  LED A intensity after lx: {query_response}")

    print("\n" + "=" * 70)
    print("✅ STEPS 1-4 COMPLETE!")
    print("=" * 70)

    print("\nSummary:")
    print("  Step 1: Dark measurement (all LEDs OFF)")
    print("  Step 2: White reference (LED A ON, empty holder)")
    print("  Step 3: Sample measurement (LED A ON, sample in holder)")
    print("  Step 4: LEDs turned OFF")

    print("\nNext steps would be:")
    print("  Step 5: Repeat 2-4 for LED B")
    print("  Step 6: Repeat 2-4 for LED C")

    print("\n" + "=" * 70)
    print("CRITICAL TEST: PWM Bug Check")
    print("=" * 70)
    print("Testing if LED A stayed OFF after Step 4...")

    result = input("Is LED A completely OFF? (yes/no): ").strip().lower()
    if result == "yes":
        print("✅ NO PWM BUG - LED properly turned off!")
        print("   The la/lx command sequence is working correctly")
    else:
        print("❌ PWM BUG DETECTED - LED still ON!")
        print("   This should NOT happen with your code design")

    ser.close()
    print("\nTest complete.")


if __name__ == "__main__":
    main()
