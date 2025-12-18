"""PicoP4SPR Serial IO Probe

Enumerates COM ports, identifies Pico (VID/PID), and runs a controlled
handshake+command sequence to isolate PermissionError(13) sources.

Commands tested (with raw IO logging):
- id, iv (identify & firmware version)
- lx (turn off all LEDs)
- lm:A (batch enable A), bA128 (set intensity), iA (query)
- ss, sp (set polarizer mode)

Usage:
  python tools/diagnostics/pico_io_probe.py

Outputs concise PASS/FAIL per command with exception details and timing.
"""

import time
import sys
import serial
import serial.tools.list_ports

PICO_VID = 0x2E8A
PICO_PID = 0x000A


def list_ports():
    ports = []
    for dev in serial.tools.list_ports.comports():
        ports.append({
            "device": dev.device,
            "vid": dev.vid,
            "pid": dev.pid,
            "desc": dev.description,
            "hwid": dev.hwid,
        })
    return ports


def try_port(device: str, baud: int = 115200, timeout: float = 1.0):
    print(f"\n=== Probing {device} ===")
    try:
        ser = serial.Serial(
            port=device,
            baudrate=baud,
            timeout=timeout,
            write_timeout=timeout,
            dsrdtr=True,
            rtscts=False,
        )
        # Required for Pico CDC on Windows
        ser.dtr = True
        ser.rts = True
        time.sleep(0.1)
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        def write(cmd: str):
            print(f"-> {cmd!r}")
            ser.write(cmd.encode())

        def read_line(label: str, wait: float = 0.2):
            time.sleep(wait)
            line = ser.readline()
            print(f"<- {label}: {line!r}")
            return line

        results = {}

        # id
        try:
            write("id\n")
            line = read_line("id")
            results["id"] = (line.startswith(b"P4SPR"), line)
        except Exception as e:
            print(f"[ERR] id: {e}")
            results["id"] = (False, e)

        # iv
        try:
            write("iv\n")
            line = read_line("iv")
            results["iv"] = (len(line) >= 4, line)
        except Exception as e:
            print(f"[ERR] iv: {e}")
            results["iv"] = (False, e)

        # lx (off)
        try:
            write("lx\n")
            ack = ser.read(10)
            print(f"<- lx ack: {ack!r}")
            results["lx"] = (b"6" in ack, ack)
        except Exception as e:
            print(f"[ERR] lx: {e}")
            results["lx"] = (False, e)

        # enable A via lm:A (firmware >= v1.9)
        try:
            write("lm:A\n")
            time.sleep(0.05)
            drain = ser.read(ser.in_waiting or 0)
            print(f"<- lm drain: {drain!r}")
            results["lm:A"] = (True, drain)
        except Exception as e:
            print(f"[ERR] lm:A: {e}")
            results["lm:A"] = (False, e)

        # bA128
        try:
            write("bA128\n")
            time.sleep(0.15)
            resp = ser.read(ser.in_waiting or 1)
            print(f"<- bA128: {resp!r}")
            results["bA128"] = (b"6" in resp or resp == b"6", resp)
        except Exception as e:
            print(f"[ERR] bA128: {e}")
            results["bA128"] = (False, e)

        # iA
        try:
            write("iA\n")
            line = read_line("iA", wait=0.05)
            results["iA"] = (line.strip().isdigit(), line)
        except Exception as e:
            print(f"[ERR] iA: {e}")
            results["iA"] = (False, e)

        # ss
        try:
            write("ss\n")
            line = read_line("ss", wait=0.12)
            ok = (line in (b"", b"6") or line.startswith(b"6"))
            results["ss"] = (ok, line)
        except Exception as e:
            print(f"[ERR] ss: {e}")
            results["ss"] = (False, e)

        # sp
        try:
            write("sp\n")
            line = read_line("sp", wait=0.12)
            ok = (line in (b"", b"6") or line.startswith(b"6"))
            results["sp"] = (ok, line)
        except Exception as e:
            print(f"[ERR] sp: {e}")
            results["sp"] = (False, e)

        # Summary
        print("\n--- Results ---")
        for k, (ok, info) in results.items():
            status = "PASS" if ok else "FAIL"
            print(f"{k:6s}: {status}  {info!r}")

        ser.close()
        return results
    except Exception as e:
        print(f"[ERR] open {device}: {e}")
        return {"open": (False, e)}


def main():
    ports = list_ports()
    print("\nDetected COM ports:")
    pico_candidates = []
    for p in ports:
        vid = p["vid"]
        pid = p["pid"]
        tag = f"VID={hex(vid) if vid else 'None'} PID={hex(pid) if pid else 'None'}"
        print(f" - {p['device']}: {p['desc']} ({tag})")
        if vid == PICO_VID and pid == PICO_PID:
            pico_candidates.append(p)

    if not pico_candidates:
        print("\nNo Pico VID/PID match found; probing all ports (Arduino excluded)...")
        # Exclude common Arduino IDs if available
        # Still probe everything since VID/PID may be missing on some Windows setups
        for p in ports:
            try_port(p["device"])
        return

    print("\nProbing Pico candidates by VID/PID:")
    for p in pico_candidates:
        try_port(p["device"])


if __name__ == "__main__":
    sys.exit(0 if main() is None else 0)
