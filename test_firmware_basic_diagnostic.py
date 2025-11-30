"""
BASIC FIRMWARE DIAGNOSTIC - V1.3 vs V1.1
Test the most fundamental LED commands one at a time.
"""
import serial
import time

def send_command(ser, cmd):
    """Send command and get response."""
    print(f"\n📤 Sending: {cmd}")
    ser.write(f"{cmd}\n".encode())
    time.sleep(0.1)
    response = ser.readline().decode().strip()
    print(f"📥 Response: {response}")
    return response

def main():
    port = 'COM4'

    print("\n" + "="*70)
    print("BASIC FIRMWARE DIAGNOSTIC - Testing V1.3 LED Commands")
    print("="*70)

    try:
        # Connect
        print(f"\n🔌 Connecting to {port}...")
        ser = serial.Serial(port, 115200, timeout=1)
        time.sleep(2)  # Wait for connection

        # Get firmware version
        print("\n" + "-"*70)
        print("STEP 1: Check Firmware Version")
        print("-"*70)
        print("Firmware V1.2 doesn't have 'info' command")
        print("Checking if device responds...")
        response = send_command(ser, "vv")  # Request verbose mode status
        print(f"\n⚠️  IMPORTANT: You're running V1.2 (NOT V1.3 with PWM fix)")
        print("   If LEDs are misbehaving, this is the BUGGY firmware!")

        input("\nPress ENTER to continue...")

        # Test 1: Turn all OFF
        print("\n" + "-"*70)
        print("TEST 1: Turn ALL LEDs OFF")
        print("-"*70)
        send_command(ser, "lx")
        print("\n👁️  VISUAL CHECK: Are ALL LEDs OFF?")
        result = input("   (y/n): ").strip().lower()
        if result != 'y':
            print("❌ FAILED: lx command not turning off all LEDs")
            print("   This is a critical failure!")
        else:
            print("✅ PASS: All LEDs are OFF")

        input("\nPress ENTER to continue...")

        # Test 2: Turn on Channel A ONLY
        print("\n" + "-"*70)
        print("TEST 2: Turn ON Channel A at 100%")
        print("-"*70)
        send_command(ser, "la(255)")
        print("\n👁️  VISUAL CHECK: Is ONLY Channel A ON?")
        print("   Channel A: Should be ON (bright)")
        print("   Channel B: Should be OFF")
        print("   Channel C: Should be OFF")
        print("   Channel D: Should be OFF")
        result = input("\n   Is ONLY Channel A ON? (y/n): ").strip().lower()
        if result != 'y':
            print("❌ FAILED: la(255) command not working correctly")
            print("   Either Channel A is OFF, or other channels are ON")
        else:
            print("✅ PASS: Only Channel A is ON")

        input("\nPress ENTER to continue...")

        # Test 3: Turn off all again
        print("\n" + "-"*70)
        print("TEST 3: Turn ALL OFF again (after Channel A was ON)")
        print("-"*70)
        send_command(ser, "lx")
        print("\n👁️  VISUAL CHECK: Are ALL LEDs OFF again?")
        result = input("   (y/n): ").strip().lower()
        if result != 'y':
            print("❌ FAILED: lx command not turning off all LEDs after la(255)")
            print("   This is the PWM bug we're trying to fix!")
        else:
            print("✅ PASS: All LEDs are OFF")

        input("\nPress ENTER to continue...")

        # Test 4: Turn on Channel B ONLY
        print("\n" + "-"*70)
        print("TEST 4: Turn ON Channel B at 100%")
        print("-"*70)
        send_command(ser, "lb(255)")
        print("\n👁️  VISUAL CHECK: Is ONLY Channel B ON?")
        print("   Channel A: Should be OFF")
        print("   Channel B: Should be ON (bright)")
        print("   Channel C: Should be OFF")
        print("   Channel D: Should be OFF")
        result = input("\n   Is ONLY Channel B ON? (y/n): ").strip().lower()
        if result != 'y':
            print("❌ FAILED: lb(255) command not working correctly")
        else:
            print("✅ PASS: Only Channel B is ON")

        input("\nPress ENTER to continue...")

        # Test 5: Turn off all
        print("\n" + "-"*70)
        print("TEST 5: Turn ALL OFF (after Channel B)")
        print("-"*70)
        send_command(ser, "lx")
        print("\n👁️  VISUAL CHECK: Are ALL LEDs OFF?")
        result = input("   (y/n): ").strip().lower()
        if result != 'y':
            print("❌ FAILED: lx not working after lb(255)")
        else:
            print("✅ PASS: All LEDs are OFF")

        input("\nPress ENTER to continue...")

        # Test 6: Batch command
        print("\n" + "-"*70)
        print("TEST 6: Batch Command - Turn ON A and C at 50%")
        print("-"*70)
        send_command(ser, "ls(128,0,128,0)")
        print("\n👁️  VISUAL CHECK: Are Channels A and C ON at 50%?")
        print("   Channel A: Should be ON (medium brightness)")
        print("   Channel B: Should be OFF")
        print("   Channel C: Should be ON (medium brightness)")
        print("   Channel D: Should be OFF")
        result = input("\n   Are A and C ON, B and D OFF? (y/n): ").strip().lower()
        if result != 'y':
            print("❌ FAILED: ls batch command not working correctly")
        else:
            print("✅ PASS: Batch command working")

        input("\nPress ENTER to continue...")

        # Test 7: Turn off all after batch
        print("\n" + "-"*70)
        print("TEST 7: Turn ALL OFF (after batch command)")
        print("-"*70)
        send_command(ser, "lx")
        print("\n👁️  VISUAL CHECK: Are ALL LEDs OFF?")
        result = input("   (y/n): ").strip().lower()
        if result != 'y':
            print("❌ FAILED: lx not working after batch command")
        else:
            print("✅ PASS: All LEDs are OFF")

        # Summary
        print("\n" + "="*70)
        print("DIAGNOSTIC COMPLETE")
        print("="*70)
        print("\n⚠️  IMPORTANT QUESTIONS:")
        print("   1. Did you flash V1.3 firmware (with PWM fix)?")
        print("   2. If using V1.3, did the fix make things WORSE?")
        print("   3. Should we revert to V1.1 firmware?")
        print("\n💡 Next steps:")
        print("   - If V1.3 is worse than V1.1, we need to revert")
        print("   - If this is V1.1, we need to compare behavior")
        print("   - We may need to check firmware build process")

        # Clean up
        send_command(ser, "lx")
        ser.close()

    except serial.SerialException as e:
        print(f"\n❌ Serial Error: {e}")
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
