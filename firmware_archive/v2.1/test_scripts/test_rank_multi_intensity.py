"""
Test rank command with different LED intensities
LED A: 255 (brightest)
LED B: 192 (75%)
LED C: 128 (50%)
LED D: 64 (25%)
"""

import serial
import time

def test_rank_multi_intensity():
    print("=" * 70)
    print("RANK COMMAND - MULTI-INTENSITY TEST")
    print("=" * 70)
    print()
    print(">>> WATCH THE LEDs - Different brightness levels:")
    print("    LED A: 255 (brightest)")
    print("    LED B: 192 (75%)")
    print("    LED C: 128 (50%)")
    print("    LED D:  64 (25%)")
    print()

    time.sleep(2)

    # Open serial connection
    ser = serial.Serial('COM5', 115200, timeout=1)
    time.sleep(1)

    # Send rank command with different intensities
    # Protocol: rank:int_a,int_b,int_c,int_d,settling_ms,dark_ms
    cmd = "rank:255,192,128,64,100,10\n"
    print(f"📤 Sending: {cmd.strip()}")
    print(f"   (A=255, B=192, C=128, D=64, settling=100ms, dark=10ms)")
    print()

    ser.write(cmd.encode())

    # Read and display responses
    start_time = time.time()
    while True:
        if ser.in_waiting > 0:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if line:
                elapsed = (time.time() - start_time) * 1000

                if line == "START":
                    print(f"⏱️ {elapsed:6.1f}ms | START - Beginning sequence")
                elif "READY" in line:
                    led = line.split(':')[0].upper()
                    print(f"⏱️ {elapsed:6.1f}ms | {line} - ✨ LED {led} ON (watch brightness!)")
                elif "READ" in line:
                    print(f"⏱️ {elapsed:6.1f}ms | {line} - 📸 Acquiring")
                elif "DONE" in line:
                    led = line.split(':')[0].upper()
                    print(f"⏱️ {elapsed:6.1f}ms | {line} - 💡 LED {led} OFF")
                elif line == "END":
                    print(f"⏱️ {elapsed:6.1f}ms | END - ✅ Sequence complete!")
                    break
                elif line == "ACK":
                    # Send ACK response
                    ser.write(b'\n')

        if (time.time() - start_time) > 2:
            print("Timeout waiting for response")
            break

    total_time = (time.time() - start_time) * 1000

    ser.close()

    print()
    print("=" * 70)
    print(f"Total time: {total_time:.1f}ms for 4 LEDs at different intensities")
    print()
    print("Did you see different brightness levels?")
    print("  A=brightest, B=bright, C=medium, D=dim")
    print("=" * 70)

if __name__ == "__main__":
    test_rank_multi_intensity()
