"""
LED Current Measurement Script
Measures actual LED current draw at 100% PWM to verify PCB current limiting

This helps determine if firmware PWM caps are needed to protect LEDs.

REQUIRED HARDWARE:
- Multimeter in DC current mode (200mA range)
- Multimeter connected in SERIES with LED power line

SAFETY:
- Do NOT exceed 180mA for any LED (absolute maximum)
- If any LED draws >60mA for LCW type, reduce PWM cap in firmware
- If any LED draws >180mA, STOP IMMEDIATELY - hardware issue!
"""

import time
import sys
import serial
import serial.tools.list_ports

# Simple controller wrapper to avoid import issues
class SimpleController:
    def __init__(self, port='COM4', baud=115200):
        self.port = port
        self.baud = baud
        self._ser = None

    def open(self):
        try:
            self._ser = serial.Serial(self.port, self.baud, timeout=1)
            time.sleep(2)  # Wait for connection
            return True
        except Exception as e:
            print(f"Error opening port: {e}")
            return False

    def close(self):
        if self._ser:
            self._ser.close()

    def turn_off_channels(self):
        if self._ser:
            self._ser.write(b'lx\n')
            self._ser.read(1)  # Read ACK

    def set_intensity(self, ch, value):
        if self._ser:
            cmd = f"b{ch}{value:03d}\n".encode()
            self._ser.write(cmd)
            self._ser.read(1)  # Read ACK

    def turn_on_channel(self, ch):
        if self._ser:
            cmd = f"l{ch}\n".encode()
            self._ser.write(cmd)
            self._ser.read(1)  # Read ACK

def print_header():
    print("\n" + "="*70)
    print("LED CURRENT MEASUREMENT TEST")
    print("="*70)
    print("\nThis test turns on each LED at 100% brightness.")
    print("You MUST measure the current with a multimeter in series with the LED.")
    print("\n⚠️  SAFETY: Stop immediately if any LED exceeds 180mA!")
    print("="*70 + "\n")

def measure_channel(controller, channel):
    """Turn on a channel and prompt user to measure current"""
    ch_upper = channel.upper()

    print(f"\n{'='*70}")
    print(f"CHANNEL {ch_upper} MEASUREMENT")
    print(f"{'='*70}")

    # Turn off all LEDs first
    controller.turn_off_channels()
    time.sleep(0.5)

    print(f"\n1. Setting Channel {ch_upper} to 100% brightness...")
    controller.set_intensity(channel, 255)
    controller.turn_on_channel(channel)
    time.sleep(1.0)

    print(f"\n2. 🔌 Connect multimeter in SERIES with Channel {ch_upper} LED power")
    print(f"   Set multimeter to DC current mode (200mA range)")
    print(f"   LED should be ON at full brightness")

    input(f"\n3. Press Enter when multimeter is connected and reading is stable...")

    print(f"\n4. 📊 READ THE CURRENT NOW from your multimeter")
    current = input(f"   Enter measured current for Channel {ch_upper} in mA: ").strip()

    try:
        current_ma = float(current)

        # Safety warnings
        if current_ma > 180:
            print(f"\n🔴 DANGER! Channel {ch_upper} current = {current_ma}mA (>180mA absolute max)")
            print(f"   STOP TESTING! Hardware current limiting insufficient!")
            print(f"   Risk of LED damage!")
            return None
        elif current_ma > 60:
            print(f"\n⚠️  WARNING: Channel {ch_upper} current = {current_ma}mA (>60mA)")
            print(f"   If this is a LCW LED, firmware PWM cap needed!")
        else:
            print(f"\n✅ Channel {ch_upper} current = {current_ma}mA (safe)")

        return current_ma

    except ValueError:
        print(f"\n❌ Invalid input. Please enter a number (e.g., 45.2)")
        return None
    finally:
        # Turn off LED
        controller.turn_off_channels()
        time.sleep(0.5)

def identify_led_type(channel):
    """Ask user which LED type is on this channel"""
    ch_upper = channel.upper()

    print(f"\n📋 Which LED type is installed on Channel {ch_upper}?")
    print("   1. LCW (Luminus MP-2016, smaller, ~11 lumens)")
    print("   2. OWW (OSRAM GW JTLMS3, larger, ~60 lumens)")

    choice = input(f"   Enter 1 or 2: ").strip()

    if choice == '1':
        return 'LCW'
    elif choice == '2':
        return 'OWW'
    else:
        return 'Unknown'

def analyze_results(results):
    """Analyze measurements and provide firmware recommendations"""
    print("\n" + "="*70)
    print("MEASUREMENT SUMMARY & FIRMWARE RECOMMENDATIONS")
    print("="*70)

    print("\n📊 Measured Currents:")
    print("-" * 70)
    print(f"{'Channel':<10} {'LED Type':<10} {'Current (mA)':<15} {'Status':<20} {'Action'}")
    print("-" * 70)

    needs_firmware_cap = False
    hardware_issue = False

    for ch, data in results.items():
        if data['current'] is None:
            continue

        current = data['current']
        led_type = data['led_type']

        # Determine status
        if current > 180:
            status = "🔴 DANGER"
            action = "STOP - Hardware fix needed"
            hardware_issue = True
        elif led_type == 'LCW' and current > 60:
            status = "⚠️  Over LCW max"
            action = "Firmware PWM cap needed"
            needs_firmware_cap = True
        elif led_type == 'OWW' and current > 180:
            status = "⚠️  Over OWW max"
            action = "Firmware PWM cap needed"
            needs_firmware_cap = True
        elif current > 60:
            status = "⚠️  High current"
            action = "Check LED type"
        else:
            status = "✅ Safe"
            action = "None"

        print(f"{ch:<10} {led_type:<10} {current:<15.1f} {status:<20} {action}")

    print("-" * 70)

    # Overall recommendation
    print("\n🎯 OVERALL RECOMMENDATION:")
    print("="*70)

    if hardware_issue:
        print("\n🔴 CRITICAL: HARDWARE CURRENT LIMITING INSUFFICIENT!")
        print("   One or more LEDs exceed absolute maximum current (180mA)")
        print("   DO NOT OPERATE until current-limiting resistors are fixed")
        print("   This cannot be fixed in firmware alone - hardware redesign needed")

    elif needs_firmware_cap:
        print("\n⚠️  FIRMWARE PWM CAPS REQUIRED")
        print("   One or more LEDs exceed their safe operating current")
        print("\n   Required firmware changes in affinite_p4spr.c:")
        print("\n   1. Add per-channel PWM limits after line 99:")
        print("      ```c")

        for ch, data in results.items():
            if data['current'] is None:
                continue

            current = data['current']
            led_type = data['led_type']

            # Calculate safe PWM cap
            if led_type == 'LCW':
                target_current = 50  # 50mA safe for LCW (60mA max)
            else:
                target_current = 150  # 150mA safe for OWW (180mA max)

            pwm_cap = min(1.0, target_current / current)

            print(f"      const float LED_{ch.upper()}_MAX_DUTY = {pwm_cap:.2f};  // {led_type} LED, limit {current:.0f}mA → {target_current}mA")

        print("      ```")
        print("\n   2. Apply limits in led_brightness() function (see LED_HARDWARE_SPECIFICATIONS.md)")
        print("\n   3. Recompile and flash firmware")

    else:
        print("\n✅ NO FIRMWARE CHANGES NEEDED!")
        print("   All LEDs operate within safe current limits")
        print("   PCB current limiting is working correctly")
        print("   Brightness differences handled automatically by Python calibration")
        print("\n   You can proceed with:")
        print("   1. Firmware testing (test_firmware_led_control.py)")
        print("   2. Firmware compilation (if testing V1.2 confirms bug)")
        print("   3. Flashing and validation (test again with V1.3)")

    print("="*70 + "\n")

def main():
    """Main measurement workflow"""
    print_header()

    input("Press Enter to start LED current measurements...")

    # Connect to controller
    print("\nConnecting to PicoP4SPR controller...")
    try:
        controller = SimpleController(port='COM4', baud=115200)
        if not controller.connect():
            print("❌ Failed to connect to controller on COM4")
            print("   Check USB connection and COM port")
            return False

        print("✅ Controller connected")

    except Exception as e:
        print(f"❌ Error connecting to controller: {e}")
        return False

    # Measure each channel
    results = {}

    for channel in ['a', 'b', 'c', 'd']:
        current = measure_channel(controller, channel)

        if current is None:
            print(f"\n⚠️  Skipping Channel {channel.upper()} (invalid measurement)")
            results[channel.upper()] = {'current': None, 'led_type': 'Unknown'}
            continue

        led_type = identify_led_type(channel)
        results[channel.upper()] = {'current': current, 'led_type': led_type}

        # Safety check after each measurement
        if current > 180:
            print(f"\n🔴 CRITICAL: Channel {channel.upper()} exceeds 180mA!")
            print("   STOPPING TEST for safety")
            break

    # Clean up
    try:
        controller.turn_off_channels()
        controller.close()
    except:
        pass

    # Analyze and provide recommendations
    analyze_results(results)

    return True

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
