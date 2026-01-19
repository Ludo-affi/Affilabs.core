"""
Test simple injection function with P4PROPLUS internal pumps.

Demonstrates volume-based injection using peristaltic pumps.
"""

import sys
from pathlib import Path

# Add affilabs to path
sys.path.insert(0, str(Path(__file__).parent))

from affilabs.utils.controller import PicoP4PRO


def test_injection():
    """Test injection with various volumes and flow rates."""
    print("="*70)
    print("  P4PROPLUS INTERNAL PUMP INJECTION TEST")
    print("="*70)
    print("\nInitializing controller...")
    
    ctrl = PicoP4PRO()
    
    # Try to connect
    if not ctrl.open():
        print("[ERROR] Could not connect to P4PROPLUS controller!")
        return
    
    print(f"[OK] Connected to {ctrl.firmware_id} version {ctrl.version}")
    
    # Check for internal pumps
    if not ctrl.has_internal_pumps():
        print(f"[ERROR] No internal pumps (version {ctrl.version})")
        ctrl.close()
        return
    
    print(f"[OK] Internal pumps detected!\n")
    
    # Test cases
    test_cases = [
        {"volume": 50, "flow_rate": 100, "ch": 1, "desc": "50 uL at 100 uL/min (Pump 1)"},
        {"volume": 100, "flow_rate": 150, "ch": 1, "desc": "100 uL at 150 uL/min (Pump 1)"},
        {"volume": 75, "flow_rate": 200, "ch": 2, "desc": "75 uL at 200 uL/min (Pump 2)"},
        {"volume": 50, "flow_rate": 100, "ch": 3, "desc": "50 uL at 100 uL/min (BOTH pumps)"},
    ]
    
    print("="*70)
    print("INJECTION TEST SEQUENCE")
    print("="*70)
    print("\nPress Enter to run each test, or 'q' to quit\n")
    
    for i, test in enumerate(test_cases, 1):
        print(f"\nTest {i}/{len(test_cases)}: {test['desc']}")
        print(f"  Volume: {test['volume']} uL")
        print(f"  Flow rate: {test['flow_rate']} uL/min")
        print(f"  Expected duration: {(test['volume'] / test['flow_rate']) * 60:.2f} sec")
        
        user_input = input("  Press Enter to start (or 'q' to quit): ").strip().lower()
        if user_input == 'q':
            print("\n[ABORT] Test sequence aborted by user")
            break
        
        print(f"\n  [RUNNING] Injection in progress...")
        result = ctrl.inject_internal_pump(
            volume_ul=test['volume'],
            flow_rate_ul_min=test['flow_rate'],
            ch=test['ch']
        )
        
        if result:
            print(f"  [SUCCESS] Injection completed")
        else:
            print(f"  [FAILED] Injection failed")
            break
        
        # Pause between injections
        if i < len(test_cases):
            import time
            print("\n  Waiting 2 seconds before next test...")
            time.sleep(2)
    
    # Cleanup
    print("\n" + "="*70)
    print("[CLEANUP] Stopping all pumps...")
    ctrl.pump_stop(ch=3)
    ctrl.close()
    print("[DONE] Test complete!")
    print("="*70)


if __name__ == "__main__":
    test_injection()
