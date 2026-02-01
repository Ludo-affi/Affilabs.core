"""
RAW COMMAND TEST - Exactly mimicking old software sequence
"""
import serial
import time

def send_raw(ser, cmd):
    """Send raw command exactly like old software"""
    ser.reset_input_buffer()
    ser.write((cmd + '\r').encode())
    time.sleep(0.1)
    response = ser.read(256)
    print(f"  → {cmd}")
    print(f"  ← {response}")
    return response

def main():
    print("="*70)
    print("RAW COMMAND TEST - Mimicking Old Software Exactly")
    print("="*70)

    ser = serial.Serial(
        port='COM8',
        baudrate=38400,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=2
    )
    time.sleep(0.5)

    try:
        # Stop any motion
        print("\n[1] Terminate any moves")
        send_raw(ser, "/1TR")
        time.sleep(0.5)

        # Initialize
        print("\n[2] Initialize pump")
        send_raw(ser, "/1YR")
        time.sleep(8)

        # Check position
        print("\n[3] Check position")
        send_raw(ser, "/1?")

        # Test 1: Aspirate with HIGH SPEED like old software priming
        print("\n" + "="*70)
        print("[4] TEST: Aspirate 1000µL like old software (166.667 mL/min)")
        print("="*70)
        print("Old software priming command: V166.667,1R then V9000R")

        # Set input valve
        print("\n  Setting valve to INPUT...")
        send_raw(ser, "/1IR")
        time.sleep(0.2)

        # Set flow rate (OLD SOFTWARE USES 166.667 mL/min for priming!)
        print("\n  Setting flow rate: V166.667,1R (10 L/hour!)")
        send_raw(ser, "/1V166.667,1R")
        time.sleep(0.8)  # Old software waits 0.8s

        # Set top speed
        print("\n  Setting top speed: V9000R")
        send_raw(ser, "/1V9000R")
        time.sleep(0.2)

        # Aspirate 1000µL (181490 steps)
        print("\n  Aspirating 181490 steps (1000µL)...")
        start = time.time()
        send_raw(ser, "/1P181490R")

        # Monitor position
        print("\n  Monitoring:")
        while True:
            time.sleep(1)
            resp = send_raw(ser, "/1?")
            elapsed = time.time() - start
            print(f"    {elapsed:.1f}s elapsed")

            # Check if done (look for idle status)
            if b' ' in resp or elapsed > 30:
                break

        elapsed = time.time() - start
        rate = (1000 / elapsed) * 60
        print(f"\n  RESULT: {elapsed:.1f}s, {rate:.0f} µL/min")

        time.sleep(2)

        # Test 2: Slow dispense
        print("\n" + "="*70)
        print("[5] TEST: Dispense 1000µL at 0.5 mL/min (30 µL/s)")
        print("="*70)

        # Set output valve
        print("\n  Setting valve to OUTPUT...")
        send_raw(ser, "/1OR")
        time.sleep(0.2)

        # Set slow flow rate
        print("\n  Setting flow rate: V0.5,1R")
        send_raw(ser, "/1V0.5,1R")
        time.sleep(0.8)

        # Set top speed
        print("\n  Setting top speed: V6000R")
        send_raw(ser, "/1V6000R")
        time.sleep(0.2)

        # Dispense
        print("\n  Dispensing 181490 steps...")
        start = time.time()
        send_raw(ser, "/1D181490R")

        # Monitor
        print("\n  Monitoring:")
        while True:
            time.sleep(5)
            resp = send_raw(ser, "/1?")
            elapsed = time.time() - start
            print(f"    {elapsed:.1f}s elapsed")

            if b' ' in resp or elapsed > 150:
                break

        elapsed = time.time() - start
        rate = (1000 / elapsed) * 60
        print(f"\n  RESULT: {elapsed:.1f}s, {rate:.0f} µL/min")

    finally:
        ser.close()
        print("\nDone")

if __name__ == "__main__":
    main()
