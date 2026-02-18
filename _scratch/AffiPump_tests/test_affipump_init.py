#!/usr/bin/env python3
"""
Quick Affipump initialization and status check
"""

import sys
sys.path.insert(0, r'c:\Users\lucia\OneDrive\Desktop\ezControl 2.0\Affilabs.core\ezcontrol-AI\affipump')

from pump_controller import PumpController
from cavro_manager import CavroPumpManager, PumpAddress

print("="*70)
print("AFFIPUMP INITIALIZATION TEST")
print("="*70)

# Step 1: Connect
print("\n[1] Connecting to pump controller...")
controller = PumpController.from_first_available()
if not controller:
    print("❌ No FTDI pump controller found on COM8")
    print("\nIs the Affipump:")
    print("  - Powered on?")
    print("  - Connected via USB?")
    print("  - Showing up as COM8?")
    sys.exit(1)

print("✅ Connected to COM8")

# Step 2: Create manager
print("\n[2] Creating pump manager...")
manager = CavroPumpManager(controller)
print("✅ Pump manager created")

# Step 3: Initialize pumps
print("\n[3] Initializing pumps (this may take 10-15 seconds)...")
print("    Sending /1ZR (Initialize Pump 1)...")
print("    Sending /2ZR (Initialize Pump 2)...")

success = manager.initialize_pumps()

if success:
    print("✅ Pumps initialized successfully!")
else:
    print("⚠️  Initialization completed with warnings")
    print("    (This is normal if pumps were already initialized)")

# Step 4: Set syringe sizes
print("\n[4] Setting syringe sizes to 5mL (5000µL)...")
manager.set_syringe_size(PumpAddress.PUMP_1, 5000)
manager.set_syringe_size(PumpAddress.PUMP_2, 5000)
print("✅ Syringe sizes configured")

# Step 5: Get status
print("\n[5] Reading pump status...")
print("\n" + "-"*70)

for pump_num, addr in [(1, PumpAddress.PUMP_1), (2, PumpAddress.PUMP_2)]:
    print(f"\nPUMP {pump_num} (Address {addr:#x}):")
    try:
        diag = manager.get_diagnostic_info(addr)
        print(f"  Position:     {diag['syringe_position_steps']} steps")
        print(f"  Volume:       {diag['syringe_volume_ul']:.1f} µL")
        print(f"  Valve Port:   {diag['valve_port']}")
        print(f"  Busy:         {diag['is_busy']}")
        print(f"  Error:        {diag['last_error']}")
        
        if diag['last_error'] == 'NO_ERROR':
            print(f"  Status:       ✅ Ready")
        else:
            print(f"  Status:       ⚠️  Error detected")
    except Exception as e:
        print(f"  Status:       ❌ Communication error: {e}")

print("\n" + "="*70)
print("AFFIPUMP STATUS CHECK COMPLETE")
print("="*70)

# Close connection
controller.close()
print("\n✅ Connection closed")
