#!/usr/bin/env python3
"""
Test script for Firmware V2.1 rankbatch command

This script validates the new rankbatch command functionality:
- Batch intensities (individual per LED)
- Cycle counting (autonomous multi-cycle execution)
- Protocol signal flow
- Performance measurement

Usage:
    python test_rankbatch.py [COM_PORT]

Example:
    python test_rankbatch.py COM5
    python test_rankbatch.py /dev/ttyACM0
"""

import serial
import time
import sys
from typing import Dict, List, Tuple


class RankbatchTester:
    """Test harness for V2.1 rankbatch command."""

    def __init__(self, port: str, baudrate: int = 115200):
        """
        Initialize tester with serial connection.

        Args:
            port: Serial port (COM5, /dev/ttyACM0, etc.)
            baudrate: Baud rate (default: 115200)
        """
        self.port = port
        self.baudrate = baudrate
        self.ser = None

    def connect(self):
        """Open serial connection to Pico."""
        print(f"📡 Connecting to {self.port} at {self.baudrate} baud...")
        self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
        time.sleep(2)  # Wait for Pico to be ready
        print("✅ Connected!\n")

    def disconnect(self):
        """Close serial connection."""
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("\n📡 Disconnected")

    def send_command(self, cmd: str) -> str:
        """
        Send command and get immediate response (ACK/NAK).

        Args:
            cmd: Command string (with newline)

        Returns:
            Response string
        """
        self.ser.write(cmd.encode())
        return self.ser.readline().decode().strip()

    def read_signal(self) -> str:
        """
        Read one line from firmware.

        Returns:
            Signal string (stripped)
        """
        return self.ser.readline().decode().strip()

    def acknowledge(self):
        """Send acknowledgment to firmware after READ signal."""
        self.ser.write(b'1\n')

    def check_version(self) -> str:
        """
        Check firmware version.

        Returns:
            Version string
        """
        print("🔍 Checking firmware version...")
        self.ser.write(b'iv\n')
        version = self.ser.readline().decode().strip()
        print(f"   Version: {version}")

        if "2.1" not in version:
            print(f"   ⚠️  Warning: Expected V2.1, got {version}")
        else:
            print(f"   ✅ V2.1 detected!\n")

        return version

    def test_single_cycle(self) -> Tuple[bool, float]:
        """
        Test single cycle with equal intensities.

        Returns:
            (success, elapsed_time)
        """
        print("=" * 60)
        print("TEST 1: Single cycle with equal intensities")
        print("=" * 60)

        cmd = "rankbatch:128,128,128,128,35,5,1\n"
        print(f"📤 Sending: {cmd.strip()}")

        start_time = time.time()
        self.ser.write(cmd.encode())

        signals = []
        channel_count = 0

        while True:
            line = self.read_signal()
            if not line:
                continue

            signals.append(line)
            print(f"   {line}")

            if line == "BATCH_START":
                print("      → Batch sequence started")

            elif line.startswith("CYCLE:"):
                print(f"      → Cycle {line.split(':')[1]} started")

            elif line.endswith(":READY"):
                ch = line[0]
                print(f"      → LED {ch.upper()} is on and settling")

            elif line.endswith(":READ"):
                ch = line[0]
                channel_count += 1
                print(f"      → Acquire spectrum for LED {ch.upper()} NOW")
                # Simulate detector read
                time.sleep(0.150)
                self.acknowledge()
                print(f"      → Sent ACK")

            elif line.endswith(":DONE"):
                ch = line[0]
                print(f"      → LED {ch.upper()} turned off")

            elif line.startswith("CYCLE_END:"):
                print(f"      → Cycle complete")

            elif line == "BATCH_END":
                elapsed = time.time() - start_time
                print(f"      → Batch sequence complete!")
                print(f"\n⏱️  Total time: {elapsed:.3f}s")
                print(f"📊 Channels measured: {channel_count}")
                print(f"📈 Average per channel: {elapsed/channel_count*1000:.1f}ms")
                break

        # Read final ACK
        final_ack = self.read_signal()
        print(f"✅ Final response: {final_ack}\n")

        # Validate
        expected_signals = [
            "BATCH_START", "CYCLE:1",
            "a:READY", "a:READ", "a:DONE",
            "b:READY", "b:READ", "b:DONE",
            "c:READY", "c:READ", "c:DONE",
            "d:READY", "d:READ", "d:DONE",
            "CYCLE_END:1", "BATCH_END"
        ]

        success = (signals == expected_signals and channel_count == 4)

        if success:
            print("✅ TEST 1 PASSED\n")
        else:
            print("❌ TEST 1 FAILED - Unexpected signal sequence\n")

        return success, elapsed

    def test_multi_cycle(self, num_cycles: int = 3) -> Tuple[bool, float]:
        """
        Test multi-cycle execution.

        Args:
            num_cycles: Number of cycles to execute

        Returns:
            (success, elapsed_time)
        """
        print("=" * 60)
        print(f"TEST 2: Multi-cycle execution ({num_cycles} cycles)")
        print("=" * 60)

        cmd = f"rankbatch:128,128,128,128,35,5,{num_cycles}\n"
        print(f"📤 Sending: {cmd.strip()}")

        start_time = time.time()
        self.ser.write(cmd.encode())

        cycle_count = 0
        channel_count = 0

        while True:
            line = self.read_signal()
            if not line:
                continue

            print(f"   {line}")

            if line.startswith("CYCLE:"):
                cycle_count += 1
                print(f"      → Starting cycle {cycle_count}/{num_cycles}")

            elif line.endswith(":READ"):
                channel_count += 1
                # Simulate detector read
                time.sleep(0.150)
                self.acknowledge()

            elif line == "BATCH_END":
                elapsed = time.time() - start_time
                print(f"      → Batch sequence complete!")
                print(f"\n⏱️  Total time: {elapsed:.3f}s")
                print(f"📊 Cycles executed: {cycle_count}")
                print(f"📊 Channels measured: {channel_count}")
                print(f"📈 Average per channel: {elapsed/channel_count*1000:.1f}ms")
                print(f"📈 Average per cycle: {elapsed/cycle_count:.3f}s")
                break

        # Read final ACK
        final_ack = self.read_signal()
        print(f"✅ Final response: {final_ack}\n")

        # Validate
        success = (cycle_count == num_cycles and channel_count == num_cycles * 4)

        if success:
            print("✅ TEST 2 PASSED\n")
        else:
            print(f"❌ TEST 2 FAILED - Expected {num_cycles} cycles, got {cycle_count}\n")

        return success, elapsed

    def test_batch_intensities(self) -> Tuple[bool, float]:
        """
        Test different intensities per LED.

        Returns:
            (success, elapsed_time)
        """
        print("=" * 60)
        print("TEST 3: Batch intensities (different per LED)")
        print("=" * 60)

        cmd = "rankbatch:225,94,97,233,15,5,1\n"
        print(f"📤 Sending: {cmd.strip()}")
        print("   LED A: 225, LED B: 94, LED C: 97, LED D: 233")

        start_time = time.time()
        self.ser.write(cmd.encode())

        channel_count = 0

        while True:
            line = self.read_signal()
            if not line:
                continue

            print(f"   {line}")

            if line.endswith(":READ"):
                channel_count += 1
                time.sleep(0.150)
                self.acknowledge()

            elif line == "BATCH_END":
                elapsed = time.time() - start_time
                print(f"\n⏱️  Total time: {elapsed:.3f}s")
                print(f"📊 Channels measured: {channel_count}")
                break

        # Read final ACK
        final_ack = self.read_signal()
        print(f"✅ Final response: {final_ack}\n")

        success = (channel_count == 4)

        if success:
            print("✅ TEST 3 PASSED\n")
        else:
            print("❌ TEST 3 FAILED\n")

        return success, elapsed

    def test_selective_channels(self) -> Tuple[bool, float]:
        """
        Test selective channel measurement (zero intensity = skip).

        Returns:
            (success, elapsed_time)
        """
        print("=" * 60)
        print("TEST 4: Selective channels (zero intensity skips)")
        print("=" * 60)

        cmd = "rankbatch:255,0,0,255,35,5,1\n"
        print(f"📤 Sending: {cmd.strip()}")
        print("   LED A: 255 (measure), LED B: 0 (skip), LED C: 0 (skip), LED D: 255 (measure)")

        start_time = time.time()
        self.ser.write(cmd.encode())

        signals = []
        channel_count = 0

        while True:
            line = self.read_signal()
            if not line:
                continue

            signals.append(line)
            print(f"   {line}")

            if line.endswith(":SKIP"):
                ch = line[0]
                print(f"      → LED {ch.upper()} skipped (intensity = 0)")

            elif line.endswith(":READ"):
                channel_count += 1
                time.sleep(0.150)
                self.acknowledge()

            elif line == "BATCH_END":
                elapsed = time.time() - start_time
                print(f"\n⏱️  Total time: {elapsed:.3f}s")
                print(f"📊 Channels measured: {channel_count}")
                print(f"📊 Channels skipped: 2")
                break

        # Read final ACK
        final_ack = self.read_signal()
        print(f"✅ Final response: {final_ack}\n")

        # Validate
        success = (channel_count == 2 and "b:SKIP" in signals and "c:SKIP" in signals)

        if success:
            print("✅ TEST 4 PASSED\n")
        else:
            print("❌ TEST 4 FAILED\n")

        return success, elapsed

    def test_backward_compatibility(self) -> Tuple[bool, float]:
        """
        Test V2.0 rank command still works.

        Returns:
            (success, elapsed_time)
        """
        print("=" * 60)
        print("TEST 5: Backward compatibility (V2.0 rank command)")
        print("=" * 60)

        cmd = "rank:128,35,5\n"
        print(f"📤 Sending: {cmd.strip()}")

        start_time = time.time()
        self.ser.write(cmd.encode())

        channel_count = 0

        while True:
            line = self.read_signal()
            if not line:
                continue

            print(f"   {line}")

            if line.endswith(":READ"):
                channel_count += 1
                time.sleep(0.150)
                self.acknowledge()

            elif line == "END":
                elapsed = time.time() - start_time
                print(f"\n⏱️  Total time: {elapsed:.3f}s")
                print(f"📊 Channels measured: {channel_count}")
                break

        # Read final ACK
        final_ack = self.read_signal()
        print(f"✅ Final response: {final_ack}\n")

        success = (channel_count == 4)

        if success:
            print("✅ TEST 5 PASSED - V2.0 rank command works\n")
        else:
            print("❌ TEST 5 FAILED - V2.0 rank command broken\n")

        return success, elapsed

    def run_all_tests(self):
        """Run complete test suite."""
        print("\n" + "=" * 60)
        print("RANKBATCH COMMAND TEST SUITE")
        print("=" * 60 + "\n")

        # Check version
        version = self.check_version()

        # Run tests
        results = []

        results.append(("Single cycle", *self.test_single_cycle()))
        results.append(("Multi-cycle", *self.test_multi_cycle(3)))
        results.append(("Batch intensities", *self.test_batch_intensities()))
        results.append(("Selective channels", *self.test_selective_channels()))
        results.append(("Backward compatibility", *self.test_backward_compatibility()))

        # Summary
        print("=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)

        passed = 0
        failed = 0

        for name, success, elapsed in results:
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"{status}  {name:<30} {elapsed:.3f}s")
            if success:
                passed += 1
            else:
                failed += 1

        print("\n" + "-" * 60)
        print(f"Total: {passed} passed, {failed} failed")
        print("=" * 60 + "\n")

        return failed == 0


def main():
    """Main entry point."""
    # Get port from command line or use default
    port = sys.argv[1] if len(sys.argv) > 1 else "COM5"

    # Create tester
    tester = RankbatchTester(port)

    try:
        # Connect
        tester.connect()

        # Run all tests
        success = tester.run_all_tests()

        # Exit with appropriate code
        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(2)

    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(3)

    finally:
        # Always disconnect
        tester.disconnect()


if __name__ == "__main__":
    main()
