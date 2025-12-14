"""Quick script to check firmware version while app is running."""
import sys
import time

# Check if affipump is available
try:
    from affipump.p4spr_controller import P4SPRController
    print("✓ P4SPRController imported")
except ImportError as e:
    print(f"✗ Failed to import P4SPRController: {e}")
    sys.exit(1)

def check_version(port="COM5"):
    """Check firmware version."""
    print(f"\n{'='*60}")
    print(f"FIRMWARE VERSION CHECK")
    print(f"{'='*60}")
    
    try:
        print(f"Connecting to {port}...")
        ctrl = P4SPRController(port)
        
        # Send version command
        print("Sending 'iv' command...")
        if ctrl._ser and ctrl._ser.is_open:
            # Clear buffer
            ctrl._ser.reset_input_buffer()
            ctrl._ser.reset_output_buffer()
            time.sleep(0.1)
            
            # Send command
            ctrl._ser.write(b"iv\n")
            time.sleep(0.2)
            
            # Read response
            response = ""
            if ctrl._ser.in_waiting > 0:
                response = ctrl._ser.read(ctrl._ser.in_waiting).decode('utf-8', errors='ignore')
            
            print(f"\n{'='*60}")
            print(f"RESPONSE:")
            print(f"{'='*60}")
            if response:
                print(response)
                
                # Parse version
                if "V2.2" in response:
                    print(f"\n✓ NEW FIRMWARE DETECTED (V2.2)")
                    print(f"  ISR bug fixes should be active")
                elif "V2.1" in response or "V2.0" in response:
                    print(f"\n⚠ OLD FIRMWARE DETECTED ({response.strip()})")
                    print(f"  ISR bugs NOT fixed - flash didn't work!")
                else:
                    print(f"\n? UNKNOWN VERSION: {response.strip()}")
            else:
                print("✗ No response from firmware")
                print("  Port may be in use or firmware not responding")
            print(f"{'='*60}\n")
            
        ctrl.close()
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    port = sys.argv[1] if len(sys.argv) > 1 else "COM5"
    check_version(port)
