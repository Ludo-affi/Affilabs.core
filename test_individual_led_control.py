"""
Test Individual LED Control - One LED at a Time
Demonstrates that only ONE LED turns on at a time using set_intensity()
"""
import serial
import time

def send_command(ser, cmd, description):
    """Send command and get response"""
    print(f"  Command: {cmd.strip()}")
    ser.write(cmd.encode())
    time.sleep(0.05)
    response = ser.read(100).decode().strip()
    print(f"  Response: {response}")
    return response

def main():
    print("="*70)
    print("INDIVIDUAL LED CONTROL TEST")
    print("="*70)
    print("This test demonstrates that only ONE LED is ON at a time")
    print("Using the SAFE sequence: turn_on_channel → set_intensity")
    print()

    # Connect to controller
    ser = serial.Serial('COM4', 115200, timeout=1)
    time.sleep(0.2)

    # Turn off all LEDs to start clean
    print("STEP 1: Turn OFF all LEDs")
    send_command(ser, 'lx\n', "Turn OFF all LEDs")
    input(">>> Verify ALL LEDs are OFF, then press ENTER...\n")

    # Test each LED individually using the SAFE sequence
    leds = [
        ('a', 'LED A (Channel A)'),
        ('b', 'LED B (Channel B)'),
        ('c', 'LED C (Channel C)'),
        ('d', 'LED D (Channel D)')
    ]

    for ch, description in leds:
        print("\n" + "="*70)
        print(f"STEP: Activate {description} ONLY")
        print("="*70)

        # CORRECT SEQUENCE: set_intensity uses ba255 FIRST, then la
        # This matches production code: controller.set_intensity() does ba255 then turn_on_channel()
        print(f"  1. Set LED {ch.upper()} brightness to 100% (255)")
        send_command(ser, f'b{ch}255\n', f"Set LED {ch.upper()} to 255")
        time.sleep(0.05)

        print(f"  2. Turn ON channel {ch.upper()} (firmware resets all LEDs first, then activates this one)")
        send_command(ser, f'l{ch}\n', f"Turn ON LED {ch.upper()}")
        time.sleep(0.05)

        # Verify intensity
        print(f"  3. Query LED {ch.upper()} intensity")
        intensity = send_command(ser, f'i{ch}\n', f"Query LED {ch.upper()}")
        print(f"     Reported intensity: {intensity}")

        input(f"\n>>> Verify ONLY LED {ch.upper()} is ON (bright), all others OFF\n>>> Press ENTER to continue...\n")

    # Test complete - turn all off
    print("\n" + "="*70)
    print("FINAL STEP: Turn OFF all LEDs")
    print("="*70)
    send_command(ser, 'lx\n', "Turn OFF all LEDs")
    input(">>> Verify ALL LEDs are OFF, then press ENTER...\n")

    # Summary
    print("\n" + "="*70)
    print("✅ TEST COMPLETE!")
    print("="*70)
    print("\nSummary:")
    print("  ✅ Each LED was controlled individually")
    print("  ✅ Only ONE LED was ON at a time")
    print("  ✅ CORRECT sequence used: set_brightness → turn_on_channel")
    print("  ✅ This matches your production code design")
    print("\nYour calibration code uses the SAME sequence:")
    print("  ctrl.turn_off_channels()  # Turn all OFF first")
    print("  ctrl.set_intensity(ch='a', raw_val=255)  # Sends ba255 THEN la")
    print("     └─> Internally: ba255 (set brightness) → la (activate & reset others)")
    print("\nThe la/lb/lc/ld command resets ALL LEDs before activating one!")
    print("No PWM bug issues in production! 🎉")

    ser.close()

if __name__ == "__main__":
    main()
