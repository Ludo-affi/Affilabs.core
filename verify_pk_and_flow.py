"""Verify pk value and pump command encoding."""

from affilabs.utils.controller import PicoP4PRO
import time

try:
    print("=" * 60)
    print("VERIFICATION: pk Value and Flow Command Encoding")
    print("=" * 60)

    ctrl = PicoP4PRO()

    if ctrl.open():
        print(f"\n✅ Connected to {ctrl.firmware_id} (version {ctrl.version})\n")

        # 1. Read current pk value
        print("1. Reading current pk value from firmware...")
        ctrl._ser.reset_input_buffer()
        ctrl._ser.reset_output_buffer()
        time.sleep(0.1)

        ctrl._ser.write(b"pk\n")
        time.sleep(0.2)

        pk_response = ctrl._ser.readline().strip()
        print(f"   Response: {pk_response!r}")

        if pk_response:
            try:
                pk_value = int(pk_response)
                print(f"   ✅ Current pk = {pk_value} µL/min\n")
            except ValueError:
                print("   ⚠️  Could not parse pk value\n")

        # 2. Send test command for 10 µL/min
        print("2. Testing pump command for 10 µL/min...")
        print("   Command format: pr3XXXX where XXXX = flow rate")

        test_rate = 10
        cmd = f"pr3{test_rate:04d}\n"
        print(f"   Sending: {cmd.strip()!r}")
        print("   Expected: pr30010")

        # 3. Calculate expected frequency
        if pk_response:
            try:
                pk = int(pk_response)
                expected_freq = (test_rate * 1000) / pk
                print("\n3. Expected pump frequency:")
                print("   Formula: freq = (rate × 1000) / pk")
                print(f"   freq = ({test_rate} × 1000) / {pk}")
                print(f"   freq = {expected_freq:.1f} Hz")

                # Calculate what pk SHOULD be for actual flow
                actual_flow = 33  # User measured
                actual_pk = (actual_flow * 1000) / expected_freq
                print(f"\n4. Analysis (actual flow = {actual_flow} µL/min):")
                print(f"   If actual flow = {actual_flow} µL/min at freq = {expected_freq:.1f} Hz")
                print(f"   Then effective pk = ({actual_flow} × 1000) / {expected_freq:.1f}")
                print(f"   Effective pk = {actual_pk:.1f} µL/min")
                print(f"\n   ⚠️  Mismatch! Firmware pk={pk} but behaving like pk={actual_pk:.0f}")

            except Exception as e:
                print(f"   Error in calculation: {e}")

        print("\n" + "=" * 60)
        print("RECOMMENDATION:")
        print("=" * 60)
        if pk_response:
            try:
                pk = int(pk_response)
                if pk == 45:
                    print("✅ pk is set to 45 (correct)")
                    print("❌ But pump is running 3× faster than expected")
                    print("🔍 Possible issues:")
                    print("   1. pk command not affecting pump speed")
                    print("   2. Firmware using different calibration")
                    print("   3. Command encoding mismatch")
                    print("\n💡 Try setting pk to 150 instead:")
                    print("   python set_pk_value.py  # and change to pk=150")
                else:
                    print(f"⚠️  pk is set to {pk}, not 45 as expected")
                    print("   Re-run set_pk_value.py to set pk=45")
            except:
                pass

        ctrl.close()

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
