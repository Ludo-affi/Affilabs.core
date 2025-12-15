"""Python wrapper for Firmware V2.1 rankbatch command.

This module provides a high-level interface to the rankbatch command,
with generator-based signal processing for integration with existing code.

Usage:
    from controller_v2_1_wrapper import ControllerV2_1

    ctrl = ControllerV2_1(port='COM5')

    # Single cycle
    for channel, signal in ctrl.led_rank_batch_cycles(
        intensities={'a': 225, 'b': 94, 'c': 97, 'd': 233},
        settling_ms=15,
        dark_ms=5,
        num_cycles=1
    ):
        if signal == "READ":
            spectrum = detector.acquire()
            # Process spectrum...
"""

import logging
import time
from collections.abc import Generator

import serial

logger = logging.getLogger(__name__)


class ControllerV2_1:
    """Controller wrapper for Pico P4SPR Firmware V2.1.

    Provides high-level interface to rankbatch command with generator-based
    signal processing compatible with existing data acquisition code.
    """

    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 1.0):
        """Initialize controller.

        Args:
            port: Serial port (COM5, /dev/ttyACM0, etc.)
            baudrate: Baud rate (default: 115200)
            timeout: Serial timeout in seconds (default: 1.0)

        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._ser: serial.Serial | None = None
        self._firmware_version: str | None = None

    def connect(self):
        """Open serial connection to Pico."""
        if self._ser and self._ser.is_open:
            logger.warning(f"Already connected to {self.port}")
            return

        logger.info(f"Connecting to {self.port} at {self.baudrate} baud")
        self._ser = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
        time.sleep(2)  # Wait for Pico to be ready

        # Check firmware version
        self._firmware_version = self._check_version()
        logger.info(f"Connected to firmware version: {self._firmware_version}")

    def disconnect(self):
        """Close serial connection."""
        if self._ser and self._ser.is_open:
            self._ser.close()
            logger.info("Disconnected")

    def _check_version(self) -> str:
        """Check firmware version.

        Returns:
            Version string

        """
        if not self._ser:
            raise RuntimeError("Not connected")

        self._ser.write(b"iv\n")
        version = self._ser.readline().decode().strip()
        return version

    def is_rankbatch_supported(self) -> bool:
        """Check if rankbatch command is supported (V2.1+).

        Returns:
            True if rankbatch supported, False otherwise

        """
        if not self._firmware_version:
            self._firmware_version = self._check_version()

        return "2.1" in self._firmware_version

    def led_rank_batch_cycles(
        self,
        intensities: dict[str, int],
        settling_ms: int = 15,
        dark_ms: int = 5,
        num_cycles: int = 1,
    ) -> Generator[tuple[str, str], None, None]:
        """Execute rankbatch command and yield channel/signal pairs.

        This generator yields (channel, signal) tuples for each event:
        - ("start", "BATCH_START"): Sequence begins
        - ("cycle", "1"): Cycle N starts
        - ("a", "READY"): LED A on, settling
        - ("a", "READ"): Acquire spectrum for LED A
        - ("a", "DONE"): LED A off
        - ("cycle_end", "1"): Cycle N complete
        - ("end", "BATCH_END"): All cycles complete

        Args:
            intensities: Dict mapping channel ('a','b','c','d') to intensity (0-255)
            settling_ms: LED settling time in ms (default: 15)
            dark_ms: Dark time between LEDs in ms (default: 5)
            num_cycles: Number of complete 4-channel cycles (default: 1)

        Yields:
            (channel, signal) tuples

        Example:
            for channel, signal in ctrl.led_rank_batch_cycles(
                intensities={'a': 225, 'b': 94, 'c': 97, 'd': 233},
                settling_ms=15,
                dark_ms=5,
                num_cycles=1
            ):
                if signal == "READ":
                    logger.info(f"Acquiring spectrum for channel {channel}")
                    spectrum = detector.acquire()
                    process_spectrum(channel, spectrum)

        """
        if not self._ser or not self._ser.is_open:
            raise RuntimeError("Not connected")

        if not self.is_rankbatch_supported():
            raise RuntimeError(
                f"Rankbatch not supported by firmware version {self._firmware_version}. "
                "Requires V2.1 or higher.",
            )

        # Build command
        int_a = intensities.get("a", 0)
        int_b = intensities.get("b", 0)
        int_c = intensities.get("c", 0)
        int_d = intensities.get("d", 0)

        cmd = f"rankbatch:{int_a},{int_b},{int_c},{int_d},{settling_ms},{dark_ms},{num_cycles}\n"
        logger.debug(f"Sending rankbatch command: {cmd.strip()}")

        # Send command
        self._ser.write(cmd.encode())

        # Process signals
        try:
            while True:
                line = self._ser.readline().decode().strip()

                if not line:
                    logger.warning("Empty line received from firmware")
                    continue

                logger.debug(f"Firmware signal: {line}")

                # Parse signal
                if line == "BATCH_START":
                    yield ("start", "BATCH_START")

                elif line.startswith("CYCLE:"):
                    cycle_num = line.split(":")[1]
                    yield ("cycle", cycle_num)

                elif line.endswith(":READY"):
                    channel = line[0]
                    yield (channel, "READY")

                elif line.endswith(":READ"):
                    channel = line[0]
                    yield (channel, "READ")
                    # Caller should acquire spectrum, then we send ACK
                    self._ser.write(b"1\n")
                    logger.debug(f"Sent ACK for channel {channel}")

                elif line.endswith(":DONE"):
                    channel = line[0]
                    yield (channel, "DONE")

                elif line.endswith(":SKIP"):
                    channel = line[0]
                    yield (channel, "SKIP")

                elif line.startswith("CYCLE_END:"):
                    cycle_num = line.split(":")[1]
                    yield ("cycle_end", cycle_num)

                elif line == "BATCH_END":
                    yield ("end", "BATCH_END")
                    break

                else:
                    logger.warning(f"Unknown signal from firmware: {line}")

        except Exception as e:
            logger.error(f"Error during rankbatch execution: {e}")
            # Try to turn off all LEDs
            try:
                self._ser.write(b"lx\n")
            except:
                pass
            raise

        # Read final ACK
        final_ack = self._ser.readline().decode().strip()
        logger.debug(f"Final ACK: {final_ack}")

    def set_batch_intensities_legacy(self, intensities: dict[str, int]):
        """Legacy method for V2.0 compatibility (sequential batch commands).

        Use led_rank_batch_cycles() instead for V2.1 performance.

        Args:
            intensities: Dict mapping channel to intensity

        """
        if not self._ser or not self._ser.is_open:
            raise RuntimeError("Not connected")

        # Build batch command
        channels = ["a", "b", "c", "d"]
        intensity_list = [str(intensities.get(ch, 0)) for ch in channels]

        # Enable LEDs
        cmd1 = f"batch:{','.join(channels)}\n"
        self._ser.write(cmd1.encode())
        time.sleep(0.020)  # 20ms for batch enable

        # Set intensities
        cmd2 = f"lm:{','.join(intensity_list)}\n"
        self._ser.write(cmd2.encode())
        time.sleep(0.010)  # 10ms for intensity set

        logger.debug(f"Set batch intensities (legacy): {intensities}")


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    # Create controller
    ctrl = ControllerV2_1(port="COM5")

    try:
        # Connect
        ctrl.connect()

        # Check if rankbatch supported
        if ctrl.is_rankbatch_supported():
            print("✅ Rankbatch command supported!\n")

            # Test single cycle
            print("Testing single cycle...")
            intensities = {"a": 225, "b": 94, "c": 97, "d": 233}

            for channel, signal in ctrl.led_rank_batch_cycles(
                intensities=intensities,
                settling_ms=15,
                dark_ms=5,
                num_cycles=1,
            ):
                print(f"  {channel}: {signal}")

                if signal == "READ":
                    print(f"    → Acquiring spectrum for channel {channel}")
                    # Simulate detector read
                    time.sleep(0.150)
                    print("    → Spectrum acquired")

            print("\n✅ Test complete!")

        else:
            print("⚠️  Rankbatch not supported, using legacy mode")
            ctrl.set_batch_intensities_legacy({"a": 128})

    finally:
        ctrl.disconnect()
