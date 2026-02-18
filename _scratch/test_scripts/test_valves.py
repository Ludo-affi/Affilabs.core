"""Test P4PRO valve commands - 6-port and 3-way valves."""
import sys
import time
sys.path.insert(0, r'c:\Users\lucia\OneDrive\Desktop\ezControl 2.0\Affilabs.core\Affilabs-core')

from affilabs.utils.controller import PicoP4PRO

print("="*80)
print("P4PRO Valve Test")
print("="*80)
print()

# Connect to P4PRO
print("Connecting to P4PRO controller...")
ctrl = PicoP4PRO()
if not ctrl.open():
    print("❌ Failed to connect to P4PRO!")
    sys.exit(1)

print(f"✅ Connected to {ctrl.firmware_id} version {ctrl.version}")
print()

# Test 6-port valves
print("="*80)
print("Testing 6-port valves (v6)")
print("State 0 = LOAD, State 1 = INJECT")
print("="*80)
print()

# Channel 1
print("Testing 6-port valve CH1...")
print("  → Setting to LOAD (state 0)...")
result = ctrl.knx_six(0, 1)
print(f"     Result: {result}")
time.sleep(1)

print("  → Setting to INJECT (state 1)...")
result = ctrl.knx_six(1, 1)
print(f"     Result: {result}")
time.sleep(1)

print("  → Returning to LOAD (state 0)...")
result = ctrl.knx_six(0, 1)
print(f"     Result: {result}")
time.sleep(1)
print()

# Channel 2
print("Testing 6-port valve CH2...")
print("  → Setting to LOAD (state 0)...")
result = ctrl.knx_six(0, 2)
print(f"     Result: {result}")
time.sleep(1)

print("  → Setting to INJECT (state 1)...")
result = ctrl.knx_six(1, 2)
print(f"     Result: {result}")
time.sleep(1)

print("  → Returning to LOAD (state 0)...")
result = ctrl.knx_six(0, 2)
print(f"     Result: {result}")
time.sleep(1)
print()

# Test 3-way valves
print("="*80)
print("Testing 3-way valves (v3)")
print("State 0 = WASTE, State 1 = LOAD")
print("="*80)
print()

# Channel 1
print("Testing 3-way valve CH1...")
print("  → Setting to WASTE (state 0)...")
result = ctrl.knx_three(0, 1)
print(f"     Result: {result}")
time.sleep(1)

print("  → Setting to LOAD (state 1)...")
result = ctrl.knx_three(1, 1)
print(f"     Result: {result}")
time.sleep(1)

print("  → Returning to WASTE (state 0)...")
result = ctrl.knx_three(0, 1)
print(f"     Result: {result}")
time.sleep(1)
print()

# Channel 2
print("Testing 3-way valve CH2...")
print("  → Setting to WASTE (state 0)...")
result = ctrl.knx_three(0, 2)
print(f"     Result: {result}")
time.sleep(1)

print("  → Setting to LOAD (state 1)...")
result = ctrl.knx_three(1, 2)
print(f"     Result: {result}")
time.sleep(1)

print("  → Returning to WASTE (state 0)...")
result = ctrl.knx_three(0, 2)
print(f"     Result: {result}")
time.sleep(1)
print()

# Final cleanup - ensure all valves closed/safe
print("="*80)
print("Cleanup: Closing all valves to safe positions...")
print("="*80)
ctrl.knx_six(0, 1)  # 6-port CH1 to LOAD
ctrl.knx_six(0, 2)  # 6-port CH2 to LOAD
ctrl.knx_three(0, 1)  # 3-way CH1 to WASTE
ctrl.knx_three(0, 2)  # 3-way CH2 to WASTE
print("✅ All valves returned to safe positions")
print()

print("="*80)
print("Valve test complete!")
print("="*80)

ctrl.close()
