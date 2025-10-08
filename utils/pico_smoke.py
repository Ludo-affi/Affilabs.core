import sys
import time
from typing import Optional

import serial
from serial.tools import list_ports


PICO_VID = 0x2E8A
PICO_PID = 0x000A


def find_pico_port() -> Optional[str]:
    ports = list_ports.comports()
    for p in ports:
        if (p.vid, p.pid) == (PICO_VID, PICO_PID):
            # Prefer the MI_00 interface if available
            if "MI_00" in (p.hwid or ""):
                return p.device
    # Fallback to any matching VID/PID
    for p in ports:
        if (p.vid, p.pid) == (PICO_VID, PICO_PID):
            return p.device
    return None


def open_serial(port: str) -> serial.Serial:
    ser = serial.Serial()
    ser.port = port
    ser.baudrate = 115200
    ser.timeout = 1.0
    ser.write_timeout = 1.0
    ser.dtr = False
    ser.rts = False
    ser.open()
    return ser


def read_available(ser: serial.Serial) -> str:
    time.sleep(0.05)
    out = b""
    while ser.in_waiting:
        out += ser.read(ser.in_waiting)
        time.sleep(0.01)
    try:
        return out.decode(errors="ignore")
    except Exception:
        return out.decode("latin1", errors="ignore")


def wait_for_banner(ser: serial.Serial, timeout: float = 1.0) -> str:
    buf = b""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        n = ser.in_waiting
        if n:
            buf += ser.read(n)
        if b"\n" in buf:
            break
        time.sleep(0.01)
    try:
        return buf.decode(errors="ignore").strip()
    except Exception:
        return buf.decode("latin1", errors="ignore").strip()


def query(ser: serial.Serial, cmd: str, dtr_pulse: bool = False) -> str:
    if dtr_pulse:
        ser.dtr = False
        time.sleep(0.05)
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        ser.dtr = True
        time.sleep(0.05)
    # send with CRLF to be tolerant
    ser.write((cmd + "\r\n").encode())
    ser.flush()
    # read one line
    line = ser.readline().decode(errors="ignore").strip()
    return line


def main() -> int:
    port = find_pico_port()
    if not port:
        print("Pico not found (VID=2E8A, PID=000A)")
        return 2

    print(f"Opening {port} ...")
    ser = open_serial(port)

    try:
        # Clear any buffered data
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        # Toggle DTR to trigger banner
        ser.dtr = False
        time.sleep(0.1)
        ser.dtr = True
        # Wait up to 1s for a banner line (or any bytes)
        banner = wait_for_banner(ser, timeout=1.0)
        if not banner:
            # Retry once with a short pulse and buffer clear
            ser.dtr = False
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            time.sleep(0.05)
            ser.dtr = True
            banner = wait_for_banner(ser, timeout=0.5)
        print(f"Banner: {banner!r}")

        # Query id and iv
        id_reply = query(ser, "id")
        iv_reply = query(ser, "iv")
        print(f"id: {id_reply!r}")
        print(f"iv: {iv_reply!r}")

        # Optional: temperature
        it_reply = query(ser, "it")
        print(f"it: {it_reply!r}")

        return 0
    finally:
        ser.close()


if __name__ == "__main__":
    raise SystemExit(main())
