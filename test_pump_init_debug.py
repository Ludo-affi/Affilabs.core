"""Test pump initialization with detailed diagnostics"""
import sys
import time
import logging
from affipump.affipump_controller import AffipumpController

# Enable logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def test_pump_initialization():
    """Test pump initialization and capture detailed status"""

    # Use COM8 - the correct pump port
    pump_port = 'COM8'
    
    print(f"\nConnecting to pump on {pump_port}...")
    pump = AffipumpController(pump_port, baudrate=38400)

    try:
        pump.open()
        print("[OK] Pump controller opened\n")

        # Check initial status
        print("=== Initial Status ===")
        status1 = pump.get_status(1)
        status2 = pump.get_status(2)
        print(f"Pump 1: {status1}")
        print(f"Pump 2: {status2}")

        if status1:
            print(f"\nPump 1 Details:")
            print(f"  Busy: {status1.get('busy')}")
            print(f"  Error: {status1.get('error')}")
            print(f"  Error Msg: {status1.get('error_msg')}")
            print(f"  Status Char: {status1.get('status_char')}")
            print(f"  Initialized: {status1.get('initialized')}")

        if status2:
            print(f"\nPump 2 Details:")
            print(f"  Busy: {status2.get('busy')}")
            print(f"  Error: {status2.get('error')}")
            print(f"  Error Msg: {status2.get('error_msg')}")
            print(f"  Status Char: {status2.get('status_char')}")
            print(f"  Initialized: {status2.get('initialized')}")

        # Initialize pumps using proper method
        print("\n=== Initializing Pumps ===")
        pump.initialize_pumps()
        print("Initialization command sent")

        # Wait and monitor
        print("\n=== Monitoring Status (10 seconds) ===")
        for i in range(10):
            time.sleep(1)
            status1 = pump.get_status(1)
            status2 = pump.get_status(2)

            p1_busy = status1.get('busy', True) if status1 else 'NO_STATUS'
            p2_busy = status2.get('busy', True) if status2 else 'NO_STATUS'
            p1_err = status1.get('error_msg', 'N/A') if status1 else 'NO_STATUS'
            p2_err = status2.get('error_msg', 'N/A') if status2 else 'NO_STATUS'

            print(f"[{i+1}s] Pump1 busy={p1_busy}, err={p1_err} | Pump2 busy={p2_busy}, err={p2_err}")

            if status1 and not status1.get('busy', True):
                print(f"  -> Pump 1 became ready at {i+1}s")
            if status2 and not status2.get('busy', True):
                print(f"  -> Pump 2 became ready at {i+1}s")

    except Exception as e:
        print(f"\n[ERROR] Exception occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        pump.close()
        print("\n[OK] Pump controller closed")

if __name__ == "__main__":
    test_pump_initialization()
