"""Quick script to check current pk value from firmware."""

from affilabs.utils.controller import PicoP4PRO
import time

try:
    print("Connecting to P4PRO/P4PROPLUS...")
    ctrl = PicoP4PRO()
    
    if ctrl.open():
        print(f"✅ Connected to {ctrl.firmware_id} (version {ctrl.version})")
        
        # Flush any leftover data in serial buffer
        ctrl._ser.reset_input_buffer()
        ctrl._ser.reset_output_buffer()
        time.sleep(0.2)
        
        # Send pk command  - try reading multiple lines
        print("Sending pk command...")
        ctrl._ser.write(b"pk\n")
        time.sleep(0.2)
        
        # Read all available data
        all_data = []
        while ctrl._ser.in_waiting > 0:
            line = ctrl._ser.readline().strip()
            if line:
                all_data.append(line)
                print(f"  Received: {line!r}")
        
        if all_data:
            for reply in all_data:
                # Extract digits from reply
                digits = bytes(ch for ch in reply if 48 <= ch <= 57)
                if digits:
                    pk_value = int(digits)
                    print(f"\n✅ Current firmware pk value: {pk_value} µL/min")
                    print(f"   (Calibration constant stored in flash bytes [6-7])\n")
                    break
            else:
                print(f"\n❓ No numeric value found in responses\n")
        else:
            print("\n❌ No response from pk command")
            print("   Firmware version may not support this feature\n")
            print(f"   Your firmware: {ctrl.firmware_id} {ctrl.version}")
            print(f"   Required: P4PROPLUS V2.3.4+ for pk command\n")
        
        ctrl.close()
    else:
        print("\n❌ Could not connect to controller\n")

except Exception as e:
    print(f"\n❌ Error: {e}\n")
    import traceback
    traceback.print_exc()
