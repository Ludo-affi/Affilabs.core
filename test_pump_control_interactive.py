"""
Interactive P4PROPLUS Internal Pump Control Test

Provides manual control over internal peristaltic pumps:
- Individual control (Pump 1, Pump 2)
- Synchronized control (Both pumps)
- Change flow rate on the fly
- Stop individual or all pumps
"""

import sys
from pathlib import Path

# Add affilabs to path
sys.path.insert(0, str(Path(__file__).parent))

from affilabs.utils.controller import PicoP4PRO


def print_menu():
    """Display control menu."""
    print("\n" + "="*70)
    print("  P4PROPLUS INTERNAL PUMP INTERACTIVE CONTROL")
    print("="*70)
    print("\nCOMMANDS:")
    print("  1 <rate>     - Start Pump 1 at <rate> uL/min (e.g., '1 100')")
    print("  2 <rate>     - Start Pump 2 at <rate> uL/min (e.g., '2 150')")
    print("  3 <rate>     - Start BOTH pumps at <rate> uL/min (e.g., '3 200')")
    print("  s1           - Stop Pump 1")
    print("  s2           - Stop Pump 2")
    print("  s3 or stop   - Stop ALL pumps")
    print("  info         - Show pump capabilities")
    print("  status       - Show current controller status")
    print("  q or quit    - Quit")
    print("\nFlow rate range: 1-300 uL/min")
    print("="*70)


def show_capabilities(ctrl):
    """Display pump capabilities."""
    if not ctrl.has_internal_pumps():
        print("[ERROR] No internal pumps detected!")
        return
    
    caps = ctrl.get_pump_capabilities()
    print("\n" + "="*70)
    print("PUMP CAPABILITIES")
    print("="*70)
    print(f"Type: {caps['type']}")
    print(f"Bidirectional: {caps['bidirectional']}")
    print(f"Flow rate range: {caps['min_flow_rate_ul_min']}-{caps['max_flow_rate_ul_min']} uL/min")
    print(f"RPM range: {caps['min_rpm']}-{caps['max_rpm']}")
    print(f"Calibration: {caps['ul_per_revolution']} uL/revolution")
    print(f"Recommended prime cycles: {caps['recommended_prime_cycles']}")
    print(f"\n{caps['suction_reliability_warning']}")
    print("="*70)


def show_status(ctrl):
    """Display controller status."""
    print("\n" + "="*70)
    print("CONTROLLER STATUS")
    print("="*70)
    print(f"Firmware: {ctrl.firmware_id}")
    print(f"Version: {ctrl.version}")
    print(f"Has internal pumps: {ctrl.has_internal_pumps()}")
    print(f"Serial port: {ctrl._ser.port if ctrl._ser else 'Not connected'}")
    print("="*70)


def process_command(ctrl, cmd):
    """Process user command."""
    cmd = cmd.strip().lower()
    
    if cmd in ['q', 'quit', 'exit']:
        return False
    
    if cmd == 'info':
        show_capabilities(ctrl)
        return True
    
    if cmd == 'status':
        show_status(ctrl)
        return True
    
    if cmd in ['s3', 'stop', 'stopall']:
        print("\n[CMD] Stopping ALL pumps...")
        result = ctrl.pump_stop(ch=3)
        print(f"[RESULT] {'Success' if result else 'Failed'}")
        return True
    
    if cmd == 's1':
        print("\n[CMD] Stopping Pump 1...")
        result = ctrl.pump_stop(ch=1)
        print(f"[RESULT] {'Success' if result else 'Failed'}")
        return True
    
    if cmd == 's2':
        print("\n[CMD] Stopping Pump 2...")
        result = ctrl.pump_stop(ch=2)
        print(f"[RESULT] {'Success' if result else 'Failed'}")
        return True
    
    # Parse start commands: "1 100", "2 150", "3 200"
    parts = cmd.split()
    if len(parts) == 2 and parts[0] in ['1', '2', '3']:
        try:
            channel = int(parts[0])
            rate = float(parts[1])
            
            # Convert to RPM for display
            rpm = ctrl._ul_min_to_rpm(rate)
            
            pump_name = {1: "Pump 1", 2: "Pump 2", 3: "BOTH pumps"}[channel]
            print(f"\n[CMD] Starting {pump_name} at {rate} uL/min ({rpm} RPM)...")
            
            result = ctrl.pump_start(rate_ul_min=rate, ch=channel)
            print(f"[RESULT] {'Success' if result else 'Failed'}")
            
        except ValueError:
            print(f"[ERROR] Invalid flow rate: {parts[1]}")
        except Exception as e:
            print(f"[ERROR] {e}")
        
        return True
    
    print("[ERROR] Unknown command. Type 'help' or see menu above.")
    return True


def main():
    """Interactive pump control loop."""
    print("="*70)
    print("  P4PROPLUS INTERNAL PUMP INTERACTIVE CONTROL")
    print("="*70)
    print("\nInitializing controller...")
    
    ctrl = PicoP4PRO()
    
    # Try to connect
    if not ctrl.open():
        print("[ERROR] Could not connect to P4PROPLUS controller!")
        print("Make sure the device is connected and powered on.")
        return
    
    print(f"[OK] Connected to {ctrl.firmware_id} version {ctrl.version}")
    
    # Check for internal pumps
    if not ctrl.has_internal_pumps():
        print(f"[ERROR] This firmware version ({ctrl.version}) does not have internal pumps!")
        print("P4PROPLUS V2.3+ required.")
        ctrl.close()
        return
    
    print(f"[OK] Internal pumps detected!")
    
    # Show initial info
    show_capabilities(ctrl)
    print_menu()
    
    # Interactive loop
    try:
        while True:
            try:
                user_input = input("\n>>> ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() == 'help':
                    print_menu()
                    continue
                
                should_continue = process_command(ctrl, user_input)
                if not should_continue:
                    break
                    
            except KeyboardInterrupt:
                print("\n\n[INFO] Interrupted by user (Ctrl+C)")
                break
            except EOFError:
                print("\n\n[INFO] EOF detected")
                break
    
    finally:
        # Stop all pumps on exit
        print("\n[CLEANUP] Stopping all pumps before exit...")
        try:
            ctrl.pump_stop(ch=3)
        except Exception as e:
            print(f"[WARN] Error stopping pumps: {e}")
        
        print("[CLEANUP] Closing controller...")
        ctrl.close()
        print("\n[DONE] Goodbye!")


if __name__ == "__main__":
    main()
