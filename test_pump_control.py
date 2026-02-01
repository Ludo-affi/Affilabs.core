#!/usr/bin/env python3
"""Standalone Pump Control Test Script

Interactive script for controlling KC pumps independently or together.
- Aspirate/dispense specific volumes at specific flow rates
- Control pumps individually or synchronized
- Control 6-port and 3-way valves
- No detector required

Author: Affilabs
Date: January 7, 2026
"""

import sys
import time
from pathlib import Path

# Add parent to path for imports
parent_dir = Path(__file__).parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from affipump.affipump_controller import AffipumpController


class PumpTester:
    """Interactive pump control tester."""

    def __init__(self, port='COM8', baudrate=38400):
        """Initialize pump controller.
        
        Args:
            port: Serial port (default: COM8)
            baudrate: Baud rate (default: 38400)
        """
        print("=" * 60)
        print("KC Pump Control Test Script")
        print("=" * 60)

        self.controller = AffipumpController(
            port=port,
            baudrate=baudrate,
            syringe_volume_ul=1000,
            auto_recovery=True
        )

        try:
            print(f"\nConnecting to {port} @ {baudrate} baud...")
            self.controller.open()
            print("✅ Connected successfully!\n")

            # Show initial status
            self._show_status()

        except Exception as e:
            print(f"❌ Failed to connect: {e}")
            sys.exit(1)

    def _show_status(self):
        """Show current pump positions and status."""
        print("\n" + "=" * 60)
        print("CURRENT STATUS")
        print("=" * 60)

        try:
            # Pump 1
            pos1 = self.controller.get_position(1)
            status1 = self.controller.get_status(1)
            valve1 = self.controller.get_valve_position(1)

            print(f"Pump 1 (KC1): {pos1:.1f} µL / 1000 µL")
            if status1:
                busy1 = "BUSY" if status1.get('busy') else "IDLE"
                print(f"  Status: {busy1}")
                if status1.get('error_msg') and status1['error_msg'] != 'No Error':
                    print(f"  Error: {status1['error_msg']}")

            # Decode valve position
            if valve1:
                valve_name = self._decode_valve_position(valve1)
                print(f"  Valve: {valve_name}")

            # Pump 2
            pos2 = self.controller.get_position(2)
            status2 = self.controller.get_status(2)
            valve2 = self.controller.get_valve_position(2)

            print(f"\nPump 2 (KC2): {pos2:.1f} µL / 1000 µL")
            if status2:
                busy2 = "BUSY" if status2.get('busy') else "IDLE"
                print(f"  Status: {busy2}")
                if status2.get('error_msg') and status2['error_msg'] != 'No Error':
                    print(f"  Error: {status2['error_msg']}")

            # Decode valve position
            if valve2:
                valve_name = self._decode_valve_position(valve2)
                print(f"  Valve: {valve_name}")

        except Exception as e:
            print(f"Error getting status: {e}")

        print("=" * 60 + "\n")

    def _decode_valve_position(self, valve_data: str) -> str:
        """Decode valve position from pump response.
        
        Args:
            valve_data: Raw valve position data from pump
            
        Returns:
            Human-readable valve position
        """
        valve_data = valve_data.strip()

        # Map common positions - these are PORTS, not directions!
        valve_map = {
            'I': 'INPUT port (active)',
            'O': 'OUTPUT port (active)',
            'B': 'BYPASS port (active)',
            '1': 'Port 1',
            '2': 'Port 2',
            '3': 'Port 3',
            '4': 'Port 4',
            '5': 'Port 5',
            '6': 'Port 6'
        }

        return valve_map.get(valve_data, f"Port {valve_data}")

    def aspirate_pump(self, pump_num: int, volume_ul: float, flow_rate_ul_min: float, valve_position: str = None):
        """Aspirate (draw) liquid into pump.
        
        Args:
            pump_num: Pump number (1 or 2)
            volume_ul: Volume to aspirate in µL
            flow_rate_ul_min: Flow rate in µL/min
            valve_position: Valve position ('input', 'output', 'bypass', or None to skip)
        """
        print(f"\n→ Aspirating {volume_ul} µL at {flow_rate_ul_min} µL/min on Pump {pump_num}...")

        try:
            # Set valve if specified
            if valve_position:
                print(f"  Setting valve to {valve_position.upper()}...")
                self.set_valve(pump_num, valve_position)
                time.sleep(0.5)

            # Show current position before
            pos_before = self.controller.get_position(pump_num)
            print(f"  Position before: {pos_before:.1f} µL")

            speed_ul_s = flow_rate_ul_min / 60.0

            # Send commands manually to preserve the valve we already set
            # (aspirate() would switch to INPUT valve automatically)
            velocity_ul_s = self.controller._format_velocity_for_v_command(speed_ul_s)
            print(f"  DEBUG: Sending V{velocity_ul_s:.3f},1R (set speed)")
            self.controller.send_command(f"/{pump_num}V{velocity_ul_s:.3f},1R")
            time.sleep(0.1)
            print(f"  DEBUG: Sending P{volume_ul:.3f},1R (aspirate command)")
            self.controller.send_command(f"/{pump_num}P{volume_ul:.3f},1R")

            # Wait for completion
            print("  Waiting for completion...", end="", flush=True)
            start = time.time()
            timeout = (volume_ul / speed_ul_s) * 2 + 10  # 2x expected + buffer

            while time.time() - start < timeout:
                status = self.controller.get_status(pump_num)
                if status and not status.get('busy'):
                    elapsed = time.time() - start
                    print(f" Done! ({elapsed:.1f}s)")
                    pos = self.controller.get_position(pump_num)
                    print(f"  New position: {pos:.1f} µL")
                    return True
                time.sleep(0.2)

            print(" TIMEOUT!")
            return False

        except Exception as e:
            print(f"  ❌ Error: {e}")
            return False

    def dispense_pump(self, pump_num: int, volume_ul: float, flow_rate_ul_min: float, valve_position: str = None):
        """Dispense (push) liquid from pump.
        
        Args:
            pump_num: Pump number (1 or 2)
            volume_ul: Volume to dispense in µL
            flow_rate_ul_min: Flow rate in µL/min
            valve_position: Valve position ('input', 'output', 'bypass', or None to skip)
        """
        print(f"\n→ Dispensing {volume_ul} µL at {flow_rate_ul_min} µL/min on Pump {pump_num}...")

        try:
            # Set valve if specified
            if valve_position:
                print(f"  Setting valve to {valve_position.upper()}...")
                self.set_valve(pump_num, valve_position)
                time.sleep(0.3)

            speed_ul_s = flow_rate_ul_min / 60.0

            # Send commands manually to preserve the valve we already set
            # (dispense() would switch to OUTPUT valve automatically)
            velocity_ul_s = self.controller._format_velocity_for_v_command(speed_ul_s)
            print(f"  DEBUG: Sending V{velocity_ul_s:.3f},1R (set speed)")
            self.controller.send_command(f"/{pump_num}V{velocity_ul_s:.3f},1R")
            time.sleep(0.1)
            print(f"  DEBUG: Sending D{volume_ul:.3f},1R (dispense command)")
            self.controller.send_command(f"/{pump_num}D{volume_ul:.3f},1R")

            # Wait for completion
            print("  Waiting for completion...", end="", flush=True)
            start = time.time()
            timeout = (volume_ul / speed_ul_s) * 2 + 10

            while time.time() - start < timeout:
                status = self.controller.get_status(pump_num)
                if status and not status.get('busy'):
                    elapsed = time.time() - start
                    print(f" Done! ({elapsed:.1f}s)")
                    pos = self.controller.get_position(pump_num)
                    print(f"  New position: {pos:.1f} µL")
                    return True
                time.sleep(0.2)

            print(" TIMEOUT!")
            return False

        except Exception as e:
            print(f"  ❌ Error: {e}")
            return False

    def aspirate_both(self, volume_ul: float, flow_rate_ul_min: float, valve_position: str = None):
        """Aspirate both pumps simultaneously.
        
        Args:
            volume_ul: Volume to aspirate in µL
            flow_rate_ul_min: Flow rate in µL/min
            valve_position: Valve position ('input', 'output', 'bypass', or None to skip)
        """
        print(f"\n→ Aspirating BOTH pumps: {volume_ul} µL at {flow_rate_ul_min} µL/min...")

        try:
            # Set valves if specified
            if valve_position:
                print(f"  Setting both valves to {valve_position.upper()}...")
                self.set_valve(1, valve_position)
                self.set_valve(2, valve_position)
                time.sleep(0.3)

            speed_ul_s = flow_rate_ul_min / 60.0
            self.controller.aspirate_both(volume_ul, speed_ul_s)

            # Wait for both
            print("  Waiting for both pumps...", end="", flush=True)
            result = self.controller.wait_until_both_ready(timeout=120.0)
            p1_ready, p2_ready, elapsed, p1_time, p2_time = result

            if p1_ready and p2_ready:
                print(f" Done! ({elapsed:.1f}s)")
                pos1 = self.controller.get_position(1)
                pos2 = self.controller.get_position(2)
                print(f"  Pump 1: {pos1:.1f} µL")
                print(f"  Pump 2: {pos2:.1f} µL")
                return True
            else:
                print(" TIMEOUT!")
                if not p1_ready:
                    print("  Pump 1 did not complete")
                if not p2_ready:
                    print("  Pump 2 did not complete")
                return False

        except Exception as e:
            print(f"  ❌ Error: {e}")
            return False

    def dispense_both(self, volume_ul: float, flow_rate_ul_min: float, valve_position: str = None):
        """Dispense both pumps simultaneously.
        
        Args:
            volume_ul: Volume to dispense in µL
            flow_rate_ul_min: Flow rate in µL/min
            valve_position: Valve position ('input', 'output', 'bypass', or None to skip)
        """
        print(f"\n→ Dispensing BOTH pumps: {volume_ul} µL at {flow_rate_ul_min} µL/min...")

        try:
            # Set valves if specified
            if valve_position:
                print(f"  Setting both valves to {valve_position.upper()}...")
                self.set_valve(1, valve_position)
                self.set_valve(2, valve_position)
                time.sleep(0.3)

            speed_ul_s = flow_rate_ul_min / 60.0
            self.controller.dispense_both(volume_ul, speed_ul_s)

            # Wait for both
            print("  Waiting for both pumps...", end="", flush=True)
            result = self.controller.wait_until_both_ready(timeout=120.0)
            p1_ready, p2_ready, elapsed, p1_time, p2_time = result

            if p1_ready and p2_ready:
                print(f" Done! ({elapsed:.1f}s)")
                pos1 = self.controller.get_position(1)
                pos2 = self.controller.get_position(2)
                print(f"  Pump 1: {pos1:.1f} µL")
                print(f"  Pump 2: {pos2:.1f} µL")
                return True
            else:
                print(" TIMEOUT!")
                return False

        except Exception as e:
            print(f"  ❌ Error: {e}")
            return False

    def set_valve(self, pump_num: int, position: str):
        """Set 6-port valve position.
        
        IMPORTANT: Valve position controls which PORT is active, NOT the direction!
        - INPUT port: Usually connected to sample/buffer source
        - OUTPUT port: Usually connected to flow cell/detector
        - BYPASS port: Alternative routing
        
        You can ASPIRATE or DISPENSE from ANY port - the valve just selects which one.
        
        Args:
            pump_num: Pump number (1 or 2)
            position: 'input' (I), 'output' (O), or 'bypass' (B)
        """
        position_map = {
            'input': 'I',
            'i': 'I',
            'output': 'O',
            'o': 'O',
            'bypass': 'B',
            'b': 'B'
        }

        valve_pos = position_map.get(position.lower())
        if not valve_pos:
            print(f"❌ Invalid position: {position}. Use 'input', 'output', or 'bypass'")
            return False

        print(f"\n→ Setting Pump {pump_num} valve to {position.upper()} port...")

        try:
            cmd = f"/{pump_num}{valve_pos}R"
            print(f"  DEBUG: Sending command: {cmd}")
            response = self.controller.send_command(cmd)
            print(f"  DEBUG: Response: {response}")

            # Check if command was accepted (@ or ` in response = success)
            if b'@' in response or b'`' in response:
                print("  ✅ Valve command accepted by pump")
                time.sleep(0.5)  # Give valve time to move
                return True
            else:
                print("  ⚠️ Unexpected response from pump")
                return False

        except Exception as e:
            print(f"  ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False

    def initialize_pump(self, pump_num: int):
        """Initialize pump (home to zero position).
        
        Args:
            pump_num: Pump number (1 or 2, or 0 for both)
        """
        if pump_num == 0:
            print("\n→ Initializing BOTH pumps to zero position...")
        else:
            print(f"\n→ Initializing Pump {pump_num} to zero position...")

        try:
            self.controller.initialize_pump(pump_num)
            print("  Waiting for initialization...", end="", flush=True)

            # Poll for completion (initialization is usually instant if already at zero)
            start = time.time()
            timeout = 30.0

            if pump_num == 0:
                # Wait for both pumps
                while time.time() - start < timeout:
                    time.sleep(0.5)
                    status1 = self.controller.get_status(1)
                    status2 = self.controller.get_status(2)

                    if status1 and status2:
                        busy1 = status1.get('busy', True)
                        busy2 = status2.get('busy', True)

                        if not busy1 and not busy2:
                            elapsed = time.time() - start
                            print(f" Done! ({elapsed:.1f}s)")
                            pos1 = self.controller.get_position(1)
                            pos2 = self.controller.get_position(2)
                            print(f"  Pump 1: {pos1:.1f} µL")
                            print(f"  Pump 2: {pos2:.1f} µL")
                            return True

                print(" TIMEOUT!")
                return False

            else:
                # Wait for single pump
                while time.time() - start < timeout:
                    time.sleep(0.5)
                    status = self.controller.get_status(pump_num)

                    if status:
                        busy = status.get('busy', True)
                        if not busy:
                            elapsed = time.time() - start
                            print(f" Done! ({elapsed:.1f}s)")
                            pos = self.controller.get_position(pump_num)
                            print(f"  Position: {pos:.1f} µL")
                            return True

                print(" TIMEOUT!")
                return False

        except Exception as e:
            print(f"  ❌ Error: {e}")
            return False

    def terminate_pump(self, pump_num: int):
        """Emergency stop pump.
        
        Args:
            pump_num: Pump number (1 or 2, or 0 for both)
        """
        if pump_num == 0:
            print("\n→ TERMINATING BOTH pumps...")
            cmd = "/0TR"
        else:
            print(f"\n→ TERMINATING Pump {pump_num}...")
            cmd = f"/{pump_num}TR"

        try:
            self.controller.send_command(cmd)
            time.sleep(0.2)
            print("  ✅ Terminate command sent")
            return True

        except Exception as e:
            print(f"  ❌ Error: {e}")
            return False

    def run_menu(self):
        """Run interactive menu."""
        while True:
            print("\n" + "=" * 60)
            print("PUMP CONTROL MENU")
            print("=" * 60)
            print("1.  Aspirate Pump 1")
            print("2.  Dispense Pump 1")
            print("3.  Aspirate Pump 2")
            print("4.  Dispense Pump 2")
            print("5.  Aspirate BOTH pumps")
            print("6.  Dispense BOTH pumps")
            print("7.  Set Pump 1 valve (6-port)")
            print("8.  Set Pump 2 valve (6-port)")
            print("9.  Initialize Pump 1 (home to zero)")
            print("10. Initialize Pump 2 (home to zero)")
            print("11. Initialize BOTH pumps")
            print("12. Terminate Pump 1 (emergency stop)")
            print("13. Terminate Pump 2 (emergency stop)")
            print("14. Terminate BOTH pumps (emergency stop)")
            print("15. Show status")
            print("0.  Exit")
            print("=" * 60)

            choice = input("\nEnter choice: ").strip()

            try:
                if choice == '0':
                    print("\n👋 Exiting...")
                    break

                elif choice == '1':
                    volume = float(input("Volume (µL): "))
                    flow_rate = float(input("Flow rate (µL/min): "))
                    valve = input("Valve position (input/output/bypass or blank to skip): ").strip()
                    self.aspirate_pump(1, volume, flow_rate, valve if valve else None)

                elif choice == '2':
                    volume = float(input("Volume (µL): "))
                    flow_rate = float(input("Flow rate (µL/min): "))
                    valve = input("Valve position (input/output/bypass or blank to skip): ").strip()
                    self.dispense_pump(1, volume, flow_rate, valve if valve else None)

                elif choice == '3':
                    volume = float(input("Volume (µL): "))
                    flow_rate = float(input("Flow rate (µL/min): "))
                    valve = input("Valve position (input/output/bypass or blank to skip): ").strip()
                    self.aspirate_pump(2, volume, flow_rate, valve if valve else None)

                elif choice == '4':
                    volume = float(input("Volume (µL): "))
                    flow_rate = float(input("Flow rate (µL/min): "))
                    valve = input("Valve position (input/output/bypass or blank to skip): ").strip()
                    self.dispense_pump(2, volume, flow_rate, valve if valve else None)

                elif choice == '5':
                    volume = float(input("Volume (µL): "))
                    flow_rate = float(input("Flow rate (µL/min): "))
                    valve = input("Valve position (input/output/bypass or blank to skip): ").strip()
                    self.aspirate_both(volume, flow_rate, valve if valve else None)

                elif choice == '6':
                    volume = float(input("Volume (µL): "))
                    flow_rate = float(input("Flow rate (µL/min): "))
                    valve = input("Valve position (input/output/bypass or blank to skip): ").strip()
                    self.dispense_both(volume, flow_rate, valve if valve else None)

                elif choice == '7':
                    position = input("Position (input/output/bypass): ")
                    self.set_valve(1, position)

                elif choice == '8':
                    position = input("Position (input/output/bypass): ")
                    self.set_valve(2, position)

                elif choice == '9':
                    self.initialize_pump(1)

                elif choice == '10':
                    self.initialize_pump(2)

                elif choice == '11':
                    self.initialize_pump(0)

                elif choice == '12':
                    self.terminate_pump(1)

                elif choice == '13':
                    self.terminate_pump(2)

                elif choice == '14':
                    self.terminate_pump(0)

                elif choice == '15':
                    self._show_status()

                else:
                    print("❌ Invalid choice")

            except ValueError as e:
                print(f"❌ Invalid input: {e}")
            except KeyboardInterrupt:
                print("\n\n⚠️ Operation interrupted by user")
                self.terminate_pump(0)
            except Exception as e:
                print(f"❌ Error: {e}")

    def close(self):
        """Close connection."""
        try:
            self.controller.close()
            print("✅ Connection closed")
        except:
            pass


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="KC Pump Control Test Script")
    parser.add_argument('--port', default='COM8', help='Serial port (default: COM8)')
    parser.add_argument('--baudrate', type=int, default=38400, help='Baud rate (default: 38400)')

    args = parser.parse_args()

    tester = None
    try:
        tester = PumpTester(port=args.port, baudrate=args.baudrate)
        tester.run_menu()

    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if tester:
            tester.close()


if __name__ == "__main__":
    main()
