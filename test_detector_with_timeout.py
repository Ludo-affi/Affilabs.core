"""Test detector with explicit timeout settings to prevent hangs."""

from affilabs.utils.phase_photonics_wrapper import PhasePhotonics
import numpy as np

print("=" * 60)
print("DETECTOR TEST - WITH EXPLICIT TIMEOUTS")
print("=" * 60)

det = PhasePhotonics()

try:
    print("\n1. Opening detector...")
    if not det.open():
        print("   FAILED to open")
        exit(1)
    print(f"   ✓ Connected: {det.serial_number}")
    
    print("\n2. Setting integration time...")
    integration_ms = 100
    if det.set_integration(integration_ms):
        print(f"   ✓ Integration: {integration_ms}ms")
    else:
        print("   FAILED to set integration")
    
    print("\n3. Setting trigger timeout...")
    timeout_ms = 500  # 5x the integration time
    if det.set_trigger_timeout(timeout_ms):
        print(f"   ✓ Timeout: {timeout_ms}ms")
    else:
        print("   FAILED to set timeout")
    
    print("\n4. Reading spectrum (with timeout protection)...")
    print("   Calling read_intensity()...")
    
    spectrum = det.read_intensity(data_type=np.uint16)
    
    if spectrum is not None:
        print(f"\n   ✓✓✓ SUCCESS! ✓✓✓")
        print(f"   Points: {len(spectrum)}")
        print(f"   Min: {spectrum.min()}")
        print(f"   Max: {spectrum.max()}")
        print(f"   Mean: {spectrum.mean():.1f}")
        print(f"   ADC: 12-bit (0-4095)")
        
        # Show first 10
        print(f"\n   First 10 values:")
        for i in range(10):
            print(f"      [{i}] = {spectrum[i]}")
    else:
        print("   ✗ FAILED - returned None")
        
except Exception as e:
    print(f"\n   ✗✗✗ EXCEPTION: {e}")
    import traceback
    traceback.print_exc()
    
finally:
    print("\n5. Closing detector...")
    det.close()
    print("   ✓ Closed")
    print("=" * 60)
