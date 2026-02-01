"""Set the firmware pk value to 55 µL/min."""

from affilabs.utils.controller import PicoP4PRO
import time

try:
    print("Connecting to P4PRO/P4PROPLUS...")
    ctrl = PicoP4PRO()

    if ctrl.open():
        print(f"✅ Connected to {ctrl.firmware_id} (version {ctrl.version})")

        # Flush buffers
        ctrl._ser.reset_input_buffer()
        ctrl._ser.reset_output_buffer()
        time.sleep(0.2)

        # Set pk to 045
        print("\nSetting pk to 045...")
        ctrl._ser.write(b"pk055\n")
        time.sleep(0.2)

        # Read response
        responses = []
        while ctrl._ser.in_waiting > 0:
            line = ctrl._ser.readline().strip()
            if line:
                responses.append(line)
                print(f"  Response: {line!r}")

        # Now read it back to verify
        print("\nVerifying new value...")
        ctrl._ser.reset_input_buffer()
        time.sleep(0.1)
        ctrl._ser.write(b"pk\n")
        time.sleep(0.2)

        while ctrl._ser.in_waiting > 0:
            line = ctrl._ser.readline().strip()
            if line:
                print(f"  Read back: {line!r}")
                digits = bytes(ch for ch in line if 48 <= ch <= 57)
                if digits:
                    pk_value = int(digits)
                    print(f"\n✅ pk successfully set to: {pk_value} µL/min\n")
                    break
        else:
            print("\n⚠️  Command sent, but could not verify")
            print("   Firmware may not support pk command (requires V2.3.4+)")
            print(f"   Your firmware: {ctrl.firmware_id} {ctrl.version}\n")

        ctrl.close()
    else:
        print("\n❌ Could not connect to controller\n")

except Exception as e:
    print(f"\n❌ Error: {e}\n")
    import traceback
    traceback.print_exc()
