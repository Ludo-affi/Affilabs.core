"""
LED ON Fixed - Detector Wait Sweep with Hardware Integration

Tests different detector wait times with FIXED LED ON duration to find optimal sampling delay.
Uses hardware spectrometer to measure actual signal stability.
"""
import sys
import time
import statistics
from datetime import datetime
from typing import List, Dict, Optional
import serial
import numpy as np

# Add parent dir to path for imports
sys.path.insert(0, '.')
from utils.hal.hal_factory import HALFactory


class LEDOnFixedDetectorWaitSweep:
    """Hardware-integrated detector wait sweep experiment with fixed LED ON time."""
    
    def __init__(self, port: str):
        self.port = port
        self.firmware = None
        self.spectrometer = None
        self.wavelengths = None
        
    def connect_hardware(self) -> bool:
        """Connect to firmware and spectrometer."""
        try:
            # Connect firmware
            print(f"Connecting to firmware on {self.port}...")
            self.firmware = serial.Serial(self.port, baudrate=115200, timeout=1)
            self.firmware.setDTR(True)
            self.firmware.setRTS(True)
            time.sleep(0.1)
            self.firmware.reset_input_buffer()
            self.firmware.reset_output_buffer()
            
            # Identify device
            self.firmware.write(b"id\n")
            time.sleep(0.05)
            fw_id = self.firmware.readline().decode('ascii', 'ignore').strip()
            print(f"✓ Firmware: {fw_id}")
            
            # Connect spectrometer
            print("Connecting to spectrometer...")
            self.spectrometer = HALFactory.create_spectrometer(auto_detect=True)
            
            # Get wavelengths
            if hasattr(self.spectrometer, 'get_wavelengths'):
                self.wavelengths = np.array(self.spectrometer.get_wavelengths())
            else:
                print("❌ Cannot get wavelengths from spectrometer")
                return False
            print(f"✓ Spectrometer: {len(self.wavelengths)} pixels")
            
            return True
            
        except Exception as e:
            print(f"❌ Hardware connection failed: {e}")
            return False
    
    def disconnect_hardware(self):
        """Disconnect all hardware."""
        if self.firmware:
            self.firmware.close()
        if self.spectrometer and hasattr(self.spectrometer, 'disconnect'):
            self.spectrometer.disconnect()
    
    def send_command(self, cmd: str):
        """Send command to firmware."""
        self.firmware.write((cmd + "\n").encode("ascii"))
    
    def read_spectrum(self) -> Optional[np.ndarray]:
        """Read spectrum from detector."""
        try:
            if hasattr(self.spectrometer, 'acquire_spectrum'):
                return np.array(self.spectrometer.acquire_spectrum())
            else:
                return np.array(self.spectrometer.read_intensity())
        except Exception as e:
            print(f"❌ Spectrum read error: {e}")
            return None
    
    def run_sweep(self, detector_wait_times_ms: List[int], led_on_ms: int = 250, 
                  cycles_per_test: int = 20, 
                  led_intensities: tuple = (50, 100, 150, 200)) -> List[Dict]:
        """
        Run detector wait time sweep experiment with FIXED LED ON duration.
        
        Args:
            detector_wait_times_ms: List of detector wait delays to test (ms)
            led_on_ms: Fixed LED ON duration (ms) - default 250ms
            cycles_per_test: Number of 4-LED cycles per detector wait test
            led_intensities: Tuple of 4 LED intensities (A, B, C, D)
        
        Returns:
            List of result dictionaries with stability metrics
        """
        print("=" * 70)
        print("DETECTOR WAIT SWEEP - FIXED LED ON TIME")
        print("="*70)
        print(f"\nLED ON time (fixed): {led_on_ms} ms")
        print(f"Detector wait times to test: {detector_wait_times_ms} ms")
        print(f"Cycles per test: {cycles_per_test} (4 LEDs per cycle)")
        print(f"LED intensities: A={led_intensities[0]}, B={led_intensities[1]}, C={led_intensities[2]}, D={led_intensities[3]}")
        print(f"Wavelength range: {self.wavelengths[0]:.1f} - {self.wavelengths[-1]:.1f} nm\n")
        
        results = []
        
        for detector_wait_ms in detector_wait_times_ms:
            print(f"\n{'='*70}")
            print(f"Testing detector wait time = {detector_wait_ms} ms (LED ON = {led_on_ms} ms)")
            print(f"{'='*70}")
            
            # Send keepalive
            self.send_command("ka")
            time.sleep(0.1)
            
            # Start rankbatch with fixed LED ON time and varying detector wait
            cmd = f"rankbatch:{led_intensities[0]},{led_intensities[1]},{led_intensities[2]},{led_intensities[3]},{led_on_ms},0,{cycles_per_test}"
            cmd_start_time = time.time()  # Mark when command is sent
            self.send_command(cmd)
            
            # Parse BATCH_START and ACK
            batch_line = self.firmware.readline().decode('ascii', 'ignore').strip()
            ack_line = self.firmware.readline().decode('ascii', 'ignore').strip()
            # Filter out ACK character (may be concatenated with next message)
            batch_line = batch_line.replace('\x06', '').lstrip('6').strip()
            ack_line = ack_line.replace('\x06', '').lstrip('6').strip()
            print(f"Status: {batch_line}, ACK: {ack_line}")
            
            # Track timing for first 3 scans
            scan_times = []
            
            # Collect detector readings for each LED
            readings_per_led = {'A': [], 'B': [], 'C': [], 'D': []}
            samples_collected = 0
            expected_samples = cycles_per_test * 4  # 4 LEDs per cycle
            
            print(f"Sampling 4 LEDs per cycle (LED_ON={led_on_ms}ms, detector_wait={detector_wait_ms}ms)...")
            
            # Check if ack_line is actually the first READY signal (happens with instant READY firmware)
            if ':READY' in ack_line:
                led_id = ack_line[0].upper()
                if led_id in ['A', 'B', 'C', 'D']:
                    ready_time = time.time()
                    # Wait specified detector delay before sampling
                    time.sleep(detector_wait_ms / 1000.0)
                    
                    # Acquire 3 scans per spectrum
                    three_scan_start = time.time()
                    peak_values = []
                    for scan_num in range(3):
                        spectrum = self.read_spectrum()
                        if spectrum is not None:
                            mask = (self.wavelengths >= 550) & (self.wavelengths <= 800)
                            peak_value = np.max(spectrum[mask])
                            peak_values.append(peak_value)
                    three_scan_end = time.time()
                    
                    if peak_values:
                        # Use mean of 3 scans
                        avg_peak = np.mean(peak_values)
                        readings_per_led[led_id].append(avg_peak)
                        samples_collected += 1
                        # Record timing for first LED measurement
                        if len(scan_times) < 1:
                            scan_times.append({
                                'scan_num': samples_collected,
                                'led': led_id,
                                'ready_elapsed': (ready_time - cmd_start_time) * 1000,
                                'three_scan_duration': (three_scan_end - three_scan_start) * 1000,
                                'total_elapsed': (three_scan_end - cmd_start_time) * 1000
                            })
            
            cycle_count = 0
            current_led_index = 0
            led_sequence = ['A', 'B', 'C', 'D']
            
            start_time = time.time()
            timeout = (led_on_ms + detector_wait_ms + 100) * expected_samples / 1000 + 10  # Add 10s buffer
            
            while samples_collected < expected_samples and (time.time() - start_time) < timeout:
                try:
                    # Check for READY signal from firmware
                    if self.firmware.in_waiting:
                        line = self.firmware.readline().decode('ascii', 'ignore').strip()
                        # Filter ACK character
                        line = line.replace('\x06', '').lstrip('6').strip()
                        
                        if ':READY' in line:
                            # Extract LED identifier (e.g., "a:READY" -> "A")
                            led_id = line[0].upper()
                            if led_id in led_sequence:
                                ready_time = time.time()
                                # Wait specified detector delay before sampling
                                time.sleep(detector_wait_ms / 1000.0)
                                
                                # Acquire 3 scans per spectrum
                                three_scan_start = time.time()
                                peak_values = []
                                for scan_num in range(3):
                                    spectrum = self.read_spectrum()
                                    if spectrum is not None:
                                        mask = (self.wavelengths >= 550) & (self.wavelengths <= 800)
                                        peak_value = np.max(spectrum[mask])
                                        peak_values.append(peak_value)
                                three_scan_end = time.time()
                                
                                if peak_values:
                                    # Use mean of 3 scans
                                    avg_peak = np.mean(peak_values)
                                    readings_per_led[led_id].append(avg_peak)
                                    samples_collected += 1
                                    
                                    # Record timing for first LED measurement
                                    if len(scan_times) < 1:
                                        scan_times.append({
                                            'scan_num': samples_collected,
                                            'led': led_id,
                                            'ready_elapsed': (ready_time - cmd_start_time) * 1000,
                                            'three_scan_duration': (three_scan_end - three_scan_start) * 1000,
                                            'total_elapsed': (three_scan_end - cmd_start_time) * 1000
                                        })
                                    
                                    if samples_collected % 4 == 0:
                                        cycle_count = samples_collected // 4
                                        print(f"  Cycle {cycle_count}/{cycles_per_test} complete ({samples_collected}/{expected_samples} samples)")
                        
                        elif 'CYCLE:' in line:
                            pass  # Firmware cycle counter (informational)
                        elif 'BATCH_COMPLETE' in line:
                            print(f"✓ Batch complete signal received")
                            break
                
                except Exception as e:
                    print(f"⚠ Sample error: {e}")
                    continue
            
            if samples_collected < expected_samples:
                print(f"⚠ Warning: Only collected {samples_collected}/{expected_samples} samples (timeout)")
            else:
                print(f"✓ All {samples_collected} samples collected")
            
            # Print timing for first LED measurement (3 scans)
            if scan_times:
                print(f"\n⏱ Timing for first LED measurement (3 scans per spectrum):")
                st = scan_times[0]
                print(f"  LED {st['led']}: READY at {st['ready_elapsed']:.1f}ms")
                print(f"  → 3-scan acquisition duration: {st['three_scan_duration']:.1f}ms")
                print(f"  → Total time from command: {st['total_elapsed']:.1f}ms")
            
            # Analyze results per LED
            print(f"\nResults for detector_wait={detector_wait_ms}ms:")
            led_results = {}
            
            for led_name in ['A', 'B', 'C', 'D']:
                readings = readings_per_led[led_name]
                if len(readings) >= 3:  # Need at least 3 samples for stats
                    mean_val = statistics.mean(readings)
                    stdev_val = statistics.stdev(readings)
                    cv = (stdev_val / mean_val * 100) if mean_val > 0 else 0
                    min_val = min(readings)
                    max_val = max(readings)
                    
                    led_results[led_name] = {
                        'count': len(readings),
                        'peak_mean': mean_val,
                        'peak_stdev': stdev_val,
                        'peak_cv': cv,
                        'min': min_val,
                        'max': max_val
                    }
                    
                    print(f"  LED {led_name}: {len(readings)} samples, peak={mean_val:.0f}±{stdev_val:.1f} (CV={cv:.2f}%), range={min_val:.0f}-{max_val:.0f}")
                else:
                    print(f"  LED {led_name}: ❌ Insufficient samples ({len(readings)})")
            
            # Overall metrics
            if led_results:
                avg_cv = statistics.mean([r['peak_cv'] for r in led_results.values()])
                result = {
                    'detector_wait_ms': detector_wait_ms,
                    'led_on_ms': led_on_ms,
                    'led_results': led_results,
                    'avg_cv': avg_cv,
                    'total_samples': samples_collected
                }
                results.append(result)
                print(f"  Average CV across LEDs: {avg_cv:.2f}%")
            else:
                print(f"  ❌ No valid LED results")
            
            time.sleep(0.5)
        
        return results
    
    def print_summary(self, results: List[Dict]):
        """Print summary table of all results."""
        print(f"\n{'='*70}")
        print(f"SUMMARY - Signal Stability vs Detector Wait (LED ON = {results[0]['led_on_ms']}ms)")
        print(f"{'='*70}")
        
        # Per-LED table
        for led in ['A', 'B', 'C', 'D']:
            print(f"\nLED {led}:")
            print(f"{'Wait(ms)':<12} {'Samples':<10} {'Peak Mean':<12} {'Std Dev':<10} {'CV%':<8}")
            print("-" * 60)
            for r in results:
                if led in r['led_results']:
                    lr = r['led_results'][led]
                    print(f"{r['detector_wait_ms']:<12} {lr['count']:<10} {lr['peak_mean']:<12.0f} "
                          f"{lr['peak_stdev']:<10.1f} {lr['peak_cv']:<8.2f}")
        
        # Overall average CV
        print(f"\n{'='*70}")
        print("Average CV across all 4 LEDs:")
        print(f"{'Wait(ms)':<12} {'Avg CV%':<10} {'Total Samples':<15}")
        print("-" * 40)
        for r in results:
            print(f"{r['detector_wait_ms']:<12} {r['avg_cv']:<10.2f} {r['total_samples']:<15}")
        
        # Find optimal detector wait time (minimum average CV)
        if results:
            best = min(results, key=lambda x: x['avg_cv'])
            print("\n" + "="*70)
            print(f"✓ Optimal detector wait time: {best['detector_wait_ms']}ms (Avg CV: {best['avg_cv']:.2f}%)")
            print(f"  (with LED ON = {best['led_on_ms']}ms)")
            print("="*70)


def main():
    if len(sys.argv) < 3:
        print("Usage: python scripts/led_on_fixed_detector_wait_sweep.py <COMx> <detector_wait_csv> [led_on_ms] [cycles] [led_intensities]")
        print("\nExample: python scripts/led_on_fixed_detector_wait_sweep.py COM5 10,25,50,75,100 250 15 20,40,60,80")
        print("\nTests different detector wait times with FIXED LED ON duration to find optimal sampling delay.")
        print("Connects to real spectrometer hardware and measures signal statistics per LED.")
        sys.exit(1)
    
    port = sys.argv[1]
    detector_wait_times = [int(x) for x in sys.argv[2].split(",")]
    led_on_ms = int(sys.argv[3]) if len(sys.argv) > 3 else 250  # Default 250ms
    cycles = int(sys.argv[4]) if len(sys.argv) > 4 else 15
    led_intensities = tuple(int(x) for x in sys.argv[5].split(",")) if len(sys.argv) > 5 else (50, 100, 150, 200)
    
    sweep = LEDOnFixedDetectorWaitSweep(port)
    
    try:
        if not sweep.connect_hardware():
            print("\n❌ Hardware connection failed. Check connections and try again.")
            sys.exit(1)
        
        results = sweep.run_sweep(detector_wait_times, led_on_ms=led_on_ms, cycles_per_test=cycles, led_intensities=led_intensities)
        
        if results:
            sweep.print_summary(results)
        else:
            print("\n❌ No results collected")
        
    except KeyboardInterrupt:
        print("\n\n⚠ Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        sweep.disconnect_hardware()


if __name__ == "__main__":
    main()
