"""Servo Calibration Tool for P4SPR V1.8
Calibrates S and P positions with adjustable servo speed
"""

import json
import time
from pathlib import Path

import serial


class ServoCalibrator:
    """Calibrate servo positions for S and P mode polarization."""

    def __init__(self, com_port: str = "COM5"):
        self.com_port = com_port
        self.ser = None
        self.current_s = 90  # Default S position
        self.current_p = 90  # Default P position
        self.servo_speed = 100  # Default speed (ms)

    def connect(self):
        """Connect to P4SPR device."""
        try:
            self.ser = serial.Serial(self.com_port, 115200, timeout=1)
            time.sleep(0.5)

            # Verify connection
            self.ser.reset_input_buffer()
            self.ser.write(b"id\n")
            time.sleep(0.1)
            response = self.ser.readline().decode(errors="ignore").strip()

            if "P4SPR" in response:
                print(f"✅ Connected: {response}")
                return True
            print(f"❌ Unexpected response: {response}")
            return False

        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False

    def disconnect(self):
        """Disconnect from device."""
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("Disconnected")

    def set_servo_speed(self, speed_ms: int):
        """Set servo movement speed.

        Args:
            speed_ms: Speed in milliseconds (50-5000)
                     Lower = faster, Higher = slower

        """
        speed_ms = max(speed_ms, 50)
        speed_ms = min(speed_ms, 5000)

        cmd = f"servo_speed:{speed_ms}\n"
        self.ser.write(cmd.encode())
        time.sleep(0.1)

        response = self.ser.read(10)
        if b"\x01" in response:
            self.servo_speed = speed_ms
            print(f"✅ Servo speed: {speed_ms} ms")
            return True
        print("❌ Failed to set speed")
        return False

    def move_to_s(self):
        """Move servo to S position."""
        self.ser.write(b"ss\n")
        time.sleep(0.1)
        response = self.ser.read(10)
        if b"\x01" in response:
            print(f"→ S position ({self.current_s}°)")
            return True
        return False

    def move_to_p(self):
        """Move servo to P position."""
        self.ser.write(b"sp\n")
        time.sleep(0.1)
        response = self.ser.read(10)
        if b"\x01" in response:
            print(f"→ P position ({self.current_p}°)")
            return True
        return False

    def set_positions(self, s_deg: int, p_deg: int):
        """Set S and P positions (0-180 degrees).

        Args:
            s_deg: S position in degrees (0-180)
            p_deg: P position in degrees (0-180)

        """
        if s_deg < 0 or s_deg > 180:
            print("❌ S position must be 0-180")
            return False
        if p_deg < 0 or p_deg > 180:
            print("❌ P position must be 0-180")
            return False

        # Format: sv followed by 3 digits for S, 3 digits for P
        cmd = f"sv{s_deg:03d}{p_deg:03d}\n"
        self.ser.write(cmd.encode())
        time.sleep(0.1)

        response = self.ser.read(10)
        if b"\x01" in response:
            self.current_s = s_deg
            self.current_p = p_deg
            print(f"✅ Set S={s_deg}°, P={p_deg}°")
            return True
        print("❌ Failed to set positions")
        return False

    def save_to_eeprom(self):
        """Save current S/P positions to EEPROM."""
        self.ser.write(b"sf\n")
        time.sleep(0.2)
        response = self.ser.read(10)
        if b"\x01" in response:
            print(f"💾 Saved to EEPROM: S={self.current_s}°, P={self.current_p}°")
            return True
        print("❌ Failed to save")
        return False

    def read_from_eeprom(self):
        """Read saved S/P positions from EEPROM."""
        self.ser.reset_input_buffer()
        self.ser.write(b"sr\n")
        time.sleep(0.1)

        response = self.ser.readline().decode(errors="ignore").strip()
        if "," in response:
            try:
                s_val, p_val = response.split(",")
                s_deg = int(s_val)
                p_deg = int(p_val)
                print(f"📖 EEPROM: S={s_deg}°, P={p_deg}°")
                return s_deg, p_deg
            except:
                print(f"⚠️ Could not parse EEPROM data: {response}")
        return None, None

    def interactive_calibration(self):
        """Interactive calibration workflow."""
        print("\n" + "=" * 60)
        print("Servo Calibration - P4SPR V1.8")
        print("=" * 60 + "\n")

        # Check current EEPROM values
        print("Reading current EEPROM values...")
        saved_s, saved_p = self.read_from_eeprom()
        if saved_s is not None:
            self.current_s = saved_s
            self.current_p = saved_p

        # Set servo speed
        print("\n1. Set Servo Speed")
        print("   (Lower = faster, Higher = slower)")
        speed = input(
            f"   Enter speed in ms (50-5000) [current: {self.servo_speed}]: ",
        ).strip()
        if speed:
            try:
                self.set_servo_speed(int(speed))
            except:
                print("   Keeping current speed")

        # Calibrate S position
        print("\n2. Calibrate S Position (Sample mode)")
        while True:
            s_input = input(
                f"   Enter S position (0-180) [current: {self.current_s}]: ",
            ).strip()
            if not s_input:
                break

            try:
                s_deg = int(s_input)
                self.set_positions(s_deg, self.current_p)
                self.move_to_s()

                confirm = input("   Test movement? (y/n): ")
                if confirm.lower() == "y":
                    print("   S → P → S")
                    self.move_to_s()
                    time.sleep(0.5)
                    self.move_to_p()
                    time.sleep(0.5)
                    self.move_to_s()

                done = input("   S position OK? (y/n): ")
                if done.lower() == "y":
                    break
            except:
                print("   Invalid input")

        # Calibrate P position
        print("\n3. Calibrate P Position (Polarized mode)")
        while True:
            p_input = input(
                f"   Enter P position (0-180) [current: {self.current_p}]: ",
            ).strip()
            if not p_input:
                break

            try:
                p_deg = int(p_input)
                self.set_positions(self.current_s, p_deg)
                self.move_to_p()

                confirm = input("   Test movement? (y/n): ")
                if confirm.lower() == "y":
                    print("   P → S → P")
                    self.move_to_p()
                    time.sleep(0.5)
                    self.move_to_s()
                    time.sleep(0.5)
                    self.move_to_p()

                done = input("   P position OK? (y/n): ")
                if done.lower() == "y":
                    break
            except:
                print("   Invalid input")

        # Final test
        print("\n4. Final Test")
        test = input("   Run full S/P cycle test? (y/n): ")
        if test.lower() == "y":
            print("\n   Running 3 cycles: S → P → S → P → S → P → S")
            for i in range(3):
                print(f"   Cycle {i+1}/3: S → P")
                self.move_to_s()
                time.sleep(1)
                self.move_to_p()
                time.sleep(1)
            self.move_to_s()
            print("   ✅ Test complete")

        # Save to EEPROM
        print("\n5. Save Configuration")
        print(
            f"   Current: S={self.current_s}°, P={self.current_p}°, Speed={self.servo_speed}ms",
        )
        save = input("   Save to EEPROM? (y/n): ")
        if save.lower() == "y":
            self.save_to_eeprom()

        # Save to file
        config_file = Path("servo_calibration.json")
        save_file = input(f"\n   Save to {config_file}? (y/n): ")
        if save_file.lower() == "y":
            config = {
                "s_position": self.current_s,
                "p_position": self.current_p,
                "servo_speed_ms": self.servo_speed,
                "com_port": self.com_port,
            }
            with open(config_file, "w") as f:
                json.dump(config, f, indent=2)
            print(f"   💾 Saved to {config_file}")

        print("\n" + "=" * 60)
        print("Calibration Complete!")
        print("=" * 60 + "\n")


def main():
    """Run servo calibration."""
    calibrator = ServoCalibrator("COM5")

    if calibrator.connect():
        try:
            calibrator.interactive_calibration()
        finally:
            calibrator.disconnect()
    else:
        print("Could not connect to P4SPR device")


if __name__ == "__main__":
    main()
