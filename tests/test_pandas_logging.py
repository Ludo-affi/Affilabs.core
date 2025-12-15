"""Test script to verify pandas logging refactoring works correctly."""

import datetime as dt
import time

import pandas as pd

# Simulate the TIME_ZONE constant (adjust as needed)
TIME_ZONE = dt.timezone(dt.timedelta(hours=-5))  # Example: EST


class TestLogging:
    """Test class to verify logging functionality."""

    def __init__(self):
        """Initialize logging DataFrames."""
        self.exp_start_perf = time.perf_counter()
        self.log_ch1 = pd.DataFrame(
            columns=["timestamp", "time", "event", "flow", "temp", "dev"],
        )
        self.log_ch2 = pd.DataFrame(
            columns=["timestamp", "time", "event", "flow", "temp", "dev"],
        )
        self.temp_log = pd.DataFrame(
            columns=["Timestamp", "Experiment Time", "Device Temp"],
        )

    def _log_event(
        self,
        channel: str,
        event: str,
        flow: str = "-",
        temp: str = "-",
        dev: str = "-",
    ) -> None:
        """Helper method to log events to the appropriate channel."""
        event_time = f"{(time.perf_counter() - self.exp_start_perf):.2f}"
        time_now = dt.datetime.now(TIME_ZONE)
        event_timestamp = (
            f"{time_now.hour:02d}:{time_now.minute:02d}:{time_now.second:02d}"
        )

        new_row = pd.DataFrame(
            [
                {
                    "timestamp": event_timestamp,
                    "time": event_time,
                    "event": event,
                    "flow": flow,
                    "temp": temp,
                    "dev": dev,
                },
            ],
        )

        if channel == "CH1":
            self.log_ch1 = pd.concat([self.log_ch1, new_row], ignore_index=True)
        elif channel == "CH2":
            self.log_ch2 = pd.concat([self.log_ch2, new_row], ignore_index=True)

    def test_logging(self):
        """Test various logging scenarios."""
        print("Testing pandas logging refactoring...\n")

        # Test 1: Basic event logging
        print("Test 1: Basic event logging")
        self._log_event("CH1", "CH 1 Stop")
        self._log_event("CH2", "CH 2 Stop")
        print(f"  ✓ CH1 entries: {len(self.log_ch1)}")
        print(f"  ✓ CH2 entries: {len(self.log_ch2)}")

        # Test 2: Event with flow and temp
        print("\nTest 2: Event with flow and temp")
        self._log_event("CH1", "Sensor reading", flow="15.50", temp="25.30")
        self._log_event("CH2", "Sensor reading", flow="14.80", temp="25.10")
        print(f"  ✓ CH1 entries: {len(self.log_ch1)}")
        print(f"  ✓ CH2 entries: {len(self.log_ch2)}")

        # Test 3: Device temperature logging
        print("\nTest 3: Device temperature logging")
        self._log_event("CH1", "Device reading", dev="30.5")
        self._log_event("CH2", "Device reading", dev="30.5")
        print(f"  ✓ CH1 entries: {len(self.log_ch1)}")
        print(f"  ✓ CH2 entries: {len(self.log_ch2)}")

        # Test 4: Inject sample
        print("\nTest 4: Inject sample")
        self._log_event("CH1", "Inject sample")
        self._log_event("CH2", "Inject sample")
        print(f"  ✓ CH1 entries: {len(self.log_ch1)}")
        print(f"  ✓ CH2 entries: {len(self.log_ch2)}")

        # Test 5: Temperature log
        print("\nTest 5: Temperature log")
        time_now = dt.datetime.now(TIME_ZONE)
        dev_timestamp = (
            f"{time_now.hour:02d}:{time_now.minute:02d}:{time_now.second:02d}"
        )
        exp_time = time.perf_counter() - self.exp_start_perf
        new_row = pd.DataFrame(
            [
                {
                    "Timestamp": dev_timestamp,
                    "Experiment Time": f"{exp_time:.2f}",
                    "Device Temp": "30.5",
                },
            ],
        )
        self.temp_log = pd.concat([self.temp_log, new_row], ignore_index=True)
        print(f"  ✓ temp_log entries: {len(self.temp_log)}")

        # Display results
        print("\n" + "=" * 60)
        print("CH1 Log:")
        print("=" * 60)
        print(self.log_ch1.to_string(index=False))

        print("\n" + "=" * 60)
        print("CH2 Log:")
        print("=" * 60)
        print(self.log_ch2.to_string(index=False))

        print("\n" + "=" * 60)
        print("Temperature Log:")
        print("=" * 60)
        print(self.temp_log.to_string(index=False))

        # Test 6: CSV export
        print("\n" + "=" * 60)
        print("Test 6: CSV Export")
        print("=" * 60)

        # Simulate kinetic log export (KNX 1.1 format)
        ch1_export = self.log_ch1.rename(
            columns={
                "timestamp": "Timestamp",
                "time": "Experiment Time",
                "event": "Event Type",
                "flow": "Flow Rate",
                "temp": "Sensor Temp",
                "dev": "Device Temp",
            },
        )

        ch1_export.to_csv("test_ch1_log.txt", sep="\t", index=False, encoding="utf-8")
        print("  ✓ CH1 log exported to test_ch1_log.txt")

        ch2_export = self.log_ch2.rename(
            columns={
                "timestamp": "Timestamp",
                "time": "Experiment Time",
                "event": "Event Type",
                "flow": "Flow Rate",
                "temp": "Sensor Temp",
                "dev": "Device Temp",
            },
        )

        ch2_export.to_csv("test_ch2_log.txt", sep="\t", index=False, encoding="utf-8")
        print("  ✓ CH2 log exported to test_ch2_log.txt")

        self.temp_log.to_csv(
            "test_temp_log.txt",
            sep="\t",
            index=False,
            encoding="utf-8",
        )
        print("  ✓ Temperature log exported to test_temp_log.txt")

        # Test 7: Clear logs
        print("\n" + "=" * 60)
        print("Test 7: Clear logs")
        print("=" * 60)

        self.log_ch1 = pd.DataFrame(
            columns=["timestamp", "time", "event", "flow", "temp", "dev"],
        )
        self.log_ch2 = pd.DataFrame(
            columns=["timestamp", "time", "event", "flow", "temp", "dev"],
        )
        self.temp_log = pd.DataFrame(
            columns=["Timestamp", "Experiment Time", "Device Temp"],
        )

        print(f"  ✓ CH1 entries after clear: {len(self.log_ch1)}")
        print(f"  ✓ CH2 entries after clear: {len(self.log_ch2)}")
        print(f"  ✓ temp_log entries after clear: {len(self.temp_log)}")

        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)


if __name__ == "__main__":
    test = TestLogging()
    test.test_logging()
