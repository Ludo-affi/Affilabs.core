"""Detector Wait Sweep Experiment

Tests different detector sampling delays to find optimal stability.
Uses host-side spectrometer API to read detector during LED-on periods.
"""

import statistics
import sys
import time

import serial


def open_port(port: str, baud: int = 115200) -> serial.Serial:
    """Open serial connection to firmware."""
    ser = serial.Serial(port, baudrate=baud, timeout=1)
    ser.setDTR(True)
    ser.setRTS(True)
    time.sleep(0.1)
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    return ser


def send_command(ser: serial.Serial, cmd: str) -> None:
    """Send command to firmware."""
    ser.write((cmd + "\n").encode("ascii"))


def read_response(ser: serial.Serial, timeout_s: float = 1.0) -> str:
    """Read firmware response."""
    end = time.time() + timeout_s
    lines = []
    while time.time() < end:
        if ser.in_waiting:
            try:
                line = ser.readline().decode("ascii", "ignore").strip()
                if line:
                    lines.append(line)
            except Exception:
                pass
        else:
            time.sleep(0.01)
    return "\n".join(lines)


def run_detector_sweep_simple(
    port: str,
    wait_times_ms: list[int],
    cycles_per_wait: int = 20,
):
    """Simple detector wait sweep without hardware manager.
    Reads READY markers from firmware, uses software-side timing.
    """
    print("=" * 70)
    print("DETECTOR WAIT SWEEP - SIMPLE MODE")
    print("=" * 70)
    print(f"\nPort: {port}")
    print(f"Wait times to test: {wait_times_ms} ms")
    print(f"Cycles per test: {cycles_per_wait}")
    print("\nNOTE: This mode tests software-side timing without detector hardware.")
    print("For full detector integration, use with hardware_manager.\n")

    ser = open_port(port)

    # Identify device
    send_command(ser, "id")
    id_resp = read_response(ser, 0.5)
    print(f"Device: {id_resp}\n")

    results = []

    for wait_ms in wait_times_ms:
        print(f"\n=== Testing wait={wait_ms}ms ===")

        # Send keepalive
        send_command(ser, "ka")
        time.sleep(0.1)

        # Start rankbatch with single LED to test timing
        led_intensity = 100
        send_command(ser, f"rankbatch:{led_intensity},0,0,0,0,0,{cycles_per_wait}")

        # Parse BATCH_START and ACK
        batch_start = ser.readline().decode().strip()
        ack = ser.readline().decode().strip()
        print(f"Status: {batch_start}, ACK: {ack}")

        # Collect READY timestamps with software-side wait
        ready_times = []
        last_keepalive = time.time()

        for _ in range(cycles_per_wait):
            # Wait for READY signal
            line = ser.readline().decode("ascii", "ignore").strip()

            # Send keepalive every 5s
            if (time.time() - last_keepalive) >= 5.0:
                send_command(ser, "ka")
                last_keepalive = time.time()

            if "READY" in line:
                # Apply software wait before "sampling"
                time.sleep(wait_ms / 1000.0)
                ready_times.append(time.time())

        # Compute interval stability
        if len(ready_times) > 1:
            intervals = [
                (ready_times[i + 1] - ready_times[i]) * 1000
                for i in range(len(ready_times) - 1)
            ]
            mean_interval = statistics.mean(intervals)
            stdev_interval = statistics.pstdev(intervals)
            jitter = max(intervals) - min(intervals)

            result = {
                "wait_ms": wait_ms,
                "count": len(ready_times),
                "mean_interval_ms": mean_interval,
                "stdev_interval_ms": stdev_interval,
                "jitter_ms": jitter,
            }
            results.append(result)
            print(
                f"  Intervals: mean={mean_interval:.1f}ms, stdev={stdev_interval:.2f}ms, jitter={jitter:.1f}ms",
            )
        else:
            print("  ❌ No timing data collected")

        time.sleep(0.5)

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    for r in results:
        print(
            f" wait={r['wait_ms']:3d}ms | count={r['count']:3d} | "
            f"interval={r['mean_interval_ms']:6.1f}ms ±{r['stdev_interval_ms']:5.2f} | "
            f"jitter={r['jitter_ms']:5.1f}ms",
        )

    ser.close()
    return results


def main():
    if len(sys.argv) < 3:
        print("Usage: python scripts/detector_wait_sweep.py <COMx> <wait_csv> [cycles]")
        print("Example: python scripts/detector_wait_sweep.py COM5 0,2,5,10,20 20")
        print("\nTests different detector sampling delays to find optimal stability.")
        sys.exit(1)

    port = sys.argv[1]
    wait_times = [int(x) for x in sys.argv[2].split(",")]
    cycles = int(sys.argv[3]) if len(sys.argv) > 3 else 20

    run_detector_sweep_simple(port, wait_times, cycles)


if __name__ == "__main__":
    main()
