"""
P4PROPLUS Internal Pump Calibration Tool

This tool helps calibrate:
1. Flow rate accuracy (actual vs commanded) for each pump
2. Correction factors for individual pump variations
3. RPM to volume/time mapping for contact time targeting

Calibration Process:
- Run pump at known RPM for known time
- Measure actual volume delivered (by weight or graduated cylinder)
- Calculate actual flow rate and correction factor
- Repeat for multiple flow rates and both pumps
- Save calibration data for use in main application
"""

import sys
from pathlib import Path
import json
from datetime import datetime

# Add affilabs to path
sys.path.insert(0, str(Path(__file__).parent))

from affilabs.utils.controller import PicoP4PRO


class PumpCalibration:
    """Manage pump calibration data."""
    
    def __init__(self):
        self.calibration_file = Path.home() / ".affilabs" / "p4proplus_pump_calibration.json"
        self.calibration_data = self.load_calibration()
    
    def load_calibration(self):
        """Load existing calibration data."""
        if self.calibration_file.exists():
            try:
                with open(self.calibration_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[WARN] Could not load calibration: {e}")
        
        # Default calibration
        return {
            "created": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "pump1": {
                "ul_per_revolution": 3.0,  # Default from spec
                "correction_factor": 1.0,   # Multiply commanded rate by this
                "calibration_points": []    # List of {rpm, measured_ul_min, correction}
            },
            "pump2": {
                "ul_per_revolution": 3.0,
                "correction_factor": 1.0,
                "calibration_points": []
            }
        }
    
    def save_calibration(self):
        """Save calibration data."""
        try:
            self.calibration_file.parent.mkdir(exist_ok=True)
            self.calibration_data["last_updated"] = datetime.now().isoformat()
            with open(self.calibration_file, 'w') as f:
                json.dump(self.calibration_data, f, indent=2)
            print(f"[OK] Calibration saved to {self.calibration_file}")
        except Exception as e:
            print(f"[ERROR] Could not save calibration: {e}")
    
    def add_calibration_point(self, pump_ch, rpm, duration_sec, measured_volume_ul):
        """Add a calibration data point."""
        pump_key = f"pump{pump_ch}"
        
        # Calculate actual flow rate
        measured_ul_min = (measured_volume_ul / duration_sec) * 60.0
        
        # Calculate what we commanded
        ul_per_rev = self.calibration_data[pump_key]["ul_per_revolution"]
        commanded_ul_min = rpm * ul_per_rev
        
        # Calculate correction factor for this point
        correction = measured_ul_min / commanded_ul_min if commanded_ul_min > 0 else 1.0
        
        point = {
            "rpm": rpm,
            "duration_sec": duration_sec,
            "measured_volume_ul": measured_volume_ul,
            "measured_ul_min": round(measured_ul_min, 2),
            "commanded_ul_min": round(commanded_ul_min, 2),
            "correction": round(correction, 4),
            "timestamp": datetime.now().isoformat()
        }
        
        self.calibration_data[pump_key]["calibration_points"].append(point)
        
        # Update average correction factor
        points = self.calibration_data[pump_key]["calibration_points"]
        avg_correction = sum(p["correction"] for p in points) / len(points)
        self.calibration_data[pump_key]["correction_factor"] = round(avg_correction, 4)
        
        print(f"\n[CALIBRATION POINT ADDED]")
        print(f"  Pump: {pump_ch}")
        print(f"  RPM: {rpm}")
        print(f"  Duration: {duration_sec} sec")
        print(f"  Measured volume: {measured_volume_ul} uL")
        print(f"  Measured flow rate: {measured_ul_min:.2f} uL/min")
        print(f"  Commanded flow rate: {commanded_ul_min:.2f} uL/min")
        print(f"  Correction factor: {correction:.4f}")
        print(f"  Updated average correction: {avg_correction:.4f}")
    
    def show_calibration_summary(self):
        """Display calibration summary."""
        print("\n" + "="*70)
        print("CALIBRATION SUMMARY")
        print("="*70)
        
        for pump_num in [1, 2]:
            pump_key = f"pump{pump_num}"
            data = self.calibration_data[pump_key]
            
            print(f"\nPUMP {pump_num}:")
            print(f"  uL per revolution: {data['ul_per_revolution']}")
            print(f"  Correction factor: {data['correction_factor']:.4f}")
            print(f"  Calibration points: {len(data['calibration_points'])}")
            
            if data['calibration_points']:
                print(f"\n  Recent measurements:")
                for point in data['calibration_points'][-5:]:  # Last 5 points
                    print(f"    {point['rpm']} RPM: {point['measured_ul_min']:.1f} uL/min "
                          f"(commanded {point['commanded_ul_min']:.1f}, correction {point['correction']:.3f})")
        
        print("="*70)


def calibrate_flow_rate(ctrl, calib):
    """Calibrate pump flow rate accuracy."""
    print("\n" + "="*70)
    print("FLOW RATE CALIBRATION")
    print("="*70)
    print("\nThis measures actual flow rate vs commanded flow rate.")
    print("\nYou will need:")
    print("  - Graduated cylinder or scale (measure actual volume)")
    print("  - Timer (or use the automated timing)")
    print("  - Sample liquid in reservoir")
    
    while True:
        print("\n" + "-"*70)
        pump_ch = input("\nPump to calibrate (1, 2, or 'done' to finish): ").strip()
        
        if pump_ch.lower() == 'done':
            break
        
        if pump_ch not in ['1', '2']:
            print("[ERROR] Invalid pump number")
            continue
        
        pump_ch = int(pump_ch)
        
        # Get test parameters
        try:
            rpm = int(input("RPM to test (5-300): ").strip())
            if rpm < 5 or rpm > 300:
                print("[ERROR] RPM must be 5-300")
                continue
            
            duration = float(input("Duration in seconds (10-60 recommended): ").strip())
            if duration < 1:
                print("[ERROR] Duration must be >= 1 second")
                continue
            
        except ValueError:
            print("[ERROR] Invalid number")
            continue
        
        # Calculate expected volume
        ul_per_rev = calib.calibration_data[f"pump{pump_ch}"]["ul_per_revolution"]
        expected_ul_min = rpm * ul_per_rev
        expected_volume = (expected_ul_min / 60.0) * duration
        
        print(f"\n[TEST PARAMETERS]")
        print(f"  Pump: {pump_ch}")
        print(f"  RPM: {rpm}")
        print(f"  Duration: {duration} sec")
        print(f"  Expected flow rate: {expected_ul_min:.1f} uL/min")
        print(f"  Expected volume: {expected_volume:.1f} uL")
        
        input("\nPress Enter when ready to start pump...")
        
        # Start pump
        print(f"\n[STARTING] Pump {pump_ch} at {rpm} RPM...")
        flow_rate = rpm * ul_per_rev
        
        if not ctrl.pump_start(rate_ul_min=flow_rate, ch=pump_ch):
            print("[ERROR] Failed to start pump")
            continue
        
        # Wait for duration
        print(f"[RUNNING] Pumping for {duration} seconds...")
        import time
        time.sleep(duration)
        
        # Stop pump
        print("[STOPPING] Pump stopped")
        ctrl.pump_stop(ch=pump_ch)
        
        # Get measured volume
        print("\nMeasure the actual volume delivered (graduated cylinder or scale)")
        print(f"Expected: {expected_volume:.1f} uL")
        
        try:
            measured_volume = float(input("Measured volume (uL): ").strip())
            
            if measured_volume <= 0:
                print("[ERROR] Invalid volume")
                continue
            
            # Add calibration point
            calib.add_calibration_point(pump_ch, rpm, duration, measured_volume)
            calib.save_calibration()
            
        except ValueError:
            print("[ERROR] Invalid volume measurement")
            continue
        
        # Ask if continue
        cont = input("\nCalibrate another point? (y/n): ").strip().lower()
        if cont != 'y':
            break


def test_contact_time(ctrl, calib):
    """Test contact time accuracy with calibrated values."""
    print("\n" + "="*70)
    print("CONTACT TIME TEST")
    print("="*70)
    print("\nThis tests if calibrated flow rates achieve target contact times.")
    
    while True:
        print("\n" + "-"*70)
        
        try:
            pump_ch = input("\nPump to test (1, 2, or 'done' to finish): ").strip()
            
            if pump_ch.lower() == 'done':
                break
            
            if pump_ch not in ['1', '2']:
                print("[ERROR] Invalid pump number")
                continue
            
            pump_ch = int(pump_ch)
            
            # Get target contact time and volume
            contact_time_sec = float(input("Target contact time (seconds): ").strip())
            volume_ul = float(input("Injection volume (uL): ").strip())
            
            # Calculate required flow rate
            required_ul_min = (volume_ul / contact_time_sec) * 60.0
            
            # Apply correction factor
            correction = calib.calibration_data[f"pump{pump_ch}"]["correction_factor"]
            corrected_ul_min = required_ul_min / correction
            
            # Convert to RPM
            ul_per_rev = calib.calibration_data[f"pump{pump_ch}"]["ul_per_revolution"]
            rpm = int(corrected_ul_min / ul_per_rev)
            rpm = max(5, min(300, rpm))  # Clamp to valid range
            
            print(f"\n[CALCULATED PARAMETERS]")
            print(f"  Target contact time: {contact_time_sec} sec")
            print(f"  Injection volume: {volume_ul} uL")
            print(f"  Required flow rate: {required_ul_min:.1f} uL/min")
            print(f"  Correction factor: {correction:.4f}")
            print(f"  Corrected flow rate: {corrected_ul_min:.1f} uL/min")
            print(f"  RPM: {rpm}")
            
            input("\nPress Enter to start test injection (have timer ready)...")
            
            # Perform injection
            print(f"\n[INJECT] Starting injection...")
            print(f"START TIMER NOW!")
            
            if not ctrl.pump_start(rate_ul_min=corrected_ul_min, ch=pump_ch):
                print("[ERROR] Failed to start pump")
                continue
            
            import time
            time.sleep(contact_time_sec)
            
            ctrl.pump_stop(ch=pump_ch)
            print(f"[STOP] Injection complete")
            print(f"STOP TIMER - Expected time: {contact_time_sec} sec")
            
            # Get actual measured time
            actual_time = float(input("\nActual contact time measured (seconds): ").strip())
            time_error = actual_time - contact_time_sec
            percent_error = (time_error / contact_time_sec) * 100
            
            print(f"\n[RESULTS]")
            print(f"  Target time: {contact_time_sec} sec")
            print(f"  Actual time: {actual_time} sec")
            print(f"  Error: {time_error:+.2f} sec ({percent_error:+.1f}%)")
            
            if abs(percent_error) <= 5:
                print(f"  [OK] Within 5% tolerance!")
            else:
                print(f"  [WARN] >5% error - may need recalibration")
            
        except ValueError:
            print("[ERROR] Invalid input")
            continue
        except Exception as e:
            print(f"[ERROR] {e}")
            continue
        
        cont = input("\nTest another contact time? (y/n): ").strip().lower()
        if cont != 'y':
            break


def main():
    """Main calibration workflow."""
    print("="*70)
    print("  P4PROPLUS INTERNAL PUMP CALIBRATION TOOL")
    print("="*70)
    
    # Initialize controller
    print("\nInitializing controller...")
    ctrl = PicoP4PRO()
    
    if not ctrl.open():
        print("[ERROR] Could not connect to P4PROPLUS controller!")
        return
    
    print(f"[OK] Connected to {ctrl.firmware_id} version {ctrl.version}")
    
    if not ctrl.has_internal_pumps():
        print(f"[ERROR] No internal pumps (version {ctrl.version})")
        ctrl.close()
        return
    
    print(f"[OK] Internal pumps detected!")
    
    # Initialize calibration
    calib = PumpCalibration()
    calib.show_calibration_summary()
    
    # Main menu
    while True:
        print("\n" + "="*70)
        print("CALIBRATION MENU")
        print("="*70)
        print("1. Calibrate flow rate (measure actual vs commanded)")
        print("2. Test contact time accuracy")
        print("3. View calibration summary")
        print("4. Reset calibration data")
        print("q. Quit")
        print("="*70)
        
        choice = input("\nSelect option: ").strip().lower()
        
        if choice == '1':
            calibrate_flow_rate(ctrl, calib)
        elif choice == '2':
            test_contact_time(ctrl, calib)
        elif choice == '3':
            calib.show_calibration_summary()
        elif choice == '4':
            confirm = input("Reset ALL calibration data? (yes/no): ").strip().lower()
            if confirm == 'yes':
                calib.calibration_data = {
                    "created": datetime.now().isoformat(),
                    "last_updated": datetime.now().isoformat(),
                    "pump1": {
                        "ul_per_revolution": 3.0,
                        "correction_factor": 1.0,
                        "calibration_points": []
                    },
                    "pump2": {
                        "ul_per_revolution": 3.0,
                        "correction_factor": 1.0,
                        "calibration_points": []
                    }
                }
                calib.save_calibration()
                print("[OK] Calibration data reset")
        elif choice in ['q', 'quit', 'exit']:
            break
        else:
            print("[ERROR] Invalid option")
    
    # Cleanup
    print("\n[CLEANUP] Stopping all pumps...")
    ctrl.pump_stop(ch=3)
    ctrl.close()
    print("[DONE] Calibration session complete!")


if __name__ == "__main__":
    main()
