"""
Empirical LED/Detector Timing Measurement Test

This script measures:
1. Actual cycle time for complete 4-LED sequence
2. LED ON to detector acquisition timing for each channel
3. Detector acquisition window usage

Test Configuration:
- Integration time: 10ms
- LED intensities from 16:09 PM calibration (Dec 16, 2025):
  - CH1 (a): S=224, P=237
  - CH2 (b): S=87, P=96
  - CH3 (c): S=67, P=105
  - CH4 (d): S=244, P=255
- NUM_SCANS: 8 (actual system configuration)
- Expected timing:
  - LED_ON_TIME_MS: 225ms (optimized for 1000ms cycle)
  - DETECTOR_WAIT_MS: 45ms (optimized)
  - Per-channel time: 225ms
  - Total cycle: 900ms (4 channels × 225ms)
"""

import time
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple
import sys
from pathlib import Path

# Add affilabs to path
sys.path.insert(0, str(Path(__file__).parent))

from affilabs.core.hardware_manager import HardwareManager
from affilabs import settings

# Override timing settings for optimized test
settings.DETECTOR_WAIT_MS = 45.0  # Reduced from 60ms (optimized stabilization)
settings.LED_ON_TIME_MS = 225.0   # Optimized for 1000ms cycle (25ms savings per LED)


class TimingMeasurement:
    """Empirical timing measurement for LED/detector synchronization."""
    
    def __init__(self):
        self.hardware_mgr = None
        self.results: Dict[str, List[float]] = {
            'cycle_times': [],
            'led_to_detector_ch1': [],
            'led_to_detector_ch2': [],
            'led_to_detector_ch3': [],
            'led_to_detector_ch4': [],
            'detector_acquisition_ch1': [],
            'detector_acquisition_ch2': [],
            'detector_acquisition_ch3': [],
            'detector_acquisition_ch4': [],
        }
        
    def initialize_hardware(self) -> bool:
        """Initialize hardware connections."""
        print("=" * 80)
        print("EMPIRICAL TIMING MEASUREMENT TEST")
        print("=" * 80)
        print()
        print(f"Test Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        print("Test Configuration:")
        print(f"  Integration Time: 10ms")
        print(f"  LED Intensities (from 16:09 PM calibration):")
        print(f"    CH1 (a): S=224, P=237")
        print(f"    CH2 (b): S=87, P=96")
        print(f"    CH3 (c): S=67, P=105")
        print(f"    CH4 (d): S=244, P=255")
        print(f"  NUM_SCANS: 8")
        print(f"  LED_ON_TIME_MS: {settings.LED_ON_TIME_MS}ms")
        print(f"  DETECTOR_WAIT_MS: {settings.DETECTOR_WAIT_MS}ms")
        print()
        
        try:
            self.hardware_mgr = HardwareManager()
            print("Initializing hardware...")
            
            # Scan and connect to devices
            self.hardware_mgr.scan_and_connect(auto_connect=True)
            
            # Wait for connection
            wait_start = time.time()
            max_wait = 10.0
            while not self.hardware_mgr.connected and (time.time() - wait_start) < max_wait:
                time.sleep(0.1)
            
            if not self.hardware_mgr.ctrl:
                print("ERROR: Failed to connect controller")
                return False
            print(f"✓ Controller connected")
            
            if not self.hardware_mgr.usb:
                print("ERROR: Failed to connect spectrometer")
                return False
            serial = getattr(self.hardware_mgr.usb, 'serial_number', 'USB4000')
            print(f"✓ Spectrometer connected: {serial}")
            
            print()
            return True
            
        except Exception as e:
            print(f"ERROR initializing hardware: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def set_integration_time(self, integration_ms: float) -> bool:
        """Set detector integration time."""
        try:
            # set_integration expects milliseconds (it converts to microseconds internally)
            self.hardware_mgr.usb.set_integration(integration_ms)
            print(f"✓ Integration time set to {integration_ms}ms")
            return True
        except Exception as e:
            print(f"ERROR setting integration time: {e}")
            return False
    
    def set_led_intensities(self) -> bool:
        """Set LED intensities from 16:09 PM calibration (ONCE at initialization)."""
        try:
            # LED intensities from calibration_20251216_160910.json
            # Set the PWM duty cycle for each LED once - firmware stores these values
            # Then we only need to send turn_on_channel() commands during acquisition
            
            # Send brightness commands directly via serial (bypass adapter overhead)
            ctrl = self.hardware_mgr.ctrl._ctrl  # Get raw controller
            
            led_config = [
                ('a', 224),  # CH1 (a): S-mode
                ('b', 87),   # CH2 (b): S-mode
                ('c', 67),   # CH3 (c): S-mode
                ('d', 244),  # CH4 (d): S-mode
            ]
            
            for ch, intensity in led_config:
                # Format: ba224\n, bb087\n, bc067\n, bd244\n
                cmd = f"b{ch}{int(intensity):03d}\n"
                ctrl._ser.write(cmd.encode())
                time.sleep(0.01)  # Small delay between commands
                # Drain response
                if ctrl._ser.in_waiting > 0:
                    ctrl._ser.read(ctrl._ser.in_waiting)
            
            print(f"✓ LED intensities configured (S-mode from calibration):")
            print(f"  CH a: 224")
            print(f"  CH b: 87")
            print(f"  CH c: 67")
            print(f"  CH d: 244")
            print(f"  (Intensities set ONCE - will use turn_on_channel() during acquisition)")
            return True
            
        except Exception as e:
            print(f"ERROR setting LED intensities: {e}")
            return False
    
    def measure_single_cycle(self, cycle_num: int) -> bool:
        """Measure timing for one complete 4-channel cycle."""
        try:
            print(f"\nCycle {cycle_num}:")
            print("-" * 40)
            
            cycle_start = time.perf_counter()
            
            # LED intensities from calibration (S-mode)
            channels = ['a', 'b', 'c', 'd']
            led_intensities = {'a': 224, 'b': 87, 'c': 67, 'd': 244}
            
            for idx, channel in enumerate(channels, 1):
                # Turn on LED for this channel (intensity already set at initialization)
                cycle_channel_start = time.perf_counter()
                
                # Measure turn_on command execution time
                turn_on_start = time.perf_counter()
                
                # Send direct serial command: la\n, lb\n, lc\n, ld\n
                ctrl = self.hardware_mgr.ctrl._ctrl  # Get raw controller
                cmd = f"l{channel}\n"
                ctrl._ser.write(cmd.encode())
                
                # Wait for ACK (firmware sends '6' or '1')
                time.sleep(0.002)
                if ctrl._ser.in_waiting > 0:
                    ctrl._ser.read(ctrl._ser.in_waiting)  # Drain ACK
                
                turn_on_end = time.perf_counter()
                turn_on_duration_ms = (turn_on_end - turn_on_start) * 1000
                
                # LED is now ON - mark the time (production timing point)
                led_on_time = time.perf_counter()
                
                # Wait for LED stabilization (DETECTOR_WAIT_MS)
                time.sleep(settings.DETECTOR_WAIT_MS / 1000.0)
                
                # Start detector acquisition
                detector_start = time.perf_counter()
                led_to_detector_ms = (detector_start - led_on_time) * 1000
                
                # Acquire spectrum with averaging (8 scans averaged by detector)
                # Use read_roi with full spectrum range (0 to wavelength array length)
                # For USB4000: typically 3648 pixels
                spectrum = self.hardware_mgr.usb.read_roi(0, 3648, num_scans=8)
                
                detector_end = time.perf_counter()
                detector_duration_ms = (detector_end - detector_start) * 1000
                
                # Enforce LED_ON_TIME_MS timing (keeps LED on for full duration)
                # LED stays on for full period from when it turned on
                elapsed_since_led_on = (time.perf_counter() - led_on_time) * 1000
                remaining_led_on_ms = max(0, settings.LED_ON_TIME_MS - elapsed_since_led_on)
                
                # Debug timing breakdown
                channel_elapsed = (time.perf_counter() - cycle_channel_start) * 1000
                
                if remaining_led_on_ms > 0:
                    time.sleep(remaining_led_on_ms / 1000.0)
                
                # Get spectrum stats
                if spectrum is not None:
                    max_counts = np.max(spectrum)
                else:
                    max_counts = 0
                
                # Store timing measurements
                self.results[f'led_to_detector_ch{idx}'].append(led_to_detector_ms)
                self.results[f'detector_acquisition_ch{idx}'].append(detector_duration_ms)
                
                print(f"  CH{idx} ({channel}): TurnOn={turn_on_duration_ms:.1f}ms, "
                      f"LED→Det={led_to_detector_ms:.1f}ms, "
                      f"Acq={detector_duration_ms:.1f}ms, "
                      f"Elapsed={elapsed_since_led_on:.1f}ms, "
                      f"Sleep={remaining_led_on_ms:.1f}ms, "
                      f"Total={channel_elapsed:.1f}ms")
            
            cycle_end = time.perf_counter()
            cycle_time_ms = (cycle_end - cycle_start) * 1000
            self.results['cycle_times'].append(cycle_time_ms)
            
            print(f"  Total cycle time: {cycle_time_ms:.2f}ms")
            
            return True
            
        except Exception as e:
            print(f"ERROR in cycle {cycle_num}: {e}")
            return False
    
    def run_test(self, num_cycles: int = 10) -> bool:
        """Run complete timing test with multiple cycles."""
        print()
        print("=" * 80)
        print(f"RUNNING {num_cycles} MEASUREMENT CYCLES")
        print("=" * 80)
        
        for i in range(1, num_cycles + 1):
            if not self.measure_single_cycle(i):
                return False
            
            # Brief pause between cycles
            time.sleep(0.1)
        
        return True
    
    def analyze_results(self):
        """Analyze and display timing statistics."""
        print()
        print("=" * 80)
        print("TIMING ANALYSIS RESULTS")
        print("=" * 80)
        print()
        
        # Cycle time statistics
        cycle_times = np.array(self.results['cycle_times'])
        print("COMPLETE CYCLE TIME (4 channels):")
        print(f"  Mean:   {np.mean(cycle_times):.2f}ms")
        print(f"  Std:    {np.std(cycle_times):.2f}ms")
        print(f"  Min:    {np.min(cycle_times):.2f}ms")
        print(f"  Max:    {np.max(cycle_times):.2f}ms")
        print(f"  Expected: {settings.LED_ON_TIME_MS * 4:.2f}ms")
        deviation = np.mean(cycle_times) - (settings.LED_ON_TIME_MS * 4)
        print(f"  Deviation: {deviation:+.2f}ms ({deviation / (settings.LED_ON_TIME_MS * 4) * 100:+.2f}%)")
        print()
        
        # Per-channel LED-to-detector timing
        print("LED ON → DETECTOR START TIMING (per channel):")
        for ch in range(1, 5):
            times = np.array(self.results[f'led_to_detector_ch{ch}'])
            print(f"  CH{ch}: Mean={np.mean(times):.2f}ms, "
                  f"Std={np.std(times):.2f}ms, "
                  f"Range=[{np.min(times):.2f}, {np.max(times):.2f}]ms")
            print(f"       Expected: {settings.DETECTOR_WAIT_MS:.2f}ms, "
                  f"Deviation: {np.mean(times) - settings.DETECTOR_WAIT_MS:+.2f}ms")
        print()
        
        # Detector acquisition duration
        print("DETECTOR ACQUISITION DURATION (8 scans × 10ms):")
        for ch in range(1, 5):
            times = np.array(self.results[f'detector_acquisition_ch{ch}'])
            print(f"  CH{ch}: Mean={np.mean(times):.2f}ms, "
                  f"Std={np.std(times):.2f}ms, "
                  f"Range=[{np.min(times):.2f}, {np.max(times):.2f}]ms")
            print(f"       Expected: ~80ms (8 × 10ms), "
                  f"Overhead: {np.mean(times) - 80:+.2f}ms")
        print()
        
        # Timing validation
        print("TIMING VALIDATION:")
        print(f"  LED_ON_TIME_MS: {settings.LED_ON_TIME_MS}ms")
        print(f"  DETECTOR_WAIT_MS: {settings.DETECTOR_WAIT_MS}ms")
        print(f"  SAFETY_BUFFER_MS: 10ms (assumed)")
        detector_window = settings.LED_ON_TIME_MS - settings.DETECTOR_WAIT_MS - 10
        print(f"  Calculated Detector Window: {detector_window}ms")
        print()
        
        avg_acq_time = np.mean([
            np.mean(self.results[f'detector_acquisition_ch{ch}'])
            for ch in range(1, 5)
        ])
        margin = detector_window - avg_acq_time
        print(f"  Average Acquisition Time: {avg_acq_time:.2f}ms")
        print(f"  Timing Margin: {margin:.2f}ms")
        
        if margin > 0:
            print(f"  ✓ PASS: Acquisition fits within detector window (+{margin:.2f}ms margin)")
        else:
            print(f"  ✗ FAIL: Acquisition exceeds detector window ({margin:.2f}ms)")
        print()
        
        # Synchronization check
        print("LED/DETECTOR SYNCHRONIZATION:")
        led_to_det_times = [
            np.mean(self.results[f'led_to_detector_ch{ch}'])
            for ch in range(1, 5)
        ]
        led_to_det_variation = np.std(led_to_det_times)
        print(f"  Mean LED→Detector delay: {np.mean(led_to_det_times):.2f}ms")
        print(f"  Variation across channels: {led_to_det_variation:.2f}ms")
        
        if led_to_det_variation < 1.0:
            print(f"  ✓ EXCELLENT: Consistent timing across all channels")
        elif led_to_det_variation < 5.0:
            print(f"  ✓ GOOD: Acceptable timing variation")
        else:
            print(f"  ⚠ WARNING: High timing variation between channels")
        print()
    
    def cleanup(self):
        """Cleanup hardware connections."""
        print("Cleaning up...")
        if self.hardware_mgr:
            # Turn off all LEDs using batch command
            try:
                self.hardware_mgr.ctrl.set_batch_intensities(a=0, b=0, c=0, d=0)
            except:
                pass
            
            # Disconnect devices
            try:
                self.hardware_mgr.disconnect_all()
            except:
                pass
        
        print("✓ Cleanup complete")
        print()


def main():
    """Main test execution."""
    test = TimingMeasurement()
    
    try:
        # Initialize hardware
        if not test.initialize_hardware():
            print("\nTest ABORTED: Hardware initialization failed")
            return 1
        
        # Configure detector
        if not test.set_integration_time(10.0):
            print("\nTest ABORTED: Failed to set integration time")
            return 1
        
        # Configure LEDs
        if not test.set_led_intensities():
            print("\nTest ABORTED: Failed to set LED intensities")
            return 1
        
        # Run measurement cycles
        print("\nStarting measurement in 2 seconds...")
        time.sleep(2)
        
        if not test.run_test(num_cycles=10):
            print("\nTest ABORTED: Measurement cycle failed")
            return 1
        
        # Analyze results
        test.analyze_results()
        
        print("=" * 80)
        print("TEST COMPLETED SUCCESSFULLY")
        print("=" * 80)
        return 0
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        return 130
        
    except Exception as e:
        print(f"\n\nUNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    finally:
        test.cleanup()


if __name__ == "__main__":
    sys.exit(main())
