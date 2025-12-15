import sys
import time

import serial


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/serial_dump.py <COMx> [duration_s] [cycles]")
        print("Example: python scripts/serial_dump.py COM5 8 5")
        return
    port = sys.argv[1]
    duration_s = float(sys.argv[2]) if len(sys.argv) > 2 else 8.0
    cycles = int(sys.argv[3]) if len(sys.argv) > 3 else 5

    ser = serial.Serial(port, baudrate=115200, timeout=1)
    ser.setDTR(True)
    ser.setRTS(True)
    time.sleep(0.1)
    ser.reset_input_buffer()
    ser.reset_output_buffer()

    # Identify device
    ser.write(b"id\n")
    time.sleep(0.3)
    id_resp = ser.read(ser.in_waiting or 1).decode("ascii", "ignore")
    print("ID:", id_resp.strip())

    # Send keepalive to avoid watchdog
    ser.write(b"ka\n")
    time.sleep(0.1)

    # Start a small batch
    cmd = f"rankbatch start settle=0 dark=0 cycles={cycles}\n".encode("ascii")
    ser.write(cmd)
    print("Sent:", cmd.decode("ascii").strip())

    print("\n--- Serial dump start ---")
    end = time.time() + duration_s
    while time.time() < end:
        data = ser.read(ser.in_waiting or 1)
        if data:
            try:
                sys.stdout.write(data.decode("ascii", "ignore"))
                sys.stdout.flush()
            except Exception:
                pass
        else:
            time.sleep(0.02)
    print("\n--- Serial dump end ---")

    ser.close()


if __name__ == "__main__":
    main()
