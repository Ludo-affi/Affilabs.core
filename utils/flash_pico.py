import argparse
import os
import shutil
import string
import sys
import time
from pathlib import Path

import serial
from serial.tools import list_ports

PICO_VID = 0x2E8A
PICO_PID = 0x000A

DEFAULT_UF2 = Path("firmware/pi_pico_fw/build_mgw/affinite_p4spr/affinite_p4spr.uf2")
FALLBACK_UF2 = Path("firmware/pi_pico_fw/build/affinite_p4spr/affinite_p4spr.uf2")


def find_pico_port() -> Optional[str]:
    ports = list_ports.comports()
    # Prefer MI_00 interface when possible
    for p in ports:
        if (p.vid, p.pid) == (PICO_VID, PICO_PID) and "MI_00" in (p.hwid or ""):
            return p.device
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
    ser.dtr = True
    ser.rts = False
    ser.open()
    return ser


def send_ub(port: str) -> bool:
    try:
        ser = open_serial(port)
    except serial.SerialException as e:
        print(f"ERROR: Could not open {port}: {e}")
        return False
    try:
        # Clear any pending bytes and send command with CRLF (firmware accepts CR or LF)
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        ser.write(b"ub\r\n")
        ser.flush()
        # read ack if available (not strictly necessary)
        time.sleep(0.05)
        try:
            ack = ser.readline().decode(errors="ignore").strip()
            if ack:
                print(f"ACK: {ack!r}")
        except Exception:
            pass
        return True
    finally:
        try:
            ser.close()
        except Exception:
            pass


def find_rpi_rp2_drive(timeout: float = 30.0) -> Optional[Path]:
    """Poll Windows drive letters to find the UF2 bootloader drive by marker files."""
    deadline = time.monotonic() + timeout
    candidates = [f"{d}:\\" for d in string.ascii_uppercase]
    marker_files = ("INFO_UF2.TXT", "INDEX.HTM")
    while time.monotonic() < deadline:
        for root in candidates:
            try:
                if os.path.ismount(root):
                    for m in marker_files:
                        if os.path.exists(os.path.join(root, m)):
                            return Path(root)
            except Exception:
                continue
        time.sleep(0.25)
    return None


def copy_uf2(uf2_path: Path, drive_root: Path) -> None:
    dest = drive_root / uf2_path.name
    print(f"Copying {uf2_path} -> {dest}")
    shutil.copy2(uf2_path, dest)


def wait_for_drive_disconnect(drive_root: Path, timeout: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not drive_root.exists():
            return True
        # On Windows, the mount may remain while device is flashing; also check a marker vanishes
        if not (drive_root / "INFO_UF2.TXT").exists():
            return True
        time.sleep(0.25)
    return False


def resolve_uf2_path(cli_path: Optional[str]) -> Path:
    if cli_path:
        p = Path(cli_path)
        if not p.exists():
            raise FileNotFoundError(f"UF2 not found: {p}")
        return p
    if DEFAULT_UF2.exists():
        return DEFAULT_UF2
    if FALLBACK_UF2.exists():
        return FALLBACK_UF2
    raise FileNotFoundError(
        f"UF2 not found. Looked for {DEFAULT_UF2} and {FALLBACK_UF2}. "
        "Pass --uf2 <path> to specify a file.",
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Flash RP2040 Pico by sending 'ub' and copying UF2",
    )
    parser.add_argument(
        "--uf2",
        type=str,
        default=None,
        help="Path to UF2 file (defaults to latest build)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Timeout in seconds for drive detection",
    )
    parser.add_argument(
        "--no-ub",
        action="store_true",
        help="Don't send 'ub'; assume Pico is already in BOOTSEL mode",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print actions without sending/copying",
    )
    args = parser.parse_args(argv)

    try:
        uf2_path = resolve_uf2_path(args.uf2)
    except Exception as e:
        print(f"ERROR: {e}")
        return 2

    print(f"UF2: {uf2_path}")

    if not args.no_ub:
        port = find_pico_port()
        if not port:
            print(
                "ERROR: Pico serial device not found (VID=2E8A, PID=000A). Use --no-ub if already in BOOTSEL.",
            )
            return 2
        print(f"Sending 'ub' to {port} ...")
        if args.dry_run:
            print("[dry-run] would send 'ub' now")
        else:
            ok = send_ub(port)
            if not ok:
                print(
                    "ERROR: Failed to send 'ub'. Close any app using the COM port and try again.",
                )
                return 2

    print("Waiting for RPI-RP2 drive ...")
    if args.dry_run:
        print("[dry-run] would wait for RPI-RP2 now")
        return 0

    drive = find_rpi_rp2_drive(timeout=args.timeout)
    if not drive:
        print(
            "ERROR: RPI-RP2 drive not detected. You can press BOOTSEL manually or increase --timeout.",
        )
        return 3

    print(f"Found drive: {drive}")
    try:
        copy_uf2(uf2_path, drive)
    except Exception as e:
        print(f"ERROR copying UF2: {e}")
        return 4

    print("Waiting for device to reboot after copy ...")
    _ = wait_for_drive_disconnect(drive, timeout=30.0)
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
