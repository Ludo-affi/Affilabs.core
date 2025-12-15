"""Test rank with pre-set LED intensities
Set each LED to different brightness, then call rank
"""

import time

import serial


def test_rank_with_preset_intensities():
    print("=" * 70)
    print("RANK COMMAND - PRE-SET INTENSITY TEST")
    print("=" * 70)
    print()
    print(">>> Setting individual LED intensities first...")

    ser = serial.Serial("COM5", 115200, timeout=1)
    time.sleep(1)

    # Set different brightness for each LED
    print("Setting LED A = 255 (100%)")
    ser.write(b"la:255\n")
    time.sleep(0.5)
    ser.write(b"lx\n")  # Turn off
    time.sleep(0.5)

    print("Setting LED B = 192 (75%)")
    ser.write(b"lb:192\n")
    time.sleep(0.5)
    ser.write(b"lx\n")
    time.sleep(0.5)

    print("Setting LED C = 128 (50%)")
    ser.write(b"lc:128\n")
    time.sleep(0.5)
    ser.write(b"lx\n")
    time.sleep(0.5)

    print("Setting LED D = 64 (25%)")
    ser.write(b"ld:64\n")
    time.sleep(0.5)
    ser.write(b"lx\n")
    time.sleep(0.5)

    print()
    print(">>> Now calling rank with intensity=1 (to use preset levels)...")
    print("    If this works, you should see:")
    print("    - LED A brightest")
    print("    - LED B bright")
    print("    - LED C medium")
    print("    - LED D dim")
    print()
    time.sleep(2)

    # Send rank command with intensity=1
    cmd = "rank:1,100,10\n"
    print(f"📤 Sending: {cmd.strip()}")

    ser.write(cmd.encode())

    # Read and display responses
    start_time = time.time()
    while True:
        if ser.in_waiting > 0:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if line:
                elapsed = (time.time() - start_time) * 1000

                if line == "START":
                    print(f"⏱️ {elapsed:6.1f}ms | START")
                elif "READY" in line:
                    led = line.split(":")[0].upper()
                    print(f"⏱️ {elapsed:6.1f}ms | {line} - ✨ LED {led} ON")
                    # Send ACK for READY
                    ser.write(b"\n")
                elif "READ" in line:
                    print(f"⏱️ {elapsed:6.1f}ms | {line}")
                elif "DONE" in line:
                    print(f"⏱️ {elapsed:6.1f}ms | {line} - 💡 LED OFF")
                    # Send ACK for DONE
                    ser.write(b"\n")
                elif line == "END":
                    print(f"⏱️ {elapsed:6.1f}ms | END - ✅ Complete!")
                    # Send final ACK
                    ser.write(b"\n")
                    break
                elif line == "ACK":
                    # Ignore echo
                    pass

        if (time.time() - start_time) > 2:
            print("Timeout")
            break

    total_time = (time.time() - start_time) * 1000

    ser.close()

    print()
    print("=" * 70)
    print(f"Total time: {total_time:.1f}ms")
    print()
    print("Did you see different brightness levels?")
    print("Or were they all the same (very dim)?")
    print("=" * 70)


if __name__ == "__main__":
    test_rank_with_preset_intensities()
