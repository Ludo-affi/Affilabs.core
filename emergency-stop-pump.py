"""Emergency Stop for AffiPump - Use if pump is running and won't stop."""
import sys
from affipump.affipump_controller import AffipumpController

def emergency_stop():
    """Send terminate command to both pumps on COM8."""
    print("🚨 EMERGENCY PUMP STOP 🚨")
    print("Attempting to stop both pumps on COM8...")

    try:
        # Connect to pump
        controller = AffipumpController(port='COM8')
        controller.open()
        print("✅ Connected to COM8")

        # Send broadcast terminate to all pumps
        print("⚠️  Sending TERMINATE to all pumps (broadcast)...")
        controller.send_command("/0TR")  # Address 0 = broadcast
        print("✅ Broadcast terminate sent")

        # Also send individual terminates for safety
        print("⚠️  Sending TERMINATE to pump 1...")
        controller.send_command("/1TR")
        print("✅ Pump 1 terminate sent")

        print("⚠️  Sending TERMINATE to pump 2...")
        controller.send_command("/2TR")
        print("✅ Pump 2 terminate sent")

        # Close connection
        controller.close()
        print("✅ Connection closed")
        print("\n✅ EMERGENCY STOP COMPLETE - Both pumps should be stopped")

    except Exception as e:
        print(f"❌ EMERGENCY STOP FAILED: {e}")
        print("⚠️  MANUAL ACTION REQUIRED: Power off the pump hardware immediately!")
        sys.exit(1)

if __name__ == "__main__":
    emergency_stop()
