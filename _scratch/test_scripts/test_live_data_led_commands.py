"""
Test LED commands that mimic live data monitoring sequence.
Tests the correct command format for P4PRO (la:xxx) vs P4SPR (baxxx).
"""

import serial
import serial.tools.list_ports
import time


def find_controller():
    """Find P4PRO or P4SPR controller and identify firmware."""
    ports = serial.tools.list_ports.comports()

    for port in ports:
        # Raspberry Pi Pico VID/PID
        if port.vid == 0x2E8A and port.pid == 0x000A:
            try:
                ser = serial.Serial(port.device, 115200, timeout=1)
                time.sleep(0.5)
                ser.reset_input_buffer()

                # Query firmware ID
                ser.write(b"id\n")
                time.sleep(0.1)
                response = ser.read(100).decode('utf-8', errors='ignore').strip()

                print(f"✅ Found device on {port.device}")
                print(f"   Firmware ID: {response}")

                # Determine if P4PRO or P4SPR
                is_p4pro = 'P4PRO' in response
                firmware_type = "P4PRO" if is_p4pro else "P4SPR"

                return ser, is_p4pro, firmware_type

            except Exception as e:
                print(f"⚠️  Error checking {port.device}: {e}")
                continue

    return None, None, None


def test_live_data_led_sequence(ser, is_p4pro, firmware_type):
    """Simulate the LED command sequence used in live data monitoring."""

    print("\n" + "="*70)
    print(f"LIVE DATA MONITORING LED COMMAND TEST - {firmware_type}")
    print("="*70)

    # Define test channels and intensities (simulating calibration values)
    channels = ['a', 'b', 'c', 'd']
    intensities = {
        'a': 224,  # 87.8% brightness
        'b': 192,  # 75.3% brightness
        'c': 160,  # 62.7% brightness
        'd': 128,  # 50.2% brightness
    }

    print(f"\nCommand Format: {'la:xxx (P4PRO)' if is_p4pro else 'baxxx (P4SPR)'}")
    print(f"LED Intensities: A={intensities['a']}, B={intensities['b']}, "
          f"C={intensities['c']}, D={intensities['d']}")

    # Step 1: Set all LED intensities (done once at start of acquisition)
    print("\n[STEP 1] Setting LED intensities (done once at acquisition start)...")
    print("-" * 70)

    ser.reset_input_buffer()

    for ch in channels:
        intensity = intensities[ch]

        if is_p4pro:
            # P4PRO format: la:224\n
            cmd = f"l{ch}:{int(intensity)}\n"
        else:
            # P4SPR format: ba224\n (3-digit zero-padded)
            cmd = f"b{ch}{int(intensity):03d}\n"

        print(f"   Channel {ch.upper()}: Sending {cmd.strip()!r}")
        ser.write(cmd.encode())
        time.sleep(0.005)  # 5ms delay between commands (matches live code)

        # Read response if any
        time.sleep(0.01)
        if ser.in_waiting > 0:
            resp = ser.read(ser.in_waiting)
            print(f"               Response: {resp!r}")

    print("\n✅ All LED intensities set")

    # Step 2: Simulate channel switching during measurement
    print("\n[STEP 2] Simulating channel switching (like live measurements)...")
    print("-" * 70)
    print("   (In real acquisition, we turn channels on/off to measure each LED)")

    for cycle in range(2):  # Do 2 cycles to show the pattern
        print(f"\n   Cycle {cycle + 1}:")

        for ch in channels:
            # Turn on this channel
            print(f"      LED {ch.upper()} ON (measure for 225ms)")
            ser.write(f"l{ch}\n".encode())
            time.sleep(0.225)  # Simulate LED_ON_TIME_MS

            # Turn off all channels
            ser.write(b"lx\n")
            time.sleep(0.045)  # Simulate DETECTOR_WAIT_MS (dark period)

    print("\n✅ Channel switching test complete")

    # Step 3: Turn off all LEDs
    print("\n[STEP 3] Turning off all LEDs...")
    print("-" * 70)
    ser.write(b"lx\n")
    time.sleep(0.05)
    print("   Sent: 'lx' (turn off all channels)")

    if ser.in_waiting > 0:
        resp = ser.read(ser.in_waiting)
        print(f"   Response: {resp!r}")

    print("\n✅ Test complete - all LEDs should be OFF")


def main():
    print("="*70)
    print("LIVE DATA MONITORING LED COMMAND TEST")
    print("="*70)
    print()
    print("This test mimics the exact LED commands used during live data")
    print("monitoring, showing the difference between P4PRO and P4SPR syntax.")
    print()

    # Find controller
    ser, is_p4pro, firmware_type = find_controller()

    if ser is None:
        print("❌ No P4PRO or P4SPR controller found!")
        print("   Make sure device is connected via USB.")
        return

    try:
        # Run test sequence
        test_live_data_led_sequence(ser, is_p4pro, firmware_type)

    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        ser.write(b"lx\n")  # Turn off LEDs

    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()

    finally:
        if ser and ser.is_open:
            ser.write(b"lx\n")  # Ensure LEDs are off
            time.sleep(0.1)
            ser.close()
            print("\n🔌 Serial port closed")


if __name__ == "__main__":
    main()
