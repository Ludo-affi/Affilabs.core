"""Set pump corrections in controller EEPROM: Pump 1 = 1.0, Pump 2 = 0.65"""

from affilabs.utils.controller import PicoP4PRO

try:
    print("=" * 60)
    print("SET PUMP CORRECTIONS TO EEPROM")
    print("=" * 60)
    
    ctrl = PicoP4PRO()
    
    if ctrl.open():
        print(f"\n✅ Connected to {ctrl.firmware_id} (version {ctrl.version})\n")
        
        # Read current corrections
        print("1. Reading current pump corrections...")
        try:
            current = ctrl.get_pump_corrections()
            if current:
                if isinstance(current, dict):
                    print(f"   Current: Pump 1 = {current.get(1, 'N/A')}, Pump 2 = {current.get(2, 'N/A')}")
                elif isinstance(current, tuple):
                    print(f"   Current: Pump 1 = {current[0]}, Pump 2 = {current[1]}")
            else:
                print("   Current: Not set or unable to read")
        except Exception as e:
            print(f"   Could not read current corrections: {e}")
        
        # Set new corrections
        print("\n2. Writing new pump corrections to EEPROM...")
        print("   Pump 1 = 1.000")
        print("   Pump 2 = 0.650")
        
        success = ctrl.set_pump_corrections(1.0, 0.65)
        
        if success:
            print("\n✅ SUCCESS! Pump corrections written to EEPROM")
        else:
            print("\n❌ FAILED to write pump corrections")
            print("   Firmware may not support this feature")
        
        # Verify by reading back
        print("\n3. Verifying by reading back...")
        try:
            import time
            time.sleep(0.2)  # Brief delay for EEPROM write
            
            verify = ctrl.get_pump_corrections()
            if verify:
                if isinstance(verify, dict):
                    p1 = verify.get(1, 'N/A')
                    p2 = verify.get(2, 'N/A')
                elif isinstance(verify, tuple):
                    p1, p2 = verify
                
                print(f"   Verified: Pump 1 = {p1}, Pump 2 = {p2}")
                
                # Check if values match
                if abs(float(p1) - 1.0) < 0.01 and abs(float(p2) - 0.65) < 0.01:
                    print("\n✅ VERIFICATION PASSED!")
                    print("   Pump 2 will now run at 65% of Pump 1 speed")
                else:
                    print("\n⚠️  WARNING: Read values don't match written values")
            else:
                print("   Could not verify (read returned None)")
        except Exception as e:
            print(f"   Verification error: {e}")
        
        ctrl.close()
        
        print("\n" + "=" * 60)
        print("DONE - Restart the application to use new corrections")
        print("=" * 60)
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
