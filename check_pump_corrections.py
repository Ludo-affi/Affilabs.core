"""Check current pump correction factors from firmware."""

from affilabs.utils.controller import PicoP4PRO

try:
    print("Connecting to P4PRO/P4PROPLUS...")
    ctrl = PicoP4PRO()
    
    if ctrl.open():
        print(f"✅ Connected to {ctrl.firmware_id} (version {ctrl.version})")
        
        # Check if firmware supports pump corrections
        if hasattr(ctrl, 'get_pump_corrections'):
            corrections = ctrl.get_pump_corrections()
            
            if corrections:
                print(f"\n✅ Pump correction factors:")
                print(f"   Pump 1: {corrections[0]:.3f}")
                print(f"   Pump 2: {corrections[1]:.3f}\n")
            else:
                print("\n❌ Could not read pump corrections from firmware")
                print("   (Feature may not be supported in this firmware version)\n")
        else:
            print("\n❌ Pump corrections not supported by this controller type\n")
        
        ctrl.close()
    else:
        print("\n❌ Could not connect to controller\n")

except Exception as e:
    print(f"\n❌ Error: {e}\n")
    import traceback
    traceback.print_exc()
