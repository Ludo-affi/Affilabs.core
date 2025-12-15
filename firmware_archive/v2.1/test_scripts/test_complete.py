#!/usr/bin/env python3
"""Test with proper error handling."""

import re
import time

import serial


def test_cycles():
    port = "COM5"
    baud = 115200

    print("Testing: rankbatch:100,150,200,250,1000,100,10")
    print("Monitoring for up to 8 minutes...")
    print()

    try:
        with serial.Serial(port, baud, timeout=1) as ser:
            time.sleep(0.5)

            # Send command
            command = "rankbatch:100,150,200,250,1000,100,10\n"
            ser.write(command.encode())

            cycle_pattern = re.compile(r"CYCLE:\s*(\d+)")
            cycles_seen = set()

            start_time = time.time()
            last_cycle_time = start_time
            timeout = 480  # 8 minutes
            no_data_timeout = 60  # Assume done if no data for 60s
            last_data_time = start_time

            while time.time() - start_time < timeout:
                try:
                    if ser.in_waiting:
                        last_data_time = time.time()
                        line = ser.readline().decode("utf-8", errors="ignore").strip()

                        match = cycle_pattern.search(line)
                        if match:
                            cycle_num = int(match.group(1))
                            if cycle_num not in cycles_seen:
                                current_time = time.time()
                                elapsed = current_time - last_cycle_time
                                total_elapsed = current_time - start_time
                                print(
                                    f"  Cycle {cycle_num} at {total_elapsed:.1f}s (interval: {elapsed:.1f}s)",
                                )
                                cycles_seen.add(cycle_num)
                                last_cycle_time = current_time

                                if len(cycles_seen) >= 10:
                                    print(f"\n{'='*60}")
                                    print(
                                        "🎉🎉🎉 SUCCESS! All 10 cycles completed! 🎉🎉🎉",
                                    )
                                    print(f"Total time: {total_elapsed:.1f}s")
                                    print(f"Average per cycle: {total_elapsed/10:.1f}s")
                                    print(f"{'='*60}")
                                    return True

                    # Check if we've gone too long without data
                    if time.time() - last_data_time > no_data_timeout:
                        print(
                            f"\n⚠️ No data received for {no_data_timeout}s, assuming test complete",
                        )
                        break

                except serial.SerialException:
                    print("\n⚠️ Serial connection lost")
                    break
                except Exception as e:
                    print(f"\n⚠️ Error: {e}")
                    break

                time.sleep(0.01)

            total_time = time.time() - start_time
            print(f"\n{'='*60}")
            print(f"Test ended after {total_time:.1f}s")
            print(f"Cycles completed: {len(cycles_seen)}")
            print(f"Cycles seen: {sorted(cycles_seen)}")
            if len(cycles_seen) > 0:
                print(f"Average per cycle: {total_time/len(cycles_seen):.1f}s")
            print(f"{'='*60}")
            return len(cycles_seen) == 10

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    success = test_cycles()
    if not success:
        print("\n⚠️ Test did not complete successfully")
