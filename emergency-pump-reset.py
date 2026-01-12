"""Emergency pump recovery script - resets serial connection and pumps"""

import time
import serial
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s :: %(levelname)s :: %(message)s')
logger = logging.getLogger(__name__)

def find_pump_port():
    """Find the Cavro pump serial port"""
    import serial.tools.list_ports
    
    ports = list(serial.tools.list_ports.comports())
    logger.info(f"Available ports: {[p.device for p in ports]}")
    
    # Look for Cavro pump (usually highest COM port)
    if ports:
        pump_port = max(ports, key=lambda p: int(p.device.replace('COM', ''))).device
        logger.info(f"Selected pump port: {pump_port}")
        return pump_port
    return None

def reset_serial_connection(port):
    """Force reset the serial connection"""
    logger.info(f"Resetting serial connection on {port}...")
    
    try:
        # Try to open and immediately close to reset hardware
        ser = serial.Serial(port, 9600, timeout=0.5)
        ser.close()
        time.sleep(1.0)
        
        # Reopen with proper settings
        ser = serial.Serial(
            port,
            9600,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.5,
            write_timeout=2.0
        )
        
        # Clear buffers
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        time.sleep(0.5)
        
        logger.info("Serial connection reset successfully")
        return ser
        
    except Exception as e:
        logger.error(f"Failed to reset serial: {e}")
        return None

def send_command(ser, cmd):
    """Send command and read response"""
    try:
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        
        full_cmd = f"{cmd}\r".encode('ascii')
        logger.info(f"Sending: {cmd}")
        ser.write(full_cmd)
        
        time.sleep(0.3)
        
        # Read response
        response = ser.read(1024)
        logger.info(f"Response: {response}")
        return response
        
    except Exception as e:
        logger.error(f"Command failed: {e}")
        return None

def emergency_pump_reset():
    """Execute emergency pump reset sequence"""
    
    # Find pump port
    port = find_pump_port()
    if not port:
        logger.error("No pump port found!")
        return False
    
    # Reset serial connection
    ser = reset_serial_connection(port)
    if not ser:
        logger.error("Failed to establish serial connection!")
        return False
    
    try:
        logger.info("=" * 60)
        logger.info("EMERGENCY PUMP RESET SEQUENCE")
        logger.info("=" * 60)
        
        # 1. Terminate both pumps
        logger.info("\n[Step 1] Terminating both pumps...")
        send_command(ser, "/1TR")
        time.sleep(0.5)
        send_command(ser, "/2TR")
        time.sleep(0.5)
        
        # 2. Clear errors on both pumps
        logger.info("\n[Step 2] Clearing errors...")
        send_command(ser, "/1WR")
        time.sleep(0.5)
        send_command(ser, "/2WR")
        time.sleep(0.5)
        
        # 3. Check status
        logger.info("\n[Step 3] Checking pump status...")
        status1 = send_command(ser, "/1?")
        time.sleep(0.3)
        status2 = send_command(ser, "/2?")
        time.sleep(0.3)
        
        # 4. Get positions
        logger.info("\n[Step 4] Checking pump positions...")
        pos1 = send_command(ser, "/1?1")
        time.sleep(0.3)
        pos2 = send_command(ser, "/2?1")
        time.sleep(0.3)
        
        # 5. Initialize pumps (move to zero position)
        logger.info("\n[Step 5] Initializing pumps (homing)...")
        logger.info("This will take ~10 seconds...")
        send_command(ser, "/1k100gZ0R")  # Set speed to 100 steps/sec, move to zero
        time.sleep(0.5)
        send_command(ser, "/2k100gZ0R")  # Set speed to 100 steps/sec, move to zero
        time.sleep(15)  # Wait for both pumps to complete initialization
        
        # 6. Final status check
        logger.info("\n[Step 6] Final status check...")
        final_status1 = send_command(ser, "/1?")
        time.sleep(0.3)
        final_status2 = send_command(ser, "/2?")
        time.sleep(0.3)
        
        logger.info("\n" + "=" * 60)
        logger.info("RESET SEQUENCE COMPLETE")
        logger.info("=" * 60)
        logger.info("\nPlease restart your application now.")
        
        return True
        
    except Exception as e:
        logger.error(f"Reset sequence failed: {e}")
        return False
        
    finally:
        if ser and ser.is_open:
            ser.close()
            logger.info("Serial port closed")

if __name__ == "__main__":
    logger.info("Starting emergency pump recovery...")
    logger.info("WARNING: This will terminate any running pump operations!")
    logger.info("")
    
    input("Press Enter to continue or Ctrl+C to cancel...")
    
    success = emergency_pump_reset()
    
    if success:
        logger.info("\n✓ Pumps reset successfully!")
        logger.info("\nNext steps:")
        logger.info("1. Close this window")
        logger.info("2. Restart your main application")
        logger.info("3. Try pump operations again")
    else:
        logger.error("\n✗ Reset failed - check pump power and serial connection")
        logger.error("\nTroubleshooting:")
        logger.error("1. Check pump power supply is ON")
        logger.error("2. Check USB cable connection")
        logger.error("3. Try unplugging/replugging the USB cable")
        logger.error("4. Power cycle the pump hardware")
